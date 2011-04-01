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
import gobject
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
from tile import error_graphic, highlight_graphic
from utils import json_dump
from constants import ROW, COL, NORTH, EAST, SOUTH, WEST, TILE_WIDTH, \
    TILE_HEIGHT, HIDE, BOARD, GRID, TILES, TOP, OVER_THE_TOP
from sprites import Sprites

OFFSETS = [-COL, 1, COL, -1]
MY_HAND = 0
ROBOT_HAND = 1


class Game():

    def __init__(self, canvas, parent=None, colors=['#A0FFA0', '#FF8080']):
        self._activity = parent
        self.colors = colors

        # Starting from command line
        if parent is None:
            self._running_sugar = False
            self._canvas = canvas
        else:
            self._running_sugar = True
            self._canvas = canvas
            parent.show_all()

        self._canvas.set_flags(gtk.CAN_FOCUS)
        self._canvas.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self._canvas.add_events(gtk.gdk.BUTTON_RELEASE_MASK)
        self._canvas.add_events(gtk.gdk.POINTER_MOTION_MASK)
        self._canvas.connect("expose-event", self._expose_cb)
        self._canvas.connect("button-press-event", self._button_press_cb)
        self._canvas.connect("button-release-event", self._button_release_cb)
        self._canvas.connect("motion-notify-event", self._mouse_move_cb)
        self._canvas.connect("key_press_event", self._keypress_cb)

        self._width = gtk.gdk.screen_width()
        self._height = gtk.gdk.screen_height() - (GRID_CELL_SIZE * 1.5)
        self._scale = self._height / (8.0 * TILE_HEIGHT)
        self.tile_width = TILE_WIDTH * self._scale
        self.tile_height = TILE_HEIGHT * self._scale

        # Generate the sprites we'll need...
        self._sprites = Sprites(self._canvas)
        self.grid = Grid(self._sprites, self._width, self._height,
                         self.tile_width, self.tile_height, self._scale,
                         colors[0])
        self.deck = Deck(self._sprites, self._scale, colors[1])
        self.deck.board.move((self.grid.left, self.grid.top))
        self.hands = []
        self.hands.append(Hand(self.tile_width, self.tile_height))
        self._errormsg = []
        for i in range(4):
            self._errormsg.append(error_graphic(self._sprites))
        self._highlight = highlight_graphic(self._sprites, self._scale)

        # and initialize a few variables we'll need.
        self.buddies = []
        self._my_hand = MY_HAND
        self.playing_with_robot = False
        self._all_clear()

    def _all_clear(self):
        ''' Things to reinitialize when starting up a new game. '''
        self._hide_highlight()
        self._hide_errormsgs()
        self.deck.hide()
        self.deck.clear()
        self.grid.clear()
        for hand in self.hands:
            hand.clear()
        self.show_connected_tiles()

        self._press = None
        self._release = None
        self._dragpos = [0, 0]
        self._total_drag = [0, 0]
        self.last_spr_moved = None
        self._last_tile_played = None
        self._last_tile_orientation = 0
        self._last_grid_played = None

        self.whos_turn = MY_HAND
        self._waiting_for_my_turn = False
        self._waiting_for_robot = False
        self.placed_a_tile = False
        self._there_are_errors = False

        self.score = 0

    def _initiating(self):
        if not self._running_sugar:
            return True
        return self._activity.initiating

    def new_game(self, saved_state=None, deck_index=0):
        ''' Start a new game. '''
        self._all_clear()

        # If we are not sharing or we are the sharer...
        if not self.we_are_sharing() or self._initiating():
            # Let joiners know we are starting a new game...
            if self.we_are_sharing():
                self._activity.send_event('n| ')

            # The initiator shuffles the deck...
            self.deck.shuffle()
            # ...and shares it.
            if self.we_are_sharing():
                self._activity.send_event('d|%s' % (self.deck.serialize()))

            # Deal a hand to yourself...
            self.hands[self._my_hand].deal(self.deck)

            # ...deal a hand to the robot...
            if self.playing_with_robot:
                if len(self.hands) < ROBOT_HAND + 1:
                    self.hands.append(Hand(self.tile_width, self.tile_height,
                                           remote=True))
                self.hands[ROBOT_HAND].deal(self.deck)
            # ...or deal hands to the joiners.
            elif len(self.buddies) > 1:
                for i, buddy in enumerate(self.buddies):
                    if buddy != self._activity.nick:
                        self.hands.append(Hand(
                            self.tile_width, self.tile_height, remote=True))
                        self.hands[i].deal(self.deck)
                        self._activity.send_event('h|%s' % \
                            (self.hands[i].serialize(buddy=buddy)))

            # As initiator, you take the first turn.
            self.its_my_turn()

        # If we are joining, we need to wait for a hand.
        else:
            self._my_hand = self.buddies.index(self._activity.nick)
            self.its_their_turn(self.buddies[1])  # Sharer will be buddy 1

    def we_are_sharing(self):
        ''' If we are sharing, there is more than one buddy. '''
        if len(self.buddies) > 1:
            return True

    def _set_label(self, string):
        ''' Set the label in the toolbar or the window frame. '''
        if self._running_sugar:
            self._activity.status.set_label(string)
            self._activity.score.set_label(_('Score: ') + str(self.score))
        elif hasattr(self, 'win'):
            self.win.set_title('%s: %s [%d]' % (_('Paths'), string,
                                                self.score))

    def its_my_turn(self):
        # I need to play a piece...
        self.placed_a_tile = False
        # and I am no longer waiting for my turn.
        self._waiting_for_my_turn = False
        # If I don't have any tiles left, time to redeal.
        if self.hands[self._my_hand].tiles_in_hand() == 0:
            self._redeal()
        if self._running_sugar:
            self._activity.set_player_on_toolbar(self._activity.nick)
            self._activity.dialog_button.set_icon('go-next')
            self._activity.dialog_button.set_tooltip(
                _('Click after taking your turn.'))
        self._set_label(_('It is your turn.'))

    def _redeal(self):
        # Only the sharer deals tiles.
        if not self.we_are_sharing():
            self.hands[self._my_hand].deal(self.deck)
            if self.playing_with_robot:
                self.hands[ROBOT_HAND].deal(self.deck)
            if self.hands[self._my_hand].tiles_in_hand() == 0:
                if self._running_sugar:
                    self._activity.dialog_button.set_icon(
                        'media-playback-stop-insensitive')
                    self._activity.dialog_button.set_tooltip(_('Game over'))
                self._set_label(_('Game over'))

        elif self._initiating():
            if self.deck.empty():
                self._set_label(_('Game over'))
                return
            if self.deck.tiles_remaining() < COL * len(self.buddies):
                number_of_tiles_to_deal = \
                    int(self.deck.tiles_remaining() / len(self.buddies))
                if number_of_tiles_to_deal == 0:
                    number_of_tiles_to_deal = 1  # Deal last tile in deck.
            else:
                number_of_tiles_to_deal = COL
            for i, nick in enumerate(self.buddies):
                self.hands[i].deal(self.deck, number_of_tiles_to_deal)
                # Send the joiners their new hands.
                if nick != self._activity.nick:
                    self._activity.send_event('h|%s' % \
                        (self.hands[i].serialize(buddy=nick)))

    def took_my_turn(self):
        # Did I complete my turn without any errors?
        if self._there_are_errors:
            self._set_label(_('There are errors—it is still your turn.'))
            return

        # After the tile is placed, expand regions of playable grid squares.
        self.show_connected_tiles()

        # Are there any completed paths?
        self._test_for_complete_paths(self._last_grid_played)

        # If so, let everyone know what piece I moved.
        if self.we_are_sharing():
            self._activity.send_event('p|%s' % \
                (json_dump([self._last_tile_played,
                                 self._last_tile_orientation,
                                 self._last_grid_played])))
            self._last_tile_orientation = 0  # Reset orientation.
        # I took my turn, so I am waiting again.
        self._waiting_for_my_turn = True
        if self.last_spr_moved is not None:
            self.last_spr_moved.set_layer(TILES)
            self.last_spr_moved = None
        self._hide_highlight()
        self._set_label(_('You took your turn.'))

        if self.playing_with_robot:
            self.its_their_turn(_('robot'))
            self._waiting_for_robot = True
            gobject.timeout_add(1000, self._robot_turn)
        elif not self.we_are_sharing():
            self.its_my_turn()
        elif self._initiating():
            self.whos_turn += 1
            if self.whos_turn == len(self.buddies):
                self.whos_turn = 0
            else:
                self.its_their_turn(self.buddies[self.whos_turn])
                self._activity.send_event('t|%s' % (
                    self.buddies[self.whos_turn]))

    def _robot_turn(self):
        self._robot_play()
        self.show_connected_tiles()
        if not self._waiting_for_robot:
            self.its_my_turn()

    def its_their_turn(self, nick):
        # It is someone else's turn.
        if self._running_sugar:
            if not self.playing_with_robot:
                self._activity.set_player_on_toolbar(nick)
            self._activity.dialog_button.set_icon('media-playback-stop')
            self._activity.dialog_button.set_tooltip(_('Wait your turn.'))
        self._set_label(_('Waiting for') + ' ' + nick)
        self._waiting_for_my_turn = True  # I am still waiting.

    def _button_press_cb(self, win, event):
        win.grab_focus()
        x, y = map(int, event.get_coords())

        self._dragpos = [x, y]
        self._total_drag = [0, 0]

        spr = self._sprites.find_sprite((x, y))

        # If it is not my turn, do nothing.
        if self._waiting_for_my_turn:
            self._press = None
            return

        self._release = None

        # Ignore clicks on background except to indicate you took your turn
        if spr is None or spr in self.grid.blanks or spr == self.deck.board:
            if self.placed_a_tile and spr is None:
                self.took_my_turn()
                self._press = None
            return True

        # Are we clicking on a tile in the hand?
        if self.hands[self._my_hand].spr_to_hand(spr) is not None and \
           not self._there_are_errors:
            self.last_spr_moved = spr
            clicked_in_hand = True
            if self.placed_a_tile:
                self._press = None
                self.took_my_turn()
        else:
            clicked_in_hand = False

        # We cannot switch to an old tile.
        if spr == self.last_spr_moved:
            self._press = spr

        spr.set_layer(TOP)
        self._show_highlight()
        return True

    def _mouse_move_cb(self, win, event):
        """ Drag a tile with the mouse. """
        spr = self._press
        if spr is None:
            self._dragpos = [0, 0]
            return True
        win.grab_focus()
        x, y = map(int, event.get_coords())
        dx = x - self._dragpos[0]
        dy = y - self._dragpos[1]
        spr.move_relative([dx, dy])
        self._move_relative_highlight([dx, dy])
        self._dragpos = [x, y]
        self._total_drag[0] += dx
        self._total_drag[1] += dy

    def _button_release_cb(self, win, event):
        win.grab_focus()

        self._dragpos = [0, 0]

        if self._waiting_for_my_turn:
            return

        if self._press is None:
            return

        x, y = map(int, event.get_coords())
        spr = self._sprites.find_sprite((x, y))
        self._release = spr
        grid_pos = self.grid.xy_to_grid(x, y)
        hand_pos = self.hands[self._my_hand].xy_to_hand(x, y)

        # Placing tile in grid
        if grid_pos is not None and self._it_is_a_drag():
            if self.grid.grid[grid_pos] is None:
                tile = self.deck.spr_to_tile(self._press)
                tile.spr.move(self.grid.grid_to_xy(grid_pos))
                i = self.grid.spr_to_grid(self._press)
                if i is not None:
                    self.grid.grid[i] = None

                self.grid.grid[grid_pos] = tile
                self.placed_a_tile = True
                self._last_tile_played = tile.number
                self._last_grid_played = grid_pos

                i = self.hands[self._my_hand].spr_to_hand(self._press)
                if i is not None:
                    self.hands[self._my_hand].hand[i] = None

                if self.last_spr_moved != tile.spr:
                    self.last_spr_moved = tile.spr

                self._show_highlight()
        # Returning tile to hand
        elif hand_pos is not None:
            i = self.hands[self._my_hand].find_empty_slot()
            if i is not None:
                tile = self.deck.spr_to_tile(self._press)
                tile.spr.move(self.hands[self._my_hand].hand_to_xy(i))
                if self.hands[self._my_hand].spr_to_hand(
                    self._press) is not None:
                    self.hands[self._my_hand].hand[
                        self.hands[self._my_hand].spr_to_hand(
                            self._press)] = None
                elif self.grid.spr_to_grid(self._press) is not None:
                    self.grid.grid[self.grid.spr_to_grid(self._press)] = None
                self.hands[self._my_hand].hand[i] = tile
                if spr == self.last_spr_moved:
                    self.last_spr_moved = None
                self._hide_errormsgs()
                self._there_are_errors = False
            else:  # Or return tile to the grid
                grid_pos = self.grid.spr_to_grid(self._press)
                if grid_pos is not None:
                    tile = self.deck.spr_to_tile(self._press)
                    tile.spr.move(self.grid.grid_to_xy(grid_pos))
            self._hide_highlight()
            self._press = None
            self._release = None
            self.placed_a_tile = False
            return True
        # Rotate
        elif self._press == self._release and not self._it_is_a_drag():
            tile = self.deck.spr_to_tile(spr)
            tile.rotate_clockwise()
            self._last_tile_orientation = tile.orientation
            # Reset position if there was a short drag while rotating.
            # tile.spr.move_relative((-self._total_drag[0], -self._total_drag[1]))
            if self.last_spr_moved != tile.spr:
                self.last_spr_moved = tile.spr
            self._show_highlight()

        if hand_pos is None and x < self.grid.left:  # In limbo: return to grid
            grid_pos = self.grid.spr_to_grid(self._press)
            if grid_pos is not None:
                tile = self.deck.spr_to_tile(self._press)
                tile.spr.move(self.grid.grid_to_xy(grid_pos))
                self._hide_highlight()

        self._snap_to_grid(self._release)
        self._test_for_bad_paths(self.grid.spr_to_grid(self._press))
        self._press = None
        self._release = None
        return True

    def _snap_to_grid(self, spr):
        ''' make sure a tile is aligned in its grid position '''
        for i in range(COL * ROW):
            if self.grid.grid[i] is not None:
                self.grid.grid[i].spr.move(self.grid.grid_to_xy(i))
                if self.grid.grid[i].spr == spr:
                    self._move_highlight(self.grid.grid_to_xy(i))

    def _it_is_a_drag(self):
        if self._total_drag[0] * self._total_drag[0] + \
           self._total_drag[1] * self._total_drag[1] > \
           self.tile_width * self.tile_height:
            return True
        return False

    def _game_over(self, msg=_('Game over')):
        self._set_label(msg)
        if self._running_sugar:
            self._activity.robot_button.set_icon('robot-off')

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

    def give_a_hint(self):
        ''' Try to find an open place on the grid for any tile in my_hand. '''
        order = self.deck.random_order(ROW * COL)
        for i in range(ROW * COL):
            if self._connected(order[i]):
                for tile in self.hands[self._my_hand].hand:
                    if self._try_placement(tile, order[i]):
                        # Success, so give hint.
                        self.grid.grid[order[i]] = None
                        self._show_highlight(
                            pos=self.grid.grid_to_xy(order[i]))
                        return
        # Nowhere to play.
        self._set_label(_('Nowhere to play.'))

    def _robot_play(self):
        ''' The robot tries random tiles in random locations. '''
        # TODO: strategy try to complete paths
        order = self.deck.random_order(ROW * COL)
        for i in range(ROW * COL):
            if self._connected(order[i]):
                for tile in self.hands[ROBOT_HAND].hand:
                    if self._try_placement(tile, order[i]):
                        # Success, so remove tile from hand.
                        self.hands[ROBOT_HAND].hand[
                            self.hands[ROBOT_HAND].hand.index(tile)] = None
                        tile.spr.move(self.grid.grid_to_xy(order[i]))
                        tile.spr.set_layer(TILES)
                        self._waiting_for_robot = False
                        return

        # If we didn't return above, we were unable to play a tile.
        if self._running_sugar:
            self._activity.set_robot_status(False, 'robot-off')
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
            if not self._there_are_errors:
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
                for i in self._paths[p]:
                    self.grid.grid[i[0]].set_shape(i[1])
                    self.score += self.grid.grid[i[0]].get_value()

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
            if self.grid.grid[neighbor].paths[0][(direction + 2) % 4] == 0 and\
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
        return True

    def _test_for_bad_paths(self, tile):
        ''' Is there a path to nowhere? '''
        self._hide_errormsgs()
        self._there_are_errors = False
        if tile is not None:
            self._check_tile(tile, [int(tile / COL), 0], NORTH,
                             tile + OFFSETS[0])
            self._check_tile(tile, [tile % ROW, ROW - 1], EAST,
                             tile + OFFSETS[1])
            self._check_tile(tile, [int(tile / COL), COL - 1], SOUTH,
                             tile + OFFSETS[2])
            self._check_tile(tile, [tile % ROW, 0], WEST, tile + OFFSETS[3])

    def _check_tile(self, i, edge_check, direction, neighbor):
        ''' Can a tile be placed at position i? '''
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
        if self._press is not None:
            dxdy = [[0.375, -0.125], [0.875, 0.375], [0.375, 0.875],
                    [-0.125, 0.375]]
            x, y = self._press.get_xy()
            self._errormsg[direction].move(
                (x + dxdy[direction][0] * self.tile_width,
                 y + dxdy[direction][1] * self.tile_height))
            self._errormsg[direction].set_layer(OVER_THE_TOP)
        self._there_are_errors = True

    def _hide_errormsgs(self):
        ''' Hide all the error messages. '''
        for i in range(4):
            self._errormsg[i].move((self.grid.left, self.grid.top))
            self._errormsg[i].set_layer(HIDE)

    def _hide_highlight(self):
        ''' No tile is selected. '''
        for i in range(4):
            self._highlight[i].move((self.grid.left, self.grid.top))
            self._highlight[i].set_layer(HIDE)

    def _move_relative_highlight(self, pos):
            for i in range(4):
                self._highlight[i].move_relative(pos)

    def _move_highlight(self, pos):
        x, y = pos
        self._highlight[0].move((x, y))
        self._highlight[1].move((x + 7 * self.tile_width / 8, y))
        self._highlight[2].move((x + 7 * self.tile_width / 8,
                                 y + 7 * self.tile_height / 8))
        self._highlight[3].move((x, y + 7 * self.tile_height / 8))

    def _show_highlight(self, pos=None):
        ''' Highlight the tile that is selected. '''
        if self.last_spr_moved is None and pos is None:
            self._hide_highlight()
        else:
            if pos is None:
                x, y = self.last_spr_moved.get_xy()
            else:  # Giving a hint.
                x, y = pos
            self._move_highlight((x, y))
            for i in range(4):
                self._highlight[i].set_layer(OVER_THE_TOP)

    def _keypress_cb(self, area, event):
        return True

    def _expose_cb(self, win, event):
        self._sprites.redraw_sprites()
        return True

    def _destroy_cb(self, win, event):
        gtk.main_quit()
