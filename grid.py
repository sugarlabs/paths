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

from deck import Deck
from card import blank_card

ROW = 8
COL = 8


class Grid:
    ''' Class for managing ROWxCOL matrix of cards '''

    def __init__(self, sprites, width, height, card_width, card_height, scale):
        # the playing surface
        self.grid = []
        self.blanks = []

        # the tiles in your hand        
        self.hand = []

        for i in range(ROW * COL):
            self.grid.append(None)

        for i in range(COL):
            self.hand.append(None)

        # card spacing
        self.left_hand = int(card_width / 2)
        self.left = int((width - (card_width * COL)) / 2 + card_width)
        self.xinc = int(card_width)
        self.top = 0
        self.yinc = int(card_height)

        for i in range(ROW * COL):
            self.blanks.append(blank_card(sprites, scale))
            self.blanks[i].move(self.grid_to_xy(i))

    def deal(self, deck):
        ''' Deal an initial set of cards to the hand '''
        for i in range(COL):
            self.hand[i] = deck.deal_next_card()
            self.place_a_card(self.hand[i], self.hand_to_xy(i)[0],
                                  self.hand_to_xy(i)[1])

        # and empty the grid
        for i in range(ROW * COL):
            self.grid[i] = None

    def redeal(self, deck):
        ''' Deal another set of cards to the hand '''
        for i in range(COL):
            self.hand[i] = deck.deal_next_card()
            self.place_a_card(self.hand[i], self.hand_to_xy(i)[0],
                                  self.hand_to_xy(i)[1])

    def find_empty_slot(self):
        ''' Is there an empty slot in the hand? '''
        for i in range(COL):
            if self.hand[i] == None:
                return i
        return None

    def cards_in_hand(self):
        ''' How many cards are in the hand? '''
        return COL - self.hand.count(None)

    def cards_in_grid(self):
        ''' How many cards are on the grid? '''
        return ROW * COL - self.grid.count(None)

    def restore(self, deck, saved_card_index):
        ''' Restore cards to grid upon resume or share. '''
        # TODO: restore hand too
        self.hide()
        j = 0
        for i in saved_card_index:
            if i is None:
                self.grid[j] = None
            else:
                self.grid[j] = deck.index_to_card(i)
            j += 1
        self.show()

    def place_a_card(self, c, x, y):
        ''' Place a card at position x,y and display it. '''
        if c is not None:
            c.spr.move((x, y))
            c.spr.set_layer(2000)

    def xy_to_grid(self, x, y):
        ''' Convert from sprite x,y to grid index. '''
        return COL * int((y - self.top) / self.yinc) + \
               int((x - self.left) / self.xinc)

    def xy_to_hand(self, x, y):
        ''' Convert from sprite x,y to hand index. '''
        return int((y - self.top) / self.yinc)

    def grid_to_xy(self, i):
        ''' Convert from grid index to sprite x,y. '''
        return (int((self.left + i % COL * self.xinc)),
                int((self.top + (i / COL) * self.yinc)))

    def hand_to_xy(self, i):
        ''' Convert from hand index to sprite x,y. '''
        return ((self.left_hand, (self.top + i * self.yinc)))

    def grid_to_spr(self, i):
        ''' Return the sprite in grid-position i. '''
        return self.grid[i].spr

    def hand_to_spr(self, i):
        ''' Return the sprite in hand-position i. '''
        return self.hand[i].spr

    def spr_to_grid(self, spr):
        ''' Return the index of a sprite in grid. '''
        for i in range(ROW * COL):
            if self.grid[i] is not None and self.grid[i].spr == spr:
                return(i)
        return None

    def spr_to_hand(self, spr):
        ''' Return the index of a sprite in hand. '''
        for i in range(COL):
            if self.hand[i] is not None and self.hand[i].spr == spr:
                return(i)
        return None

    def hide(self):
        ''' Hide all of the cards on the grid. '''
        for i in range(ROW * COL):
            if self.grid[i] is not None:
                self.grid[i].hide_card()

    def show(self):
        ''' Restore all card on the grid to their x,y positions. '''
        for i in range(ROW * COL):
            self.place_a_card(self.grid[i],self.grid_to_xy(i)[0],
                              self.grid_to_xy(i)[1])
  
