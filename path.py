#!/usr/bin/env python

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

import gtk

import gettextutil
import os

from game import Game


class PathMain:
    def __init__(self):
        self.r = 0

        # create a new window
        self.win = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.win.maximize()
        self.win.set_title("%s: %s" % (_("Paths"),
                           _("Move tiles to make a path.")))
        self.win.connect("delete_event", lambda w,e: gtk.main_quit())

        # A vbox to put a menu and the canvas in
        vbox = gtk.VBox(False, 0)
        self.win.add(vbox)
        vbox.show()

        canvas = gtk.DrawingArea()
        vbox.pack_end(canvas, True, True)
        canvas.show()

        self.win.show_all()

        # Join the activity
        self.vmw = Game(canvas)
        self.vmw.win = self.win
        self.vmw.activity = self
        self.vmw.level = 12

        self.vmw.new_game()

    def set_title(self, title):
        self.win.set_title(title)

    def _new_game_cb(self, widget, game):
        self.vmw.new_game()
        return True


def main():
    gtk.main()
    return 0

if __name__ == "__main__":
    PathMain()
    main()
