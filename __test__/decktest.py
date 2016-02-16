import unittest

import game

class DeckTest(unittest.TestCase):
    def test_init(self):
        deck = game.Deck()
        assert len(deck.trap_quantities) == game.NTRAPTYPES
        for trap_q in deck.trap_quantities:
            assert trap_q == game.NTRAPS

    def test_start_round(self):
        deck = game.Deck()
        deck.start_round()
        assert len(deck.cards) == 31

    def test_trap_removal(self):
        
