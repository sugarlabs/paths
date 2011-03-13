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
from sugar import profile
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

from game import Game, CARDS
from hand import Hand

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
    toolitem = gtk.ToolItem()
    toolitem.add(my_label)
    toolbar.insert(toolitem, -1)
    toolitem.show()
    return my_label


def _separator_factory(toolbar, visible=True, expand=False):
    """ Factory for adding a separator to a toolbar """
    separator = gtk.SeparatorToolItem()
    separator.props.draw = visible
    separator.set_expand(expand)
    toolbar.insert(separator, -1)
    separator.show()


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

        self._game = Game(canvas,
                          parent=self,
                          colors= profile.get_color().to_string().split(','))

        # Restore game state from Journal or start new game
        if 'deck0' in self.metadata:
            self._restore()
        else:
            self._game.new_game()

    def _setup_toolbars(self, have_toolbox):
        """ Setup the toolbars.. """

        # no sharing
        self.max_participants = 1

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

            # no sharing
            if hasattr(toolbox, 'share'):
               toolbox.share.hide()
            elif hasattr(toolbox, 'props'):
               toolbox.props.visible = False

        self._new_game_button = _button_factory('new-game',
                                                _('Start a new game.'),
                                                self._new_game_cb, toolbar)

        self.robot_button = _button_factory('robot-off',
                                             _('Play with the computer.'),
                                             self._robot_cb, toolbar)

        self.status = _label_factory(_('It is your turn.'), toolbar)

        if _have_toolbox:
            _separator_factory(toolbox.toolbar, False, True)

            stop_button = StopButton(self)
            stop_button.props.accelerator = '<Ctrl>q'
            toolbox.toolbar.insert(stop_button, -1)
            stop_button.show()

    def _new_game_cb(self, button=None):
        ''' Start a new game. '''
        self._game.new_game()

    def _robot_cb(self, button=None):
        ''' Play with the computer (or not). '''
        print 'playing with robot:', self._game.playing_with_robot
        if not self._game.playing_with_robot:
            self.set_robot_status(True, 'robot-on')
            print 'starting new game with robot'
            self._game.new_game()
        else:
            self.set_robot_status(False, 'robot-off')
            print 'starting new game without robot'
            self._game.new_game()

    def set_robot_status(self, status, icon):
        ''' Reset robot icon and status '''
        self._game.playing_with_robot = status
        self.robot_button.set_icon(icon)

    def write_file(self, file_path):
        """ Write the grid status to the Journal """
        if not hasattr(self, '_game'):
            return
        self.metadata['deck'] = self._game.deck.serialize()
        self.metadata['grid'] = self._game.grid.serialize()
        for i, hand in enumerate(self._game.hands):
            self.metadata['hand-' + str(i)] = hand.serialize()
        if self._game.last_spr_moved is not None and \
           self._game.grid.spr_to_grid(self._game.last_spr_moved) is not None:
            self.metadata['last'] = str(self._game.grid.grid[
                self._game.grid.spr_to_grid(self._game.last_spr_moved)].number)

    def _restore(self):
        """ Restore the game state from metadata """
        if 'deck' in self.metadata:
            self._game.deck.restore(self.metadata['deck'])
        if 'grid' in self.metadata:
            self._game.grid.restore(self.metadata['grid'], self._game.deck)
        self._game.show_connected_tiles()

        for i in range(2):
            if 'hand-' + str(i) in self.metadata:
                if len(self._game.hands) < i + 1:  # Add robot hand?
                    self._game.hands.append(
                        Hand(self._game.card_width, self._game.card_height,
                             robot=True))
                self._game.hands[i].restore(self.metadata['hand-' + str(i)],
                                            self._game.deck)

        self._game.deck.index = 64 - self._game.grid.cards_in_grid()
        for h in self._game.hands:
            self._game.deck.index += (8 - h.cards_in_hand())

        self._game.last_spr_moved = None
        if 'last' in self.metadata:
            j = int(self.metadata['last'])
            for k in range(64):
                if self._game.deck.cards[k].number == j:
                    self._game.last_spr_moved = self._game.deck.cards[k].spr
                    return
