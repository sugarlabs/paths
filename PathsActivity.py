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
import gobject

import sugar
from sugar.activity import activity
try:
    from sugar.graphics.toolbarbox import ToolbarBox
    _have_toolbox = True
except ImportError:
    _have_toolbox = False

if _have_toolbox:
    from sugar.bundle.activitybundle import ActivityBundle
    from sugar.activity.widgets import ActivityToolbarButton
    from sugar.activity.widgets import StopButton
    from sugar.graphics.toolbarbox import ToolbarButton

from sugar.graphics.toolbutton import ToolButton
from sugar.graphics.menuitem import MenuItem
from sugar.graphics.icon import Icon
from sugar.datastore import datastore

from gettext import gettext as _
import locale
import os.path

from game import Game

SERVICE = 'org.sugarlabs.PathsActivity'
IFACE = SERVICE
PATH = '/org/augarlabs/PathsActivity'


def _button_factory(icon_name, tooltip, callback, toolbar, cb_arg=None,
                    accelerator=None):
    """Factory for making toolbar buttons"""
    my_button = ToolButton(icon_name)
    my_button.set_tooltip(tooltip)
    my_button.props.sensitive = True
    if accelerator is not None:
        my_button.props.accelerator = accelerator
    if cb_arg is not None:
        my_button.connect('clicked', callback, cb_arg)
    else:
        my_button.connect('clicked', callback)
    if hasattr(toolbar, 'insert'):  # the main toolbar
        toolbar.insert(my_button, -1)
    else:  # or a secondary toolbar
        toolbar.props.page.insert(my_button, -1)
    my_button.show()
    return my_button


def _label_factory(label, toolbar):
    """ Factory for adding a label to a toolbar """
    my_label = gtk.Label(label)
    my_label.set_line_wrap(True)
    my_label.show()
    _toolitem = gtk.ToolItem()
    _toolitem.add(my_label)
    toolbar.insert(_toolitem, -1)
    _toolitem.show()
    return my_label


def _separator_factory(toolbar, visible=True, expand=False):
    """ Factory for adding a separator to a toolbar """
    _separator = gtk.SeparatorToolItem()
    _separator.props.draw = visible
    _separator.set_expand(expand)
    toolbar.insert(_separator, -1)
    _separator.show()


