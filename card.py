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
from sprites import Sprite

N = 0
E = N + 1
S = E + 1
W = S + 1
CARDS = 3


class Card:

    def __init__(self, sprites, svg, svgs, card_type='tile', number=0):
        self.spr = Sprite(sprites, 0, 0, svg_str_to_pixbuf(svg))
        self.highlight = []
        for s in svgs:
            self.highlight.append(svg_str_to_pixbuf(s))
        self.paths = []  # [[N, E, S, W], [N, E, S, W]]
        self.shape = None
        self.orientation = 0
        self.type = card_type
        self.number = number

    def set_paths(self, paths):
        for c in paths:
            self.paths.append(c)

    def get_paths(self):
        return self.paths

    def set_shape(self, path):
        if self.shape is None:
            self.spr.set_shape(self.highlight[path])
            self.shape = path
        elif self.shape != path:
            self.spr.set_shape(self.highlight[-1])

    def rotate_clockwise(self):
        """ rotate the card and its paths """
        for i in range(len(self.paths)):
            west = self.paths[i][W]
            self.paths[i][W] = self.paths[i][S]
            self.paths[i][S] = self.paths[i][E]
            self.paths[i][E] = self.paths[i][N]
            self.paths[i][N] = west
        self.spr.images[0] = self.spr.images[0].rotate_simple(270)
        for h in range(len(self.highlight)):
            self.highlight[h] = self.highlight[h].rotate_simple(270)
        self.spr.draw()
        self.orientation += 90
        self.orientation %= 360

    def show_card(self):
        self.spr.set_layer(CARDS)
        self.spr.draw()

    def hide_card(self):
        self.spr.hide()


#
# Load pixbuf from SVG string
#
def svg_str_to_pixbuf(svg_string):
    pl = gtk.gdk.PixbufLoader('svg')
    pl.write(svg_string)
    pl.close()
    pixbuf = pl.get_pixbuf()
    return pixbuf

#
# Create graphics used for interactions
#
from genpieces import generate_board, generate_x, generate_blank, \
    generate_corners

def board_card(sprites, scale=1.0):
    return Sprite(sprites, 0, 0, svg_str_to_pixbuf(generate_board(scale)))

def error_card(sprites, scale=1.0):
    return Sprite(sprites, 0, 0, svg_str_to_pixbuf(generate_x(0.5 * scale)))

def blank_card(sprites, scale=1.0, color='#80FF80'):
    return Sprite(sprites, 0, 0, svg_str_to_pixbuf(
            generate_blank(scale, color)))

def highlight_cards(sprites, scale=1.0):
    return [Sprite(sprites, 0, 0, svg_str_to_pixbuf(
                generate_corners(0, 0.125 * scale))),
            Sprite(sprites, 0, 0, svg_str_to_pixbuf(
                generate_corners(1, 0.125 * scale))),
            Sprite(sprites, 0, 0, svg_str_to_pixbuf(
                generate_corners(2, 0.125 * scale))),
            Sprite(sprites, 0, 0, svg_str_to_pixbuf(
                generate_corners(3, 0.125 * scale)))]
