#!/usr/bin/env python
# -*- coding: utf-8 -*-

#Copyright (c) 2009,10 Walter Bender

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

import os

#
# SVG generators
#
class SVG:
    def __init__(self):
        self._scale = 1
        self._stroke_width = 1
        self._fill = '#FFFFFF'
        self._stroke = '#000000'

    def _svg_style(self, extras=""):
        return "%s%s%s%s%s%f%s%s%s" % ("style=\"fill:", self._fill, ";stroke:",
                                       self._stroke, ";stroke-width:",
                                       self._stroke_width, ";", extras,
                                       "\" />\n")

    def _svg_line(self, x1, y1, x2, y2):
        svg_string = "<line x1=\"%f\" y1=\"%f\" x2=\"%f\" y2=\"%f\"\n" % \
                      (x1, y1, x2, y2)
        svg_string += self._svg_style("stroke-linecap:square;")
        return svg_string

    def _svg_rect(self, w, h, rx, ry, x, y):
        svg_string = "       <rect\n"
        svg_string += "          width=\"%f\"\n" % (w)
        svg_string += "          height=\"%f\"\n" % (h)
        svg_string += "          rx=\"%f\"\n" % (rx)
        svg_string += "          ry=\"%f\"\n" % (ry)
        svg_string += "          x=\"%f\"\n" % (x)
        svg_string += "          y=\"%f\"\n" % (y)
        self.set_stroke_width(1.0)
        svg_string += self._svg_style()
        return svg_string

    def _svg_x(self, w, h):
        self.set_stroke_width(10.0)
        svg_string = self._svg_line(0, 0, w, h)
        svg_string += self._svg_line(0, h, w, 0)
        return svg_string

    def _svg_corners(self, which_corner, w, h):
        self.set_stroke_width(50.0)
        if which_corner == 0:
            svg_string = self._svg_line(0, 0, w, 0)
            svg_string += self._svg_line(0, 0, 0, h)
        elif which_corner == 1:
            svg_string = self._svg_line(0, 0, w, 0)
            svg_string += self._svg_line(w, 0, w, h)
        elif which_corner == 2:
            svg_string = self._svg_line(w, 0, w, h)
            svg_string += self._svg_line(0, h, w, h)
        else:
            svg_string = self._svg_line(0, h, w, h)
            svg_string += self._svg_line(0, 0, 0, h)
        return svg_string

    def _background(self, scale):
        return self._svg_rect(54.5 * scale, 54.5 * scale, 4, 4, 0.25, 0.25)

    def header(self, scale=1, background=True):
        svg_string = "<?xml version=\"1.0\" encoding=\"UTF-8\""
        svg_string += " standalone=\"no\"?>\n"
        svg_string += "<!-- Created with Emacs -->\n"
        svg_string += "<svg\n"
        svg_string += "   xmlns:svg=\"http://www.w3.org/2000/svg\"\n"
        svg_string += "   xmlns=\"http://www.w3.org/2000/svg\"\n"
        svg_string += "   version=\"1.0\"\n"
        svg_string += "%s%f%s" % ("   width=\"", scale * 55 * self._scale,
                                  "\"\n")
        svg_string += "%s%f%s" % ("   height=\"", scale * 55 * self._scale,
                                  "\">\n")
        svg_string += "%s%f%s%f%s" % ("<g\n       transform=\"matrix(", 
                                      self._scale, ",0,0,", self._scale,
                                      ",0,0)\">\n")
        if background:
            svg_string += self._background(scale)
        return svg_string

    def footer(self):
        svg_string = "</g>\n"
        svg_string += "</svg>\n"
        return svg_string

    #
    # Utility functions
    #
    def set_scale(self, scale=1.0):
        self._scale = scale

    def set_colors(self, colors):
        self._stroke = colors[0]
        self._fill = colors[1]

    def set_stroke_width(self, stroke_width=1.0):
        self._stroke_width = stroke_width

    #
    # Card pattern generators
    #

    def path(self, a, b, c, d):
        x1 = a * 27.5 + 27.5
        y1 = b * 27.5 + 27.5
        x2 = c * 27.5 + 27.5
        y2 = d * 27.5 + 27.5
        self.set_stroke_width(10)
        svg_string = self._svg_line(x1, y1, x2, y2)
        return svg_string

