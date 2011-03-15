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
from hand import Hand
from deck import Deck
from card import error_card, highlight_cards
from sprites import Sprites

ROW = 8
COL = 8
N = 0
E = N + 1
S = E + 1
W = S + 1
OFFSETS = [-COL, 1, COL, -1]
CARD_WIDTH = 55
CARD_HEIGHT = 55
HIDE = 0
BOARD = 1
GRID = 2
CARDS = 3
OVERLAY = 4
MY_HAND = 0
ROBOT_HAND = 1

class Game():

    def __init__(self, canvas, parent=None, colors=['#A0FFA0', '#FF8080']):
        self.activity = parent
        self.colors = colors

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
        self.height = gtk.gdk.screen_height() - (GRID_CELL_SIZE * 1.5)

        self.scale = self.height / (8.0 * CARD_HEIGHT)
        self.card_width = CARD_WIDTH * self.scale
        self.card_height = CARD_HEIGHT * self.scale
        self.sprites = Sprites(self.canvas)

        self.there_are_errors = False
        self.errormsg = []

        self.grid = Grid(self.sprites, self.width, self.height,
                         self.card_width, self.card_height, self.scale,
                         colors[0])
        self.deck = Deck(self.sprites, self.scale, colors[1])
        self.deck.board.move((self.grid.left, self.grid.top))
        self.deck.hide()

        self.hands = []
        self.hands.append(Hand(self.card_width, self.card_height))
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

        self.buddies = []

    def new_game(self, saved_state=None, deck_index=0):
        ''' Start a new game. '''

        # If there is already a deck, hide it.
        if hasattr(self, 'deck'):
            self.deck.hide()

        # Shuffle the deck and deal a hand of tiles.
        self.grid.clear()
        self.deck.clear()
        self.show_connected_tiles()
        self.deck.shuffle()
        for hand in self.hands:
            hand.clear()
        self.hands[MY_HAND].deal(self.deck)
        if self.playing_with_robot:
            if len(self.hands) < ROBOT_HAND + 1:
                self.hands.append(Hand(self.card_width, self.card_height,
                                       remote=True))
            self.hands[ROBOT_HAND].deal(self.deck)
        self.press = None
        self.release = None
        self.placed_a_tile = None
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

        # Ignore clicks on background.
        if spr is None or \
           spr in self.grid.blanks or \
           spr == self.deck.board:
            if self.placed_a_tile and spr is None:
                if self.playing_with_robot:
                    self._robot_play()
                    self.show_connected_tiles()
                    if self.hands[MY_HAND].cards_in_hand() == 0:
                        for hand in self.hands:
                            hand.deal(self.deck)
                    if self.playing_with_robot and self.sugar:
                        self.activity.status.set_label(_('It is your turn.'))
                self.placed_a_tile = False
            return True

        # Are we clicking on a tile in the hand?
        if self.hands[MY_HAND].spr_to_hand(spr) is not None and \
           not self.there_are_errors:
            self.last_spr_moved = spr
            if self.sugar:
                clicked_in_hand = True
                if self.placed_a_tile:
                    if self.playing_with_robot:
                        self._robot_play()
                        if self.hands[MY_HAND].cards_in_hand() == 0:
                            for hand in self.hands:
                                hand.deal(self.deck)
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
            i = self.hands[MY_HAND].find_empty_slot()
            if i is not None: 
                card = self.deck.spr_to_card(self.press)

                card.spr.move(self.hands[MY_HAND].hand_to_xy(i))
                if self.hands[MY_HAND].spr_to_hand(self.press) is not None:
                    self.hands[MY_HAND].hand[
                        self.hands[MY_HAND].spr_to_hand(self.press)] = None
                elif self.grid.spr_to_grid(self.press) is not None:
                    self.grid.grid[self.grid.spr_to_grid(self.press)] = None
                self.hands[MY_HAND].hand[i] = card
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

            i = self.hands[MY_HAND].spr_to_hand(self.press)
            if i is not None:
                self.hands[MY_HAND].hand[i] = None

            if self.last_spr_moved != card.spr:
                self.last_spr_moved = card.spr
            self._show_highlight()
        self._test_for_bad_paths(self.grid.spr_to_grid(self.press))
        if not self.there_are_errors:
            self._test_for_complete_paths(self.grid.spr_to_grid(self.press))
        self.press = None
        self.release = None
        self.show_connected_tiles()

        if self.hands[MY_HAND].cards_in_hand() == 0 and \
           not self.playing_with_robot:
            self.hands[MY_HAND].deal(self.deck)
        return True

    def _game_over(self, msg=_('Game over')):
        if self.sugar:
            self.activity.status.set_label(msg)
            self.activity.robot_button.set_icon('robot-off')

    def show_connected_tiles(self):
        ''' Highlight the squares that surround the tiles already on the grid.
        '''
        for i in range(ROW * COL):
            if self._connected(i):
                self.grid.blanks[i].set_layer(GRID)
            else:
                self.grid.blanks[i].set_layer(HIDE)

    def _connected(self, tile):
        ''' Does tile abut the path? '''
        if self.grid.grid.count(None) == ROW * COL:
            return True
        if self.grid.grid[tile] is not None:  # already has a tile
            return False
        if tile > COL and self.grid.grid[tile + OFFSETS[0]] is not None:
            return True
        if tile % ROW < ROW - 1 and \
           self.grid.grid[tile + OFFSETS[1]] is not None:
            return True
        if tile < (ROW - 1) * COL and \
           self.grid.grid[tile + OFFSETS[2]] is not None:
            return True
        if tile % ROW > 0 and self.grid.grid[tile + OFFSETS[3]] is not None:
            return True

    def _robot_play(self):
        ''' The robot tries random cards in random locations. '''
        # TODO: try to complete paths
        order = self.deck.random_order(ROW * COL)
        for i in range(ROW * COL):
            if self._connected(order[i]):
                for tile in self.hands[ROBOT_HAND].hand:
                    if self._try_placement(tile, order[i]):
                        # Success, so remove tile from hand.
                        self.hands[ROBOT_HAND].hand[
                            self.hands[ROBOT_HAND].hand.index(tile)] = None
                        tile.spr.move(self.grid.grid_to_xy(order[i]))
                        tile.spr.set_layer(CARDS)
                        return

        # If we didn't return above, we were unable to play a tile.
        if self.sugar:
            self.activity.set_robot_status(False, 'robot-off')
        # At the end of the game, show any tiles remaining in the robot's hand.
        for i in range(COL):
            if self.hands[ROBOT_HAND].hand[i] is not None:
                x, y = self.hands[ROBOT_HAND].hand_to_xy(i)
                self.hands[ROBOT_HAND].hand[i].spr.move(
                    (self.grid.left_hand + self.grid.xinc, y))
        self._game_over(_('Robot unable to play'))

    def _try_placement(self, tile, i):
        ''' Try to place a tile at grid posiion i. Rotate it, if necessary. '''
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

    def _test_for_complete_paths(self, tile):
        ''' Did this tile complete a path? (or two paths?) '''

        # A tile can complete up to two paths.
        self._paths = [[], []]
        break_in_path = [False, False]

        # Seed the paths and lists with the current tile.
        if tile is not None:
            self._add_to_path_list(tile, 0, 0)
            if len(self.grid.grid[tile].paths) == 2:
                self._add_to_path_list(tile, 1, 1)

        # Walk the path.
        for p in range(2):
            tile, path = self._tile_to_test(p)
            while(tile is not None):
                self._test(tile, path, p, self._test_a_neighbor)
                self._tile_has_been_tested(tile, path, p)
                tile, path = self._tile_to_test(p)
            # Is the path complete?
            for i in self._paths[p]:
                if not self._test(i[0], i[1], None, self._test_a_connection):
                    break_in_path[p] = True
            if not break_in_path[p] and len(self._paths[p]) > 0:
                # TODO: Change the color of path 0 vs 1
                for i in self._paths[p]:
                    self.grid.grid[i[0]].set_shape(i[1])

    def _tile_to_test(self, test_path):
        ''' Find a tile that needs testing. '''
        for i in self._paths[test_path]:
            if i[2] is False:
                return i[0], i[1]
        return None, None

    def _add_to_path_list(self, tile, tile_path, test_path):
        ''' Only add a tile to the path if it is not already there. '''
        for i in self._paths[test_path]:
            if i[0] == tile and i[1] == tile_path:
                return
        self._paths[test_path].append([tile, tile_path, False])

    def _tile_has_been_tested(self, tile, tile_path, test_path):
        ''' Mark a tile as tested. '''
        for i in self._paths[test_path]:
            if i[0] == tile and i[1] == tile_path:
                i[2] = True
                return

    def _test(self, tile, tile_path, test_path, test):
        ''' Test each neighbor of a block for a connecting path. '''
        if tile is None:
            return False
        for i in range(4):
            if not test(tile, tile_path, test_path, i, tile + OFFSETS[i]):
                return False
        return True

    def _test_a_connection(self, tile, tile_path, test_path, direction,
                           neighbor):
        ''' Is there a break in the connection? If so return False. '''
        if self.grid.grid[tile].paths[tile_path][direction] == 1:
            if self.grid.grid[neighbor] is None:
                return False
            # Which of the neighbor's paths are we connecting to?
            if len(self.grid.grid[neighbor].paths) == 1:
                if self.grid.grid[neighbor].paths[0][(direction + 2) % 4] == 0:
                    return False
                else:
                    return True
            if self.grid.grid[neighbor].paths[0][(direction + 2) % 4] == 0 and \
               self.grid.grid[neighbor].paths[1][(direction + 2) % 4] == 0:
                return False
        return True

    def _test_a_neighbor(self, tile, tile_path, test_path, direction,
                         neighbor):
        ''' Are we connected to a neighbor's path? If so, add the neighbor
        to our paths list and to the list of tiles that need to be tested. '''
        if self.grid.grid[tile].paths[tile_path][direction] == 1:
            if self.grid.grid[neighbor] is not None:
                if not neighbor in self._paths[test_path]:
                    # Which of the neighbor's paths are we connecting to?
                    if self.grid.grid[neighbor].paths[0][
                        (direction + 2) % 4] == 1:
                        self._add_to_path_list(neighbor, 0, test_path)
                    elif len(self.grid.grid[neighbor].paths) == 2 and \
                         self.grid.grid[neighbor].paths[1][
                        (direction + 2) % 4] == 1:
                        self._add_to_path_list(neighbor, 1, test_path)
                    else:
                        print 'You should never see this message.'
        return True

    def _test_for_bad_paths(self, tile):
        ''' Is there a path to nowhere? '''
        self._hide_errormsgs()
        self.there_are_errors = False
        if tile is not None:
            self._check_card(tile, [int(tile / COL), 0], N, tile + OFFSETS[0])
            self._check_card(tile, [tile % ROW, ROW - 1], E, tile + OFFSETS[1])
            self._check_card(tile, [int(tile / COL), COL - 1], S,
                             tile + OFFSETS[2])
            self._check_card(tile, [tile % ROW, 0], W, tile + OFFSETS[3])

    def _check_card(self, i, edge_check, direction, neighbor):
        ''' Can a card be placed at position i? '''
        if edge_check[0] == edge_check[1]:
            for path in self.grid.grid[i].paths:
                if path[direction] == 1:
                    self._display_errormsg(i, direction)
        else:
            if self.grid.grid[neighbor] is not None:
                my_path = 0
                your_path = 0
                for c in self.grid.grid[i].paths:
                    if c[direction] == 1:
                        my_path = 1
                for c in self.grid.grid[neighbor].paths:
                    if c[(direction + 2) % 4] == 1:
                        your_path = 1
                if my_path != your_path:
                    self._display_errormsg(i, direction)

    def _display_errormsg(self, i, direction):
        ''' Display an error message where and when appropriate. '''
        if self.press is not None:
            dxdy = [[0.375, -0.125], [0.875, 0.375], [0.375, 0.875],
                    [-0.125, 0.375]]
            x, y = self.press.get_xy()
            self.errormsg[direction].move(
                (x + dxdy[direction][0] * self.card_width,
                 y + dxdy[direction][1] * self.card_height))
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
