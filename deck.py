#Copyright (c) 2009-11 Walter Bender

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

import gtk
from random import randrange

from card import Card, board_card
from genpieces import generate_tile_1_line, generate_tile_2_lines
from utils import json_dump, json_load
from constants import HIDE, BOARD, ROW, COL


class Deck:
    ''' Class for defining deck of cards. '''

    def __init__(self, sprites, scale=1.0, color='#000000'):
        ''' Create the deck of cards. '''
        self.cards = []
        i = 0
        for a in range(16):
            self.cards.append(Card(sprites,
                generate_tile_1_line(-1, 0, 0, 0, scale),
                [generate_tile_1_line(-1, 0, 0, 0, scale, color)], number=i))
            self.cards[-1].set_paths([[0, 0, 0, 1]])
            i += 1
        for a in range(4):
            self.cards.append(Card(sprites,
                generate_tile_1_line(-1, 0, 1, 0, scale),
                [generate_tile_1_line(-1, 0, 1, 0, scale, color)], number=i))
            self.cards[-1].set_paths([[0, 1, 0, 1]])
            i += 1
        for a in range(12):
            self.cards.append(Card(sprites,
                generate_tile_2_lines(-1, 0, 1, 0, 0, 0, 0, 1, scale),
                [generate_tile_2_lines(-1, 0, 1, 0, 0, 0, 0, 1, scale,
                                        [color, color])], number=i))
            self.cards[-1].set_paths([[0, 1, 1, 1]])
            i += 1
        for a in range(16):
            self.cards.append(Card(sprites,
                generate_tile_2_lines(-1, 0, 0, 0, 0, -1, 0, 0, scale),
                [generate_tile_2_lines(-1, 0, 0, 0, 0, -1, 0, 0, scale,
                                        [color, color])], number=i))
            self.cards[-1].set_paths([[1, 0, 0, 1]])
            i += 1
        for a in range(4):
            self.cards.append(Card(sprites,
                generate_tile_2_lines(-1, 0, 1, 0, 0, -1, 0, 1, scale),
                [generate_tile_2_lines(-1, 0, 1, 0, 0, -1, 0, 1, scale,
                                        [color, color])], number=i))
            self.cards[-1].set_paths([[1, 1, 1, 1]])
            i += 1
        for a in range(8):
            self.cards.append(Card(sprites,
                generate_tile_2_lines(0, -1, 1, 0, -1, 0, 0, 1, scale),
                [generate_tile_2_lines(0, -1, 1, 0, -1, 0, 0, 1, scale,
                                       [color, '#000000']),
                 generate_tile_2_lines(0, -1, 1, 0, -1, 0, 0, 1, scale,
                                       ['#000000', color]),
                 generate_tile_2_lines(0, -1, 1, 0, -1, 0, 0, 1, scale,
                                       [color, color])], number=i))
            self.cards[-1].set_paths([[1, 1, 0, 0], [0, 0, 1, 1]])
            i += 1
        for a in range(4):
            self.cards.append(Card(sprites,
                generate_tile_2_lines(0, -1, 1, 0, -1, 0, 0, 0, scale),
                [generate_tile_2_lines(0, -1, 1, 0, -1, 0, 0, 0, scale,
                                       [color, '#000000']),
                 generate_tile_2_lines(0, -1, 1, 0, -1, 0, 0, 0, scale,
                                       ['#000000', color]),
                 generate_tile_2_lines(0, -1, 1, 0, -1, 0, 0, 0, scale,
                                       [color, color])], number=i))
            self.cards[-1].set_paths([[1, 1, 0, 0], [0, 0, 0, 1]])
            i += 1

        # Remember the current position in the deck.
        self.index = 0

        # And a playing surface
        self.board = board_card(sprites, scale=scale)
        self.board.set_layer(BOARD)

    def shuffle(self):
        ''' Shuffle the deck (Knuth algorithm). '''
        decksize = self.count()
        # Hide all the cards and make sure they are back to orientation 0
        for c in self.cards:
            c.reset()
        # Randomize the card order.
        for n in range(decksize):
            i = randrange(decksize - n)
            self.swap_cards(n, decksize - 1 - i)            
        # Reset the index to the beginning of the deck after a shuffle,
        self.index = 0
        self.hide()
        return

    def random_order(self, size=ROW * COL):
        ''' randomize a list'''
        order = []
        for i in range(size):
            order.append(i)
        for n in range(size):
            i = randrange(size - n)
            a = order[n]
            order[n] = order[size - 1 - i]
            order[size - 1 - i] = a
        return order

    def serialize(self):
        ''' Serialize the deck for passing to share and saving '''
        order = []
        for i in range(ROW * COL):
            order.append(self.cards[i].number)
        return json_dump(order)

    def restore(self, deck_as_text):
        ''' Restore the deck upon resume. '''
        deck = []
        order = json_load(deck_as_text)
        for i in order:
            deck.append(self.cards[order[i]])
        self.cards = deck[:]

    def clear(self):
        ''' Remove any highlight from the cards. '''
        for i in self.cards:
            i.reset()

    def swap_cards(self,i,j):
        ''' Swap the position of two cards in the deck. '''
        tmp = self.cards[j]
        self.cards[j] = self.cards[i]
        self.cards[i] = tmp
        return

    def spr_to_card(self, spr):
        ''' Given a sprite, find the corresponding card in the deck. '''
        for c in self.cards:
            if c.spr == spr:
                return c
        return None

    def index_to_card(self, i):
        ''' Given a card index, find the corresponding card in the deck. '''
        for c in self.cards:
            if c.index == i:
                return c
        return None

    def deal_next_card(self):
        ''' Return the next card from the deck. '''
        if self.empty():
            return None
        next_card = self.cards[self.index]
        self.index += 1
        return next_card
 
    def empty(self):
        ''' Is the deck empty? '''
        if self.cards_remaining() > 0:
            return False
        else:
            return True

    def cards_remaining(self):
        ''' Return how many cards are remaining in the deck. '''
        return(self.count()-self.index)

    def hide(self):
        ''' Hide the deck. '''
        for c in self.cards:
            if c is not None:
                c.hide_card()

    def count(self):
        ''' Return the length of the deck. '''
        return len(self.cards)
