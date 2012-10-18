#Copyright (c) 2011 Walter Bender
# Port To GTK3:
# Ignacio Rodriguez <ignaciorodriguez@sugarlabs.org>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# You should have received a copy of the GNU General Public License
# along with this library; if not, write to the Free Software
# Foundation, 51 Franklin Street, Suite 500 Boston, MA 02110-1335 USA


from gi.repository import Gtk, Gdk, GdkPixbuf, GObject

from deck import Deck
from tile import blank_tile
from utils import json_dump, json_load
from constants import ROW, COL, GRID, TILES


class Grid:
    ''' Class for managing ROWxCOL matrix of tiles '''

    def __init__(self, sprites, width, height, tile_width, tile_height, scale,
                 color):
        # the playing surface
        self.grid = []
        self.blanks = []

        for i in range(ROW * COL):
            self.grid.append(None)

        # tile spacing
        self.left_hand = int(tile_width / 2)
        self.left = int((width - (tile_width * COL)) / 2 + tile_width)
        self.xinc = int(tile_width)
        self.top = 0
        self.yinc = int(tile_height)

        for i in range(ROW * COL):
            self.blanks.append(blank_tile(sprites, scale=scale, color=color))
            self.blanks[i].move(self.grid_to_xy(i))
            self.blanks[i].set_layer(GRID)

    def clear(self):
        for i in range(ROW * COL):
            self.grid[i] = None

    def tiles_in_grid(self):
        ''' How many tiles are on the grid? '''
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
        ''' Restore tiles to grid upon resume or share. '''
        self.hide()
        grid = json_load(grid_as_text)
        for i in range(ROW * COL):
            if grid[i][0] is None:
                self.grid[i] = None
            else:
                for k in range(ROW * COL):
                    if deck.tiles[k].number == grid[i][0]:
                        self.add_tile_to_grid(k, grid[i][1], i, deck)
                        break
        self.show()

    def add_tile_to_grid(self, tile_number, orientation, grid_number, deck):
        ''' Add tiles[tile_number] to grid[grid_number] at orientation '''
        self.grid[grid_number] = deck.tiles[tile_number]
        self.grid[grid_number].spr.move(self.grid_to_xy(grid_number))
        self.grid[grid_number].spr.set_layer(TILES)
        while orientation > 0:
            self.grid[grid_number].rotate_clockwise()
            orientation -= 90

    def place_a_tile(self, c, x, y):
        ''' Place a tile at position x,y and display it. '''
        if c is not None:
            c.spr.move((x, y))
            c.spr.set_layer(TILES)

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
        ''' Hide all of the tiles on the grid. '''
        for i in range(ROW * COL):
            if self.grid[i] is not None:
                self.grid[i].hide()

    def show(self):
        ''' Restore all tile on the grid to their x,y positions. '''
        for i in range(ROW * COL):
            self.place_a_tile(self.grid[i], self.grid_to_xy(i)[0],
                              self.grid_to_xy(i)[1])
