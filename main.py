import argparse
import os
import sys

import game

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('commands', type=str, nargs='+')
    args = parser.parse_args(sys.argv[1:])

    cwd = os.getcwd()

    players = [game.Player(i, cwd, cmd) for i, cmd in enumerate(args.commands)]
    g = game.Game(players)
    try:
        g.play()
        for p in g.players:
            print('Player {}: {}'.format(p.pk, p.wealth))
    finally:
        for p in g.players:
            p.cleanup()

if __name__ == '__main__':
    main()