#
# Card generators
#
def generate_x(scale=1):
    svg = SVG()
    svg.set_scale(scale)
    svg.set_colors(["#FF0000", "#FF0000"])
    svg_string = svg.header(background=False)
    svg_string += svg._svg_x(55, 55)
    svg_string += svg.footer()
    return svg_string

def generate_corners(which_corner=0, scale=1):
    svg = SVG()
    svg.set_scale(scale)
    svg.set_colors(["#0000FF", "#0000FF"])
    svg_string = svg.header(background=False)
    svg_string += svg._svg_corners(which_corner, 55, 55)
    svg_string += svg.footer()
    return svg_string

def generate_blank(scale=1, color='#A0FFA0'):
    svg = SVG()
    svg.set_scale(scale)
    svg.set_colors([color, color])
    svg_string = svg.header()
    svg_string += svg.footer()
    return svg_string

def generate_board(scale=1, color='#000000'):
    svg = SVG()
    svg.set_scale(scale)
    svg.set_colors([color, '#FFFFFF'])
    svg_string = svg.header(scale=8)  # board is 8x8 tiles
    svg_string += svg.footer()
    return svg_string

def generate_tile_1_line(a, b, c, d, scale=1, color='#000000'):
    svg = SVG()
    svg.set_scale(scale)
    svg.set_colors([color, '#FFFFFF'])
    svg_string = svg.header()
    svg_string += svg.path(a, b, c, d)
    svg_string += svg.footer()
    return svg_string

def generate_tile_2_lines(a, b, c, d, e, f, g, h, scale=1, color='#000000'):
    svg = SVG()
    svg.set_scale(scale)
    svg.set_colors([color, '#FFFFFF'])
    svg_string = svg.header()
    svg_string += svg.path(a, b, c, d)
    svg_string += svg.path(e, f, g, h)
    svg_string += svg.footer()
    return svg_string

#
# Command line utilities used for testing purposed only
#
def open_file(datapath, filename):
    return file(os.path.join(datapath, filename), "w")

def close_file(f):
    f.close()

def generator(datapath):
    i = 0
    filename = "tile-%d.svg" % (i)
    f = open_file(datapath, filename)
    f.write(generate_tile_1_line(-1, 0, 0, 0))
    close_file(f)
    i += 1
    filename = "tile-%d.svg" % (i)
    f = open_file(datapath, filename)
    f.write(generate_tile_1_line(-1, 0, 1, 0))
    i += 1
    close_file(f)
    filename = "tile-%d.svg" % (i)
    f = open_file(datapath, filename)
    f.write(generate_tile_2_lines(-1, 0, 1, 0, 0, 0, 0, 1))
    i += 1
    close_file(f)
    filename = "tile-%d.svg" % (i)
    f = open_file(datapath, filename)
    f.write(generate_tile_2_lines(-1, 0, 0, 0, 0, -1, 0, 0))
    i += 1
    close_file(f)
    filename = "tile-%d.svg" % (i)
    f = open_file(datapath, filename)
    f.write(generate_tile_2_lines(-1, 0, 1, 0, 0, -1, 0, 1))
    i += 1
    close_file(f)
    filename = "tile-%d.svg" % (i)
    f = open_file(datapath, filename)
    f.write(generate_tile_2_lines(-1, 0, 0, 1, 0, -1, 1, 0))
    i += 1
    close_file(f)
    filename = "tile-%d.svg" % (i)
    f = open_file(datapath, filename)
    f.write(generate_tile_2_lines(-1, 0, 0, 0, 0, -1, 1, 0))
    i += 1
    close_file(f)
    f = open_file(datapath, 'x.svg')
    f.write(generate_x())
    i += 1
    close_file(f)
    f = open_file(datapath, 'blank.svg')
    f.write(generate_blank())
    i += 1
    close_file(f)
    f = open_file(datapath, 'corners.svg')
    f.write(generate_corners())
    i += 1
    close_file(f)
    f = open_file(datapath, 'board.svg')
    f.write(generate_board())
    i += 1
    close_file(f)

def main():
    return 0

if __name__ == "__main__":
    if not os.path.exists(os.path.join(os.path.abspath('.'), 'images')):
        os.mkdir(os.path.join(os.path.abspath('.'), 'images'))
    generator(os.path.join(os.path.abspath('.'), 'images'))
    main()