class PathsActivity(activity.Activity):
    """ Path puzzle game """

    def __init__(self, handle):
        """ Initialize the toolbars and the game board """
        super(PathsActivity,self).__init__(handle)

        self._setup_toolbars(_have_toolbox)

        # Create a canvas
        canvas = gtk.DrawingArea()
        canvas.set_size_request(gtk.gdk.screen_width(), \
                                gtk.gdk.screen_height())
        self.set_canvas(canvas)
        canvas.show()
        self.show_all()

        self.game = Game(canvas, self)

        # Restore game state from Journal or start new game
        if 'deck0' in self.metadata:
            self._restore()
        else:
            self.game.new_game()

    def _setup_toolbars(self, have_toolbox):
        """ Setup the toolbars.. """

        if have_toolbox:
            toolbox = ToolbarBox()

            # Activity toolbar
            activity_button = ActivityToolbarButton(self)

            toolbox.toolbar.insert(activity_button, 0)
            activity_button.show()

            self.set_toolbar_box(toolbox)
            toolbox.show()
            toolbar = toolbox.toolbar

        else:
            # Use pre-0.86 toolbar design
            games_toolbar = gtk.Toolbar()
            toolbox = activity.ActivityToolbox(self)
            self.set_toolbox(toolbox)
            toolbox.add_toolbar(_('Game'), games_toolbar)
            toolbox.show()
            toolbox.set_current_toolbar(1)
            toolbar = games_toolbar

        self.new_game_button = _button_factory('new-game',
                                               _('Start a new game.'),
                                               self.new_game_cb, toolbar)

        self.robot_button = _button_factory('robot-off',
                                            _('Play with the computer.'),
                                            self.robot_cb, toolbar)

        self.status = _label_factory('play on', toolbar)

        if _have_toolbox:
            _separator_factory(toolbox.toolbar, False, True)

            stop_button = StopButton(self)
            stop_button.props.accelerator = '<Ctrl>q'
            toolbox.toolbar.insert(stop_button, -1)
            stop_button.show()

    def new_game_cb(self, button=None):
        ''' Start a new game. '''
        self.game.new_game()

    def robot_cb(self, button=None):
        ''' Play with the computer (or not). '''
        if not self.game.playing_with_robot:
             self.game.playing_with_robot = True
             self.game.grid.set_robot_status(True)
             self.robot_button.set_icon('robot-on')
             self.game.new_game()
        else:
             self.game.playing_with_robot = False
             self.game.grid.set_robot_status(False)
             self.robot_button.set_icon('robot-off')
             self.game.new_game()

    def write_file(self, file_path):
        """ Write the grid status to the Journal """
        if not hasattr(self, 'game'):
            return
        for i in range(64):
            self.metadata['deck' + str(i)] = \
                str(self.game.deck.cards[i].number)
        for i in range(64):
            if self.game.grid.grid[i] is not None:
                self.metadata['grid' + str(i)] = \
                    str(self.game.grid.grid[i].number)
                self.metadata['rotate' + str(i)] = \
                    str(self.game.grid.grid[i].orientation)
            else:
                self.metadata['grid' + str(i)] = 'None'
        for i in range(8):
            if self.game.grid.hand[i] is not None:
                self.metadata['hand' + str(i)] = \
                    str(self.game.grid.hand[i].number)
            else:
                self.metadata['hand' + str(i)] = 'None'
        if self.game.last_spr_moved is not None and \
           self.game.grid.spr_to_grid(self.game.last_spr_moved) is not None:
            self.metadata['last'] = str(self.game.grid.grid[
                self.game.grid.spr_to_grid(self.game.last_spr_moved)].number)

    def _restore(self):
        """ Restore the game state from metadata """
        deck = []
        for i in range(64):
            if 'deck' + str(i) in self.metadata:
                deck.append(self.game.deck.cards[
                        int(self.metadata['deck' + str(i)])])
        if len(deck) == 64:  # We've retrieved an entire deck
            self.game.deck.cards = deck[:]
        for i in range(64):
            if 'grid' + str(i) in self.metadata:
                if self.metadata['grid' + str(i)] == 'None':
                    self.game.grid.grid[i] = None
                else:
                    j = int(self.metadata['grid' + str(i)])
                    for k in range(64):
                        if self.game.deck.cards[k].number == j:
                            self.game.grid.grid[i] = self.game.deck.cards[k]
                    self.game.grid.grid[i].spr.move(
                        self.game.grid.grid_to_xy(i))
                    self.game.grid.grid[i].spr.set_layer(2000)
                    if 'rotate' + str(i) in self.metadata:
                        o = int(self.metadata['rotate' + str(i)])
                        while o > 0:
                            self.game.grid.grid[i].rotate_clockwise()
                            o -= 90
            else:
                self.game.grid.grid[i] = None
        for i in range(8):
            if 'hand' + str(i) in self.metadata:
                if self.metadata['hand' + str(i)] == 'None':
                    self.game.grid.hand[i] = None
                else:
                    j = int(self.metadata['hand' + str(i)])
                    for k in range(64):
                        if self.game.deck.cards[k].number == j:
                            self.game.grid.hand[i] = self.game.deck.cards[k]
                    self.game.grid.hand[i].spr.move(
                        self.game.grid.hand_to_xy(i))
                    self.game.grid.hand[i].spr.set_layer(2000)
            else:
                self.game.grid.hand[i] = None
        self.game.deck.index = 64 - self.game.grid.grid.count(None) + \
                                8 - self.game.grid.hand.count(None)
        self.game.last_spr_moved = None
        if 'last' in self.metadata:
            j = int(self.metadata['last'])
            for k in range(64):
                if self.game.deck.cards[k].number == j:
                    self.game.last_spr_moved = self.game.deck.cards[k].spr
                    return
