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


from gi.repository import Gdk, Gtk
from constants import NORTH, EAST, SOUTH, WEST, HIDE, TILES
from sprites import Sprite
from utils import svg_str_to_pixbuf


class Tile:

    def __init__(self, sprites, svg, svgs, tile_type='tile', number=0):
        self.highlight = [svg_str_to_pixbuf(svg)]
        self.spr = Sprite(sprites, 0, 0, self.highlight[0])
        for s in svgs:
            self.highlight.append(svg_str_to_pixbuf(s))
        self.paths = []  # [[N, E, S, W], [N, E, S, W]]
        self.shape = None
        self.orientation = 0
        self.type = tile_type
        self.number = number
        self.value = 1
        self.spr.set_label_color('#FF0000')

    def set_value(self, value):
        self.value = value

    def get_value(self):
        return self.value

    def set_paths(self, paths):
        for c in paths:
            self.paths.append(c)

    def get_paths(self):
        return self.paths

    def reset(self):
        self.spr.set_layer(HIDE)
        self.shape = None
        self.spr.set_shape(self.highlight[0])
        while self.orientation != 0:
            self.rotate_clockwise()

    def set_shape(self, path):
        if self.shape is None:
            self.spr.set_shape(self.highlight[path + 1])
            self.shape = path
        elif self.shape != path:
            self.spr.set_shape(self.highlight[-1])

    def rotate_clockwise(self):
        """ rotate the tile and its paths """
        for i in range(len(self.paths)):
            west = self.paths[i][WEST]
            self.paths[i][WEST] = self.paths[i][SOUTH]
            self.paths[i][SOUTH] = self.paths[i][EAST]
            self.paths[i][EAST] = self.paths[i][NORTH]
            self.paths[i][NORTH] = west
        for h in range(len(self.highlight)):
            self.highlight[h] = self.highlight[h].rotate_simple(270)
        self.spr.set_shape(self.highlight[0])
        self.orientation += 90
        self.orientation %= 360

    def show_tile(self):
        self.spr.set_layer(CARDS)

    def hide(self):
        self.spr.move((-self.spr.get_dimensions()[0], 0))


#
# Utilities used to create graphics used for interactions
#
from genpieces import generate_board, generate_x, generate_blank, \
    generate_corners


def board_card(sprites, scale=1.0):
    return Sprite(sprites, 0, 0, svg_str_to_pixbuf(generate_board(scale)))


def error_graphic(sprites, scale=1.0):
    return Sprite(sprites, -100, 0, svg_str_to_pixbuf(generate_x(0.5 * scale)))


def blank_tile(sprites, scale=1.0, color='#80FF80'):
    return Sprite(sprites, 0, 0, svg_str_to_pixbuf(
            generate_blank(scale, color)))


def highlight_graphic(sprites, scale=1.0):
    return [Sprite(sprites, -100, 0, svg_str_to_pixbuf(
                generate_corners(0, 0.125 * scale))),
            Sprite(sprites, -100, 0, svg_str_to_pixbuf(
                generate_corners(1, 0.125 * scale))),
            Sprite(sprites, -100, 0, svg_str_to_pixbuf(
                generate_corners(2, 0.125 * scale))),
            Sprite(sprites, -100, 0, svg_str_to_pixbuf(
                generate_corners(3, 0.125 * scale)))]
