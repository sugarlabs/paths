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

from tile import Tile, board_card
from genpieces import generate_tile_1_line, generate_tile_2_lines
from utils import json_dump, json_load
from constants import HIDE, BOARD, ROW, COL


class Deck:
    ''' Class for defining deck of tiles. '''

    def __init__(self, sprites, scale=1.0, color='#000000'):
        ''' Create the deck of tiles. '''
        self.tiles = []
        i = 0
        for a in range(16):
            self.tiles.append(Tile(sprites,
                generate_tile_1_line(-1, 0, 0, 0, scale),
                [generate_tile_1_line(-1, 0, 0, 0, scale, color)], number=i))
            self.tiles[-1].set_paths([[0, 0, 0, 1]])
            i += 1
        for a in range(4):
            self.tiles.append(Tile(sprites,
                generate_tile_1_line(-1, 0, 1, 0, scale),
                [generate_tile_1_line(-1, 0, 1, 0, scale, color)], number=i))
            self.tiles[-1].set_paths([[0, 1, 0, 1]])
            i += 1
        for a in range(12):
            self.tiles.append(Tile(sprites,
                generate_tile_2_lines(-1, 0, 1, 0, 0, 0, 0, 1, scale),
                [generate_tile_2_lines(-1, 0, 1, 0, 0, 0, 0, 1, scale,
                                        [color, color])], number=i))
            self.tiles[-1].set_paths([[0, 1, 1, 1]])
            self.tiles[-1].set_value(2)
            i += 1
        for a in range(16):
            self.tiles.append(Tile(sprites,
                generate_tile_2_lines(-1, 0, 0, 0, 0, -1, 0, 0, scale),
                [generate_tile_2_lines(-1, 0, 0, 0, 0, -1, 0, 0, scale,
                                        [color, color])], number=i))
            self.tiles[-1].set_paths([[1, 0, 0, 1]])
            i += 1
        for a in range(4):
            self.tiles.append(Tile(sprites,
                generate_tile_2_lines(-1, 0, 1, 0, 0, -1, 0, 1, scale),
                [generate_tile_2_lines(-1, 0, 1, 0, 0, -1, 0, 1, scale,
                                        [color, color])], number=i))
            self.tiles[-1].set_paths([[1, 1, 1, 1]])
            self.tiles[-1].set_value(4)
            i += 1
        for a in range(8):
            self.tiles.append(Tile(sprites,
                generate_tile_2_lines(0, -1, 1, 0, -1, 0, 0, 1, scale),
                [generate_tile_2_lines(0, -1, 1, 0, -1, 0, 0, 1, scale,
                                       [color, '#000000']),
                 generate_tile_2_lines(0, -1, 1, 0, -1, 0, 0, 1, scale,
                                       ['#000000', color]),
                 generate_tile_2_lines(0, -1, 1, 0, -1, 0, 0, 1, scale,
                                       [color, color])], number=i))
            self.tiles[-1].set_paths([[1, 1, 0, 0], [0, 0, 1, 1]])
            self.tiles[-1].set_value(4)
            i += 1
        for a in range(4):
            self.tiles.append(Tile(sprites,
                generate_tile_2_lines(0, -1, 1, 0, -1, 0, 0, 0, scale),
                [generate_tile_2_lines(0, -1, 1, 0, -1, 0, 0, 0, scale,
                                       [color, '#000000']),
                 generate_tile_2_lines(0, -1, 1, 0, -1, 0, 0, 0, scale,
                                       ['#000000', color]),
                 generate_tile_2_lines(0, -1, 1, 0, -1, 0, 0, 0, scale,
                                       [color, color])], number=i))
            self.tiles[-1].set_paths([[1, 1, 0, 0], [0, 0, 0, 1]])
            self.tiles[-1].set_value(3)
            i += 1

        # Remember the current position in the deck.
        self.index = 0

        # And a playing surface
        self.board = board_card(sprites, scale=scale)
        self.board.set_layer(BOARD)

    def shuffle(self):
        ''' Shuffle the deck (Knuth algorithm). '''
        decksize = self.count()
        # Hide all the tiles and make sure they are back to orientation 0
        for tile in self.tiles:
            tile.reset()
        # Randomize the tile order.
        for n in range(decksize):
            i = randrange(decksize - n)
            self.swap_tiles(n, decksize - 1 - i)
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
            order.append(self.tiles[i].number)
        return json_dump(order)

    def restore(self, deck_as_text):
        ''' Restore the deck upon resume. '''
        deck = []
        order = json_load(deck_as_text)
        for i in order:
            # deck.append(self.tiles[order[i]])
            deck.append(self.tiles[i])
        self.tiles = deck[:]
        print 'restoring deck'
        for i in range(COL * ROW):
            print self.tiles[i].number

    def clear(self):
        ''' Remove any highlight from the tiles. '''
        for tile in self.tiles:
            tile.reset()

    def swap_tiles(self, i, j):
        ''' Swap the position of two tiles in the deck. '''
        tmp = self.tiles[j]
        self.tiles[j] = self.tiles[i]
        self.tiles[i] = tmp
        return

    def spr_to_tile(self, spr):
        ''' Given a sprite, find the corresponding tile in the deck. '''
        for tile in self.tiles:
            if tile.spr == spr:
                return tile
        return None

    def index_to_tile(self, i):
        ''' Given a tile index, find the corresponding tile in the deck. '''
        for tile in self.tiles:
            if tile.index == i:
                return tile
        return None

    def deal_next_tile(self):
        ''' Return the next tile from the deck. '''
        if self.empty():
            return None
        next_tile = self.tiles[self.index]
        self.index += 1
        return next_tile

    def empty(self):
        ''' Is the deck empty? '''
        if self.tiles_remaining() > 0:
            return False
        else:
            return True

    def tiles_remaining(self):
        ''' Return how many tiles are remaining in the deck. '''
        return(self.count() - self.index)

    def hide(self):
        ''' Hide the deck. '''
        for tile in self.tiles:
            if tile is not None:
                tile.hide()

    def count(self):
        ''' Return the length of the deck. '''
        return len(self.tiles)
