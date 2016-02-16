import random
import sys

class RandomBot:
    me = None
    players = None

    def process_line(self, line):
        data = line.rstrip().split(' ')
        if data[0] == 'you':
            self.me = int(data[1])
        elif data[0] == 'players':
            self.players = data[1:]
        elif data[0] == 'end':
            return self.choose_action()

        return None

    def choose_action(self):
        if self.players is None:
            return 'ready'
        elif self.players[self.me] != 'stay':
            return None

        if random.randint(0, 10):
            return 'stay'
        else:
            return 'leave'

if __name__ == '__main__':
    bot = RandomBot()
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        action = bot.process_line(line)
        if action is not None:
            sys.stdout.write(action)
            sys.stdout.write('\n')
            sys.stdout.flush()
