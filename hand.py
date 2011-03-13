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
CARDS = 3


class Hand:
    ''' Class for managing COL matrix of cards '''

    def __init__(self, card_width, card_height, robot=False):
        # the tiles in your hand        
        self.hand = []
        self.robot = robot  # Does this hand belong to the robot?

        for i in range(COL):
            self.hand.append(None)

        # card spacing
        self.xinc = int(card_width)
        if self.robot:
            self.left = -self.xinc
        else:
            self.left = int(card_width / 2)
        self.top = 0
        self.yinc = int(card_height)
        print 'hand: left = %d, top = %d' % (self.left, self.top)

    def clear(self):
        for i in range(COL):
            self.hand[i] = None

    def deal(self, deck):
        ''' Deal an initial set of cards to the hand '''
        for i in range(COL):
            self.hand[i] = deck.deal_next_card()
            self.hand[i].spr.move(self.hand_to_xy(i))
            self.hand[i].spr.set_layer(CARDS)

    def find_empty_slot(self):
        ''' Is there an empty slot in the hand? '''
        for i in range(COL):
            if self.hand[i] == None:
                return i
        return None

    def cards_in_hand(self):
        ''' How many cards are in the hand? '''
        return COL - self.hand.count(None)

    def serialize(self):
        ''' Serialize the hand for passing to share and saving '''
        hand = []
        for i in range( COL):
            if self.hand[i] is not None:
                hand.append(self.hand[i].number)
            else:
                hand.append(None)
        return json_dump(hand)

    def restore(self, hand_as_text, deck):
        ''' Restore cards to hand upon resume or share. '''
        hand = json_load(hand_as_text)
        for i in range(COL):
            if hand[i] is None:
                self.hand[i] = None
            else:
                for k in range(ROW * COL):
                    if deck.cards[k].number == hand[i]:
                        self.hand[i] = deck.cards[k]
                        self.hand[i].spr.move(self.hand_to_xy(i))
                        self.hand[i].spr.set_layer(CARDS)
                        break

    def xy_to_hand(self, x, y):
        ''' Convert from sprite x,y to hand index. '''
        return int((y - self.top) / self.yinc)

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
