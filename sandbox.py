import argparse
import os
import shlex
import signal
import six
import subprocess
import sys
import threading
import time
from six.moves import queue

# make python 3.x compatible with python 2.x
if six.PY3:
    def unicode(s, errors="strict"):
        if isinstance(s, str):
            return s
        elif isinstance(s, bytes) or isinstance(s, bytearray):
            return s.decode("utf-8", errors)
        raise SandboxError("Tried to convert unrecognized type to unicode")

class SandboxError(Exception):
    pass

def _monitor_file(fd, q):
    while True:
        line = fd.readline()
        if not line:
            q.put(None)
            break
        line = unicode(line, errors="replace")
        line = line.rstrip('\r\n')
        q.put(line)

class House:
    """Provide an insecure sandbox to run arbitrary commands in."""

    def __init__(self, working_directory):
        self._is_alive = False
        self.command_process = None
        self.stdout_queue = queue.Queue()
        self.working_directory = working_directory

    def start(self, shell_command):
        """Start a command running in the sandbox"""
        if self.is_alive:
            raise SandboxError("Tried to run command with one in progress.")
        working_directory = self.working_directory
        self.child_queue = queue.Queue()
        shell_command = shlex.split(shell_command)
        try:
            self.command_process = subprocess.Popen(shell_command,
                                                    stdin=subprocess.PIPE,
                                                    stdout=subprocess.PIPE,
                                                    stderr=sys.stderr,
                                                    universal_newlines=True,
                                                    cwd=working_directory)
        except OSError:
            raise SandboxError('Failed to start {0}'.format(shell_command))
        self._is_alive = True
        stdout_monitor = threading.Thread(target=_monitor_file,
                                args=(self.command_process.stdout, self.stdout_queue))
        stdout_monitor.daemon = True
        stdout_monitor.start()
        threading.Thread(target=self._child_writer).start()

    def kill(self):
        """Stops the sandbox.

        Shuts down the sandbox, cleaning up any spawned processes, threads, and
        other resources. The shell command running inside the sandbox may be
        suddenly terminated.

        """
        if self.is_alive:
            try:
                self.command_process.kill()
            except OSError:
                pass
            self.command_process.wait()
            self.child_queue.put(None)

    @property
    def is_alive(self):
        """Indicates whether a command is currently running in the sandbox"""
        if self._is_alive:
            sub_result = self.command_process.poll()
            if sub_result is None:
                return True
            self.child_queue.put(None)
            self._is_alive = False
        return False

    def pause(self):
        """Pause the process by sending a SIGSTOP to the child

        A limitation of the method is it will only pause the initial
        child process created any further (grandchild) processes created
        will not be paused.

        This method is a no-op on Windows.
        """
        try:
            self.command_process.send_signal(signal.SIGSTOP)
        except (ValueError, AttributeError, OSError):
            pass

    def resume(self):
        """Resume the process by sending a SIGCONT to the child

        This method is a no-op on Windows
        """
        try:
            self.command_process.send_signal(signal.SIGCONT)
        except (ValueError, AttributeError, OSError):
            pass

    def _child_writer(self):
        q = self.child_queue
        stdin = self.command_process.stdin
        while True:
            ln = q.get()
            if ln is None:
                break
            try:
                stdin.write(ln)
                stdin.flush()
            except (OSError, IOError):
                self.kill()
                break

    def write(self, str):
        """Write str to stdin of the process being run"""
        if not self.is_alive:
            return False
        self.child_queue.put(str)

    def write_line(self, line):
        """Write line to stdin of the process being run

        A newline is appended to line and written to stdin of the child process

        """
        if not self.is_alive:
            return False
        self.child_queue.put(line + "\n")

    def read_line(self, timeout=0):
        """Read line from child process

        Returns a line of the child process' stdout, if one isn't available
        within timeout seconds it returns None. Also guaranteed to return None
        at least once after each command that is run in the sandbox.

        """
        if not self.is_alive:
            timeout=0
        try:
            return self.stdout_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def check_path(self, path, errors):
        resolved_path = os.path.join(self.working_directory, path)
        if not os.path.exists(resolved_path):
            errors.append("Output file " + str(path) + " was not created.")
            return False
        else:
            return True

def get_sandbox(working_dir):
    return House(working_dir)

def main():
    parser = argparse.ArgumentParser(usage="usage: %prog [options] <command to run>")
    parser.add_option("-d", "--directory", action="store", dest="working_dir",
            default=".",
            help="Working directory to run command in")
    parser.add_option("-l", action="append", dest="send_lines", default=list(),
            help="String to send as a line on commands stdin")
    parser.add_option("-s", "--send-delay", action="store", dest="send_delay",
            type="float", default=0.0,
            help="Time in seconds to sleep after sending a line")
    parser.add_option("-r", "--receive-wait", action="store",
            dest="resp_wait", type="float", default=600,
            help="Time in seconds to wait for another response line")
    options, args = parser.parse_args()
    if len(args) == 0:
        parser.error("Must include a command to run.\
                \nRun with --help for more information.")

    print("Sandbox working directory: %s" % (options.working_dir))
    sandbox = get_sandbox(options.working_dir)
    try:
        print()
        sandbox.start(" ".join(args))
        for line in options.send_lines:
            sandbox.write_line(line)
            print("sent: " + line)
            time.sleep(options.send_delay)
        while True:
            response = sandbox.read_line(options.resp_wait)
            if response is None:
                print()
                print("No more responses. Terminating.")
                break
            print("response: " + response)
    finally:
        sandbox.kill()

if __name__ == "__main__":
    main()
