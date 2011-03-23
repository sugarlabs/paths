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
from utils import json_dump, json_load
from constants import ROW, COL, GRID, CARDS


class Grid:
    ''' Class for managing ROWxCOL matrix of cards '''

    def __init__(self, sprites, width, height, card_width, card_height, scale,
                 color):
        # the playing surface
        self.grid = []
        self.blanks = []

        for i in range(ROW * COL):
            self.grid.append(None)

        # card spacing
        self.left_hand = int(card_width / 2)
        self.left = int((width - (card_width * COL)) / 2 + card_width)
        self.xinc = int(card_width)
        self.top = 0
        self.yinc = int(card_height)

        for i in range(ROW * COL):
            self.blanks.append(blank_card(sprites, scale=scale, color=color))
            self.blanks[i].move(self.grid_to_xy(i))
            self.blanks[i].set_layer(GRID)

    def clear(self):
        for i in range(ROW * COL):
            self.grid[i] = None

    def cards_in_grid(self):
        ''' How many cards are on the grid? '''
        return ROW * COL - self.grid.count(None)

    def serialize(self):
        ''' Serialize the grid for passing to share and saving '''
        grid = []
        for i in range(ROW * COL):
            if self.grid[i] is not None:
                grid.append([self.grid[i].number, self.grid[i].orientation])
            else:
                grid.append([None, None])
        return json_dump(grid)

    def restore(self, grid_as_text, deck):
        ''' Restore cards to grid upon resume or share. '''
        self.hide()
        grid = json_load(grid_as_text)
        for i in range(ROW * COL):
            if grid[i][0] is None:
                self.grid[i] = None
            else:
                for k in range(ROW * COL):
                    if deck.cards[k].number == grid[i][0]:
                        self.add_card_to_grid(k, grid[i][1], i, deck) 
                        break
        self.show()

    def add_card_to_grid(self, card_number, orientation, grid_number, deck):
        ''' Add cards[card_number] to grid[grid_number] at orientation ''' 
        self.grid[grid_number] = deck.cards[card_number]
        self.grid[grid_number].spr.move(self.grid_to_xy(grid_number))
        self.grid[grid_number].spr.set_layer(CARDS)
        while orientation > 0:
            self.grid[grid_number].rotate_clockwise()
            orientation -= 90

    def place_a_card(self, c, x, y):
        ''' Place a card at position x,y and display it. '''
        if c is not None:
            c.spr.move((x, y))
            c.spr.set_layer(CARDS)

    def xy_to_grid(self, x, y):
        ''' Convert from sprite x,y to grid index. '''
        if x > self.left:
            return COL * int((y - self.top) / self.yinc) + \
                   int((x - self.left) / self.xinc)
        else:
            return None

    def grid_to_xy(self, i):
        ''' Convert from grid index to sprite x,y. '''
        return (int((self.left + i % COL * self.xinc)),
                int((self.top + (i / COL) * self.yinc)))

    def grid_to_spr(self, i):
        ''' Return the sprite in grid-position i. '''
        return self.grid[i].spr

    def spr_to_grid(self, spr):
        ''' Return the index of a sprite in grid. '''
        for i in range(ROW * COL):
            if self.grid[i] is not None and self.grid[i].spr == spr:
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
  
