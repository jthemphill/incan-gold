import random
import sandbox
import six
import time

# Constants
NTRAPTRIGGER = 2
NTRAPS = 3
NTRAPTYPES = 5
NROUNDS = 5

# Treasure distribution
TREASURES = [1,2,3,4,5,5,7,7,9,11,11,13,14,15,17]
ARTIFACT_VALUES = [5, 5, 5, 10, 10]

# Card types
TRAP = 0
TREASURE = 1
ARTIFACT = 2

# Trap types
FIRE = 0
MUMMY = 1
ROCKSLIDE = 2
SNAKES = 3
SPIDERS = 4

# Player statuses
OUT = 0
STAY = 1
LEAVE = 2

class Player:
    def __init__(self, pk, cwd, cmd):
        self.pk = pk
        self.pipe = sandbox.get_sandbox(cwd)
        self.pipe.start(cmd)

        self.wealth = 0

    def get_ready(self):
        ready = self.pipe.read_line()
        if ready != 'ready':
            raise BadBotException(self.pk)
        
    def start_round(self):
        self.wealth_held = 0
        self.in_temple = True

    def move(self):
        if not self.in_temple:
            return OUT

        move = self.pipe.read_line()

        if move == None:
            return None
        elif move == 'stay':
            return STAY
        elif move == 'leave':
            return LEAVE
        else:
            raise InvalidMoveException(self.pk)

    def leave(self, added_wealth):
        self.in_temple = False
        self.wealth += added_wealth

    def tell(self, output):
        if not self.pipe.is_alive:
            raise BadBotException(self.pk)
        for line in output:
            self.pipe.write_line(' '.join(map(str, line)))
        self.pipe.write_line('end')

    def cleanup(self):
        self.pipe.kill()

def trap_name(trap_type):
    if trap_type == FIRE:
        return 'fire'
    elif trap_type == MUMMY:
        return 'mummy'
    elif trap_type == ROCKSLIDE:
        return 'rockslide'
    elif trap_type == SNAKES:
        return 'snake'
    elif trap_type == SPIDERS:
        return 'spiders'
    raise InvalidMoveException()

class Deck:
    def __init__(self):
        self.artifacts = 0
        self.trap_quantities = [NTRAPS for i in range(NTRAPTYPES)]
        self.cards = None

    def start_round(self):
        self.artifacts += 1
        self.cards = []
        for x in TREASURES:
            self.cards.append((TREASURE, x))
        for i in range(NTRAPTYPES):
            for j in range(NTRAPS):
                self.cards.append((TRAP, i))

        for i in range(self.artifacts):
            self.cards.append((ARTIFACT, -1))

        random.shuffle(self.cards)

    def draw(self):
        return self.cards.pop()

class Game:
    def __init__(self, players, opts = None):
        self.players = players
        self.round_number = 0
        self.turn_number = 0
        self.deck = Deck()
        self.artifacts_taken = 0

        self.opts = {
            'loadtime': 100,
            'turntime': 100,
            'nplayers': len(self.players),
        }

        if opts is not None:
            for k in opts:
                self.opts[k] = opts[k]

    def play(self):
        self.broadcast_params()
        time.sleep(float(self.opts['loadtime']) / 1000)
        for p in self.players:
            p.get_ready()

        for i in range(NROUNDS):
            self.start_round()
            while not self.all_players_have_left():
                event = self.enter_room()
                self.broadcast_turn(event)
                if self.trap_was_triggered():
                    for i, n in enumerate(self.traps):
                        if n == NTRAPTRIGGER:
                            self.deck.trap_quantities[i] -= 1
                            break
                    break
                moves = self.get_all_moves(self.opts['turntime'])
                self.process_moves(moves)

        return self.players

    def start_round(self):
        self.round_number += 1
        self.turn_number = 0

        self.wealth_held = 0
        self.treasures = []
        self.traps = [0 for i in range(NTRAPTYPES)]
        self.artifacts_seen = 0

        self.deck.start_round()
        for p in self.players:
            p.start_round()

    def enter_room(self):
        num_active_players = len([p for p in self.players if p.in_temple])
        card_type, card_value = self.deck.draw()
        if card_type == TRAP:
            self.traps[card_value] += 1
        elif card_type == TREASURE:
            self.wealth_held += card_value // num_active_players
            self.treasures.append(card_value % num_active_players)
        elif card_type == ARTIFACT:
            self.artifacts_seen += 1

        return (card_type, card_value)

    def get_all_moves(self, turntime):
        t0 = time.time() * 1000
        moves = {p.pk: OUT for p in self.players if not p.in_temple}
        while len(moves) < len(self.players) and time.time() * 1000 < t0 + turntime:
            for p in self.players:
                move = p.move()
                if move is not None:
                    moves[p.pk] = move

        # If you don't decide within the turntime, you're leaving.
        for p in self.players:
            if p.in_temple and p.pk not in moves:
                moves[p.pk] = LEAVE

        return moves

    def process_moves(self, moves):
        leaving = {
            pk: self.players[pk]
            for (pk, move) in moves.items()
            if move == LEAVE
        }
        funds_taken = self.wealth_held
        if leaving:
            for i in range(len(self.treasures)):
                funds_taken += self.treasures[i] // len(leaving)
                self.treasures[i] = self.treasures[i] % len(leaving)

        if len(leaving) == 1:
            funds_taken += self.value_of_artifacts(self.artifacts_seen)
            self.artifacts_taken += self.artifacts_seen
            self.deck.artifacts = 0

        for pk in leaving:
            self.players[pk].leave(funds_taken)

    def trap_was_triggered(self):
        return any([t == NTRAPTRIGGER for t in self.traps])

    def all_players_have_left(self):
            return not any([p for p in self.players if p.in_temple])

    def value_of_artifacts(self, artifacts):
        value = 0
        for i in range(artifacts):
            value += ARTIFACT_VALUES[self.artifacts_taken + i]
        return value

    def broadcast_params(self):
        for p in self.players:
            p.tell(self.opts.items() + [['you', p.pk]])

    def broadcast_turn(self, event):
        turn = [
            ['turn', self.round_number, self.turn_number],
            ['players'] + [self.render_player_status(p) for p in self.players],
            self.render_event(event),
        ]
        for p in self.players:
            p.tell(turn)

    def render_event(self, event):
        if event[0] == TRAP:
            return ['trap', trap_name(event[1])]
        elif event[0] == TREASURE:
            return ['treasure', event[1]]
        elif event[0] == ARTIFACT:
            return ['artifact']
        raise Exception(event)
        
    def render_player_status(self, player):
        if player.in_temple:
            return 'stay'
        else:
            return 'out'

@six.python_2_unicode_compatible
class BadBotException(Exception):
    def __init__(self, pk):
        self.pk = pk

    def __str__(self):
        return 'Player {} crashed!'.format(self.pk)

@six.python_2_unicode_compatible
class InvalidMoveException(Exception):
    def __init__(self, pk):
        self.pk = pk

    def __str__(self):
        return 'Player {} made an invalid move!'.format(self.pk)
