#Copyright (c) 2011 Walter Bender

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

from utils import json_dump, json_load

ROW = 8
COL = 8
TILES = 3


class Hand:
    ''' Class for managing COL matrix of tiles '''

    def __init__(self, tile_width, tile_height, remote=False):
        # The tiles in your hand
        self.hand = []
        self.remote = remote  # Does this hand belong to someone remote?

        for i in range(COL):
            self.hand.append(None)

        # Tile spacing
        self.xinc = int(tile_width)
        if self.remote:
            self.left = -self.xinc
        else:
            self.left = int(tile_width / 2)
        self.top = 0
        self.yinc = int(tile_height)

    def clear(self):
        for i in range(COL):
            self.hand[i] = None

    def deal(self, deck, number=COL):
        ''' Deal an initial set of tiles to the hand '''
        for i in range(number):
            self.hand[i] = deck.deal_next_tile()
            if self.hand[i] is not None:
                self.hand[i].spr.move(self.hand_to_xy(i))
                self.hand[i].spr.set_layer(TILES)
        return True

    def find_empty_slot(self):
        ''' Is there an empty slot in the hand? '''
        for i in range(COL):
            if self.hand[i] == None:
                return i
        return None

    def tiles_in_hand(self):
        ''' How many tiles are in the hand? '''
        return COL - self.hand.count(None)

    def serialize(self, buddy=None):
        ''' Serialize the hand for passing to share and saving '''
        if buddy == None:
            hand = []
        else:
            hand = [buddy]
        for i in range(COL):
            if self.hand[i] is not None:
                hand.append(self.hand[i].number)
            else:
                hand.append(None)
        return json_dump(hand)

    def restore(self, hand_as_text, deck, buddy=False):
        ''' Restore tiles to hand upon resume or share. '''
        hand = json_load(hand_as_text)
        print 'restoring hand'
        if buddy:
            offset = 1  # skip the buddy
        else:
            offset = 0
        for tile in range(COL):
            i = tile + offset
            if hand[i] is None:
                self.hand[i] = None
            else:
                for k in range(ROW * COL):
                    if deck.tiles[k].number == hand[i]:
                        print k, '-->', tile
                        self.hand[tile] = deck.tiles[k]
                        self.hand[tile].spr.move(self.hand_to_xy(tile))
                        self.hand[tile].spr.set_layer(TILES)
                        break

    def xy_to_hand(self, x, y):
        ''' Convert from sprite x,y to hand index. '''
        if x < self.left + self.xinc:
            return int((y - self.top) / self.yinc)
        else:
            return None

    def hand_to_xy(self, i):
        ''' Convert from hand index to sprite x,y. '''
        return ((self.left, (self.top + i * self.yinc)))

    def hand_to_spr(self, i):
        ''' Return the sprite in hand-position i. '''
        return self.hand[i].spr

    def spr_to_hand(self, spr):
        ''' Return the index of a sprite in hand. '''
        for i in range(COL):
            if self.hand[i] is not None and self.hand[i].spr == spr:
                return(i)
        return None
