# -*- coding: utf-8 -*-
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
from gettext import gettext as _
import logging
_logger = logging.getLogger('paths-activity')

try:
    from sugar.graphics import style
    GRID_CELL_SIZE = style.GRID_CELL_SIZE
except ImportError:
    GRID_CELL_SIZE = 0

from grid import Grid
from deck import Deck
from card import error_card, highlight_cards
from sprites import Sprites

N = 0
E = N + 1
S = E + 1
W = S + 1
CARD_WIDTH = 55
CARD_HEIGHT = 55
ROW = 8
COL = 8
HIDE = 0
BOARD = 1
GRID = 2
CARDS = 3
OVERLAY = 4

class Game():

    def __init__(self, canvas, parent=None):
        self.activity = parent

        # Starting from command line
        if parent is None:
            self.sugar = False
            self.canvas = canvas
        else:
            self.sugar = True
            self.canvas = canvas
            parent.show_all()

        self.canvas.set_flags(gtk.CAN_FOCUS)
        self.canvas.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self.canvas.add_events(gtk.gdk.BUTTON_RELEASE_MASK)
        self.canvas.connect("expose-event", self._expose_cb)
        self.canvas.connect("button-press-event", self._button_press_cb)
        self.canvas.connect("button-release-event", self._button_release_cb)
        self.canvas.connect("key_press_event", self._keypress_cb)
        self.width = gtk.gdk.screen_width()
        self.height = gtk.gdk.screen_height()-GRID_CELL_SIZE

        self.scale = self.height / (8.0 * CARD_HEIGHT)
        self.card_width = CARD_WIDTH * self.scale
        self.card_height = CARD_HEIGHT * self.scale
        self.sprites = Sprites(self.canvas)

        self.there_are_errors = False
        self.errormsg = []

        self.grid = Grid(self.sprites, self.width, self.height,
                         self.card_width, self.card_height, self.scale)
        self.deck = Deck(self.sprites, self.scale)
        self.deck.board.spr.move((self.grid.left, self.grid.top))
        self.deck.hide()

        for i in range(4):
            self.errormsg.append(error_card(self.sprites))
        self._hide_errormsgs()

        self.highlight = highlight_cards(self.sprites, self.scale)
        self._hide_highlight()

        self.press = None
        self.release = None
        self.last_spr_moved = None

        self.playing_with_robot = False
        self.placed_a_tile = False

    def new_game(self, saved_state=None, deck_index=0):
        ''' Start a new game. '''

        # If there is already a deck, hide it.
        if hasattr(self, 'deck'):
            self.deck.hide()

        # Shuffle the deck and deal a hand of tiles.
        if self.playing_with_robot:
            self.grid.set_robot_status(True)
        else:
            self.grid.set_robot_status(False)
        self.grid.clear()
        self._show_connected_tiles()
        self.deck.shuffle()
        self.grid.deal(self.deck)
        self.last_spr_moved = None
        self._hide_highlight()
        self._hide_errormsgs()

    def _button_press_cb(self, win, event):
        win.grab_focus()
        x, y = map(int, event.get_coords())
        self.start_drag = [x, y]

        spr = self.sprites.find_sprite((x, y))
        self.press = None
        self.release = None

        # Ignore clicks on background
        if spr is None or \
           spr in self.grid.blanks or \
           spr == self.deck.board.spr:
            if self.placed_a_tile and spr is None:
                if self.playing_with_robot:
                    if self.sugar:
                        self.activity.status.set_label(
                            _('The robot is taking a turn.'))
                        self._robot_play()
                        self._show_connected_tiles()
                        if self.grid.cards_in_hand() == 0:
                            self.grid.redeal(self.deck)
                    if self.playing_with_robot and self.sugar:
                        self.activity.status.set_label(_('It is your turn.'))
                self.placed_a_tile = False
            return True

        # Are we clicking on a tile in the hand?
        if self.grid.spr_to_hand(spr) is not None and \
           not self.there_are_errors:
            self.last_spr_moved = spr
            if self.sugar:
                clicked_in_hand = True
                if self.placed_a_tile:
                    if self.playing_with_robot:
                        if self.sugar:
                            self.activity.status.set_label(
                                _('The robot taking a turn.'))
                            self._robot_play()
                            if self.grid.cards_in_hand() == 0:
                                self.grid.redeal(self.deck)
                self.placed_a_tile = False
        else:
            clicked_in_hand = False

        # We cannot switch to an old tile.
        if spr == self.last_spr_moved:
            self.press = spr

        self._show_highlight()
        return True

    def _button_release_cb(self, win, event):
        win.grab_focus()

        if self.press is None:
            return

        x, y = map(int, event.get_coords())
        spr = self.sprites.find_sprite((x, y))

        if spr is None:  # Returning tile to hand
            i = self.grid.find_empty_slot()
            if i is not None: 
                card = self.deck.spr_to_card(self.press)
                card.spr.move(self.grid.hand_to_xy(i))
                if self.grid.spr_to_hand(self.press) is not None:
                    self.grid.hand[self.grid.spr_to_hand(self.press)] = None
                elif self.grid.spr_to_grid(self.press) is not None:
                    self.grid.grid[self.grid.spr_to_grid(self.press)] = None
                self.grid.hand[i] = card
                if spr == self.last_spr_moved:
                    self.last_spr_moved = None
                    self._hide_highlight()
            self._hide_errormsgs()
            self._there_are_errors = False
            self.press = None
            self.release = None
            self.placed_a_tile = False
            return True

        self.release = spr
        if self.press == self.release:
            card = self.deck.spr_to_card(spr)
            card.rotate_clockwise()
            if self.last_spr_moved != card.spr:
                self.last_spr_moved = card.spr
            self._show_highlight()

        elif self.release in self.grid.blanks:
            card = self.deck.spr_to_card(self.press)
            card.spr.move(self.grid.grid_to_xy(self.grid.xy_to_grid(x, y)))
            i = self.grid.spr_to_grid(self.press)
            if i is not None:
                self.grid.grid[i] = None
                
            self.grid.grid[self.grid.xy_to_grid(x, y)] = card
            self.placed_a_tile = True

            i = self.grid.spr_to_hand(self.press)
            if i is not None:
                self.grid.hand[i] = None

            if self.last_spr_moved != card.spr:
                self.last_spr_moved = card.spr
            self._show_highlight()
        self._test_for_bad_paths(self.grid.spr_to_grid(self.press))
        self.press = None
        self.release = None
        self._show_connected_tiles()

        if self.grid.cards_in_hand() == 0 and not self.playing_with_robot:
            self.grid.redeal(self.deck)
        return True

    def _game_over(self, msg=_('Game over')):
        if self.sugar:
            self.activity.status.set_label(msg)
            self.activity.robot_button.set_icon('robot-off')

    def _show_connected_tiles(self):
        ''' Highlight the tiles that surround the tiles on the grid '''
        for i in range(64):
            if self._connected(i):
                self.grid.blanks[i].set_layer(GRID)
            else:
                self.grid.blanks[i].set_layer(HIDE)

    def _connected(self, i):
        ''' Does grid position i abut the path? '''
        if self.grid.grid.count(None) == ROW * COL:
            return True
        if self.grid.grid[i] is not None: # already has a tile
            return False
        if i > COL and self.grid.grid[i - COL] is not None:
            return True
        if i < (ROW - 1) * COL and self.grid.grid[i + COL] is not None:
            return True
        if i % ROW > 0 and self.grid.grid[i -1] is not None:
            return True
        if i % ROW < ROW - 1 and self.grid.grid[i + 1] is not None:
            return True

    def _robot_play(self):
        ''' robot tries random cards in random locations '''
        order = self.deck.random_order(ROW * COL)
        for i in range(ROW * COL):
            if self._connected(order[i]):
                for tile in self.grid.robot_hand:
                    if self._try_placement(tile, order[i]):
                        # Success, so remove tile from hand
                        self.grid.robot_hand[
                            self.grid.robot_hand.index(tile)] = None
                        print order[i], self.grid.grid_to_xy(order[i])
                        tile.spr.move(self.grid.grid_to_xy(order[i]))
                        tile.spr.set_layer(CARDS)
                        return
        self.playing_with_robot = False
        self.grid.set_robot_status(False)
        self._game_over(_('Robot unable to play'))

    def _try_placement(self, tile, i):
        if tile is None:
            return False
        self.grid.grid[i] = tile
        for j in range(4):
            self._test_for_bad_paths(i)
            if not self.there_are_errors:
                return True
            tile.rotate_clockwise()
        self.grid.grid[i] = None
        return False

    def _test_for_bad_paths(self, tile):
        ''' Is there a path to no where? '''
        self._hide_errormsgs()
        self.there_are_errors = False
        if tile is not None:
            self._check_north(tile)
            self._check_east(tile)
            self._check_south(tile)
            self._check_west(tile)

    def _check_north(self, i):
        # Is it in the top row?
        if int(i / COL) == 0:
            if self.grid.grid[i].connections[N] == 1:
                self._display_errormsg(i, N)
        else:
            if self.grid.grid[i-COL] is not None:
                if self.grid.grid[i].connections[N] != \
                   self.grid.grid[i-COL].connections[S]:
                    self._display_errormsg(i, N)

    def _check_east(self, i):
        # Is it in the right column?
        if int(i % ROW) == ROW - 1:
            if self.grid.grid[i].connections[E] == 1:
                self._display_errormsg(i, E)
        else:
            if self.grid.grid[i+1] is not None:
                if self.grid.grid[i].connections[E] != \
                   self.grid.grid[i+1].connections[W]:
                    self._display_errormsg(i, E)

    def _check_south(self, i):
        # Is it in the bottom row?
        if int(i / COL) == COL - 1:
            if self.grid.grid[i].connections[S] == 1:
                self._display_errormsg(i, S)
        else:
            if self.grid.grid[i+COL] is not None:
                if self.grid.grid[i].connections[S] != \
                   self.grid.grid[i+COL].connections[N]:
                    self._display_errormsg(i, S)

    def _check_west(self, i):
        # Is it in the left column?
        if int(i % ROW) == 0:
            if self.grid.grid[i].connections[W] == 1:
                self._display_errormsg(i, W)
        else:
            if self.grid.grid[i-1] is not None:
                if self.grid.grid[i].connections[W] != \
                   self.grid.grid[i-1].connections[E]:
                    self._display_errormsg(i, W)

    def _display_errormsg(self, i, direction):
        ''' Display an error message where and when appropriate. '''
        if self.press is not None:
            offsets = [[0.375, -0.125], [0.875, 0.375], [0.375, 0.875],
                       [-0.125, 0.375]]
            x, y = self.press.get_xy()
            self.errormsg[direction].move(
                (x + offsets[direction][0] * self.card_width,
                 y + offsets[direction][1] * self.card_height))
            self.errormsg[direction].set_layer(OVERLAY)
        self.there_are_errors = True

    def _hide_errormsgs(self):
        ''' Hide all the error messages. '''
        for i in range(4):
            self.errormsg[i].move((self.grid.left, self.grid.top))
            self.errormsg[i].set_layer(HIDE)

    def _hide_highlight(self):
        ''' No tile is selected. '''
        for i in range(4):
            self.highlight[i].set_layer(HIDE)

    def _show_highlight(self):
        ''' Highlight the tile that is selected. '''
        if self.last_spr_moved is None:
            self._hide_highlight()
        else:
            x, y = self.last_spr_moved.get_xy()
            self.highlight[0].move((x, y))
            self.highlight[1].move((x + 7 * self.card_width / 8, y))
            self.highlight[2].move((x + 7 * self.card_width / 8,
                                    y + 7 * self.card_height / 8))
            self.highlight[3].move((x, y + 7 * self.card_height / 8))
            for i in range(4):
                self.highlight[i].set_layer(OVERLAY)

    def _keypress_cb(self, area, event):
        return True

    def _expose_cb(self, win, event):
        self.sprites.redraw_sprites()
        return True

    def _destroy_cb(self, win, event):
        gtk.main_quit()
