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
from utils import json_dump
from constants import ROW, COL, NORTH, EAST, SOUTH, WEST, CARD_WIDTH, \
    CARD_HEIGHT, HIDE, BOARD, GRID, CARDS, TOP, OVER_THE_TOP
from sprites import Sprites

OFFSETS = [-COL, 1, COL, -1]
MY_HAND = 0
ROBOT_HAND = 1


class Game():

    def __init__(self, canvas, parent=None, colors=['#A0FFA0', '#FF8080']):
        self.activity = parent
        self.colors = colors

        # Starting from command line
        if parent is None:
            self.running_sugar = False
            self.canvas = canvas
        else:
            self.running_sugar = True
            self.canvas = canvas
            parent.show_all()

        self.canvas.set_flags(gtk.CAN_FOCUS)
        self.canvas.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self.canvas.add_events(gtk.gdk.BUTTON_RELEASE_MASK)
        self.canvas.add_events(gtk.gdk.POINTER_MOTION_MASK)
        self.canvas.connect("expose-event", self._expose_cb)
        self.canvas.connect("button-press-event", self._button_press_cb)
        self.canvas.connect("button-release-event", self._button_release_cb)
        self.canvas.connect("motion-notify-event", self._mouse_move_cb)
        self.canvas.connect("key_press_event", self._keypress_cb)

        self.width = gtk.gdk.screen_width()
        self.height = gtk.gdk.screen_height() - (GRID_CELL_SIZE * 1.5)
        self.scale = self.height / (8.0 * CARD_HEIGHT)
        self.card_width = CARD_WIDTH * self.scale
        self.card_height = CARD_HEIGHT * self.scale

        # Generate the sprites we'll need...
        self.sprites = Sprites(self.canvas)
        self.grid = Grid(self.sprites, self.width, self.height,
                         self.card_width, self.card_height, self.scale,
                         colors[0])
        self.deck = Deck(self.sprites, self.scale, colors[1])
        self.deck.board.move((self.grid.left, self.grid.top))
        self.hands = []
        self.hands.append(Hand(self.card_width, self.card_height))
        self.errormsg = []
        for i in range(4):
            self.errormsg.append(error_card(self.sprites))
        self.highlight = highlight_cards(self.sprites, self.scale)

        # and initialize a few variables we'll need.
        self.buddies = []
        self.my_hand = MY_HAND
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

        self.press = None
        self.release = None
        self.dragpos = [0, 0]
        self.total_drag = [0, 0]
        self.last_spr_moved = None
        self.last_tile_played = None
        self.last_tile_orientation = 0
        self.last_grid_played = None

        self.whos_turn = MY_HAND
        self.waiting_for_my_turn = False
        self.waiting_for_robot = False
        self.placed_a_tile = False
        self.there_are_errors = False

    def new_game(self, saved_state=None, deck_index=0):
        ''' Start a new game. '''

        print 'starting new game'
        self._all_clear()

        # If we are not sharing or we are the sharer...
        if not self._we_are_sharing() or self.activity.initiating:
            if not self._we_are_sharing():
                print 'We are not sharing.'
            if not self.activity.initiating:
                print 'I am initiating.'
            # Let joiners know we are starting a new game...
            if self._we_are_sharing():
                print 'sending a new_game event'
                self.activity.send_event('n| ')

            # The initiator shuffles the deck...
            self.deck.shuffle()
            # ...and shares it.
            if self._we_are_sharing():
                print 'sending a new deck event'
                self.activity.send_event('d|%s' % (self.deck.serialize()))

            # Deal a hand to yourself...
            print 'dealing myself a hand'
            self.hands[self.my_hand].deal(self.deck)

            # ...deal a hand to the robot...
            if self.playing_with_robot:
                print 'dealing robot a hand'
                if len(self.hands) < ROBOT_HAND + 1:
                    self.hands.append(Hand(self.card_width, self.card_height,
                                           remote=True))
                self.hands[ROBOT_HAND].deal(self.deck)
            # ...or deal hands to the joiners.
            elif len(self.buddies) > 1:
                for i, buddy in enumerate(self.buddies):
                    if buddy != self.activity.nick:
                        self.hands.append(Hand(
                            self.card_width, self.card_height, remote=True))
                        self.hands[i].deal(self.deck)
                        print 'dealing %s a hand' % (buddy)
                        self.activity.send_event('h|%s' % \
                            (self.hands[i].serialize(buddy=buddy)))

            # As initiator, you take the first turn.
            self.its_my_turn()

        # If we are joining, we need to wait for a hand.
        else:
            self.my_hand = self.buddies.index(self.activity.nick)
            print 'Waiting for hand from the sharer and a turn to play.'
            self.its_their_turn(_('my turn'))

    def _we_are_sharing(self):
        ''' If we are sharing, there is more than one buddy. '''
        if len(self.buddies) > 1:
            return True

    def _set_label(self, string):
        ''' Set the label in the toolbar or the window frame. '''
        if self.running_sugar:
            self.activity.status.set_label(string)
        elif hasattr(self, 'win'):
            self.win.set_title('%s: %s' % (_('Paths'), string))

    def its_my_turn(self):
        print 'its my turn'
        # I need to play a piece...
        self.placed_a_tile = False
        # and I am no longer waiting for my turn.
        self.waiting_for_my_turn = False
        # If I don't have any tiles left, time to redeal.
        if self.hands[self.my_hand].cards_in_hand() == 0:
            self._redeal()
        if self.running_sugar:
            self.activity.dialog_button.set_icon('dialog-ok')
            self.activity.dialog_button.set_tooltip(
                _('Click after taking your turn.'))
        self._set_label(self.activity.nick + ': ' + _('It is my turn.'))

    def _redeal(self):
        # Only the sharer deals cards.
        if not self._we_are_sharing():
            self.hands[self.my_hand].deal(self.deck)
            if self.playing_with_robot:
                self.hands[ROBOT_HAND].deal(self.deck)
            if self.hands[self.my_hand].cards_in_hand() == 0:
                if self.running_sugar:
                    self.activity.dialog_button.set_icon('dialog-cancel')
                    self.activity.dialog_button.set_tooltip(_('Game over'))
                self._set_label(_('Game over'))
                
        elif self.activity.initiating:
            for i, buddy in enumerate(self.buddies):
                print 'dealing %s a hand' % (buddy)
                self.hands[i].deal(self.deck)
                # Send the joiners their new hands.
                if buddy != self.activity.nick:
                    self.activity.send_event('h|%s' % \
                        (self.hands[i].serialize(buddy=buddy)))

    def took_my_turn(self):
        # Did I complete my turn without any errors?
        if self.there_are_errors:
            self._set_label(_('There are errors -- still my turn.'))
            return

        # Are there any completed paths?
        print 'testing for completed tiles'
        # self._test_for_complete_paths(self.grid.spr_to_grid(self.press))
        self._test_for_complete_paths(self.last_grid_played)

        # If so, let everyone know what piece I moved.
        if self._we_are_sharing():
            self.activity.send_event('p|%s' % \
                (json_dump([self.last_tile_played,
                                 self.last_tile_orientation,
                                 self.last_grid_played])))
        # I took my turn, so I am waiting again.
        self.waiting_for_my_turn = True
        self.last_spr_moved.set_layer(CARDS)
        self._hide_highlight()
        print 'took my turn'
        self._set_label(_('I took my turn.'))
        if self.playing_with_robot:
            self.its_their_turn(_('robot'))
            self.waiting_for_robot = True
            self._robot_play()
            self.show_connected_tiles()

        # If the robot played or playing solitaire, go again.
        if self.playing_with_robot or not self._we_are_sharing():
            self.its_my_turn()

    def its_their_turn(self, nick):
        # It is someone else's turn.
        print 'waiting for ', nick
        if self.running_sugar:
            self.activity.dialog_button.set_icon('dialog-cancel')
            self.activity.dialog_button.set_tooltip(_('Wait your turn.'))
        self._set_label(_('Waiting for') + nick)

    def _button_press_cb(self, win, event):
        win.grab_focus()
        x, y = map(int, event.get_coords())

        self.dragpos = [x, y]
        self.total_drag = [0, 0]

        spr = self.sprites.find_sprite((x, y))

        # If it is not my turn, do nothing.
        if self.waiting_for_my_turn:
            print "Waiting for my turn -- ignoring button press."
            self.press = None
            return

        self.release = None

        # Ignore clicks on background except to indicate you took your turn
        if spr is None or \
           spr in self.grid.blanks or \
           spr == self.deck.board:
            if self.placed_a_tile and spr is None:
                print 'placed a tile and clicked on None'
                self.took_my_turn()
                self.press = None
            return True

        # Are we clicking on a tile in the hand?
        if self.hands[self.my_hand].spr_to_hand(spr) is not None and \
           not self.there_are_errors:
            self.last_spr_moved = spr
            clicked_in_hand = True
            if self.placed_a_tile:
                print 'placed a tile and clicked in hand'
                self.press = None
                self.took_my_turn()
        else:
            clicked_in_hand = False

        # We cannot switch to an old tile.
        if spr == self.last_spr_moved:
            self.press = spr

        spr.set_layer(TOP)
        self._show_highlight()
        return True

    def _mouse_move_cb(self, win, event):
        """ Drag a tile with the mouse. """
        spr = self.press
        if spr is None:
            self.dragpos = [0, 0]
            return True
        win.grab_focus()
        x, y = map(int, event.get_coords())
        dx = x - self.dragpos[0]
        dy = y - self.dragpos[1]
        spr.move_relative([dx, dy])
        self._move_highlight([dx, dy])
        self.dragpos = [x, y]
        self.total_drag[0] += dx
        self.total_drag[1] += dy

    def _button_release_cb(self, win, event):
        win.grab_focus()

        self.dragpos = [0, 0]

        if self.waiting_for_my_turn:
            print "waiting for my turn -- ignoring button release"
            return

        if self.press is None:
            return

        x, y = map(int, event.get_coords())
        spr = self.sprites.find_sprite((x, y))

        # when we are dragging, this sprite will be the same as self.press
        grid_pos = self.grid.xy_to_grid(x, y)
        hand_pos = self.hands[self.my_hand].xy_to_hand(x, y)
        print grid_pos, hand_pos
        if grid_pos is not None:  # Placing tile in grid
            if self.grid.grid[grid_pos] is None:
                card = self.deck.spr_to_card(self.press)
                print 'moving card to grid ', self.grid.grid_to_xy(grid_pos)
                card.spr.move(self.grid.grid_to_xy(grid_pos))
                i = self.grid.spr_to_grid(self.press)
                if i is not None:
                    self.grid.grid[i] = None
                
                self.grid.grid[grid_pos] = card
                self.placed_a_tile = True
                self.last_tile_played = card.number
                self.last_grid_played = grid_pos

                i = self.hands[self.my_hand].spr_to_hand(self.press)
                if i is not None:
                    self.hands[self.my_hand].hand[i] = None

                if self.last_spr_moved != card.spr:
                    self.last_spr_moved = card.spr
                self._show_highlight()
        # Returning tile to hand
        elif hand_pos is not None: # or x < self.grid.left:
            i = self.hands[self.my_hand].find_empty_slot()
            print 'found an empty slot?', i
            if i is not None: 
                print 'returning card to hand'
                card = self.deck.spr_to_card(self.press)
                print 'moving card to ', self.hands[self.my_hand].hand_to_xy(i)
                card.spr.move(self.hands[self.my_hand].hand_to_xy(i))
                if self.hands[self.my_hand].spr_to_hand(self.press) is not None:
                    self.hands[self.my_hand].hand[
                        self.hands[self.my_hand].spr_to_hand(self.press)] = None
                elif self.grid.spr_to_grid(self.press) is not None:
                    self.grid.grid[self.grid.spr_to_grid(self.press)] = None
                self.hands[self.my_hand].hand[i] = card
                if spr == self.last_spr_moved:
                    self.last_spr_moved = None
                self._hide_errormsgs()
                self._there_are_errors = False
                self.show_connected_tiles()
            else:  # Or return tile to the grid
                grid_pos = self.grid.spr_to_grid(self.press)
                if grid_pos is not None: 
                    card = self.deck.spr_to_card(self.press)
                    print 'returning card to grid'
                    card.spr.move(self.grid.grid_to_xy(grid_pos))

            self._hide_highlight()
            self.press = None
            self.release = None
            self.placed_a_tile = False
            return True

        self.release = spr
        if self.press == self.release and not self._it_is_a_drag():
            card = self.deck.spr_to_card(spr)
            card.rotate_clockwise()
            self.last_tile_orientation = card.orientation
            if self.last_spr_moved != card.spr:
                self.last_spr_moved = card.spr
            self._show_highlight()

        self._test_for_bad_paths(self.grid.spr_to_grid(self.press))
        self.show_connected_tiles()
        self.press = None
        self.release = None
        return True

    def _it_is_a_drag(self):
        if self.total_drag[0] * self.total_drag[0] + \
           self.total_drag[1] * self.total_drag[1] > \
           self.card_width * self.card_height:
            return True
        return False

    def _game_over(self, msg=_('Game over')):
        self._set_label(msg)
        if self.running_sugar:
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
                        tile.spr.set_layer(CARDS)
                        self.waiting_for_robot = False
                        return

        # If we didn't return above, we were unable to play a tile.
        if self.running_sugar:
            self.activity.set_robot_status(False, 'robot-off')
        # At the end of the game, show any tiles remaining in the robot's hand.
        for i in range(COL):
            if self.hands[ROBOT_HAND].hand[i] is not None:
                x, y = self.hands[ROBOT_HAND].hand_to_xy(i)
                self.hands[ROBOT_HAND].hand[i].spr.move(
                    (self.grid.left_hand + self.grid.xinc, y))
        self.waiting_for_robot = False
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
            self._check_card(tile, [int(tile / COL), 0], NORTH,
                             tile + OFFSETS[0])
            self._check_card(tile, [tile % ROW, ROW - 1], EAST,
                             tile + OFFSETS[1])
            self._check_card(tile, [int(tile / COL), COL - 1], SOUTH,
                             tile + OFFSETS[2])
            self._check_card(tile, [tile % ROW, 0], WEST, tile + OFFSETS[3])

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
            self.errormsg[direction].set_layer(OVER_THE_TOP)
        self.there_are_errors = True

    def _hide_errormsgs(self):
        ''' Hide all the error messages. '''
        for i in range(4):
            self.errormsg[i].move((self.grid.left, self.grid.top))
            self.errormsg[i].set_layer(HIDE)

    def _hide_highlight(self):
        ''' No tile is selected. '''
        for i in range(4):
            self.highlight[i].move((self.grid.left, self.grid.top))
            self.highlight[i].set_layer(HIDE)

    def _move_highlight(self, pos):
            for i in range(4):
                self.highlight[i].move_relative(pos)

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
                self.highlight[i].set_layer(OVER_THE_TOP)

    def _keypress_cb(self, area, event):
        return True

    def _expose_cb(self, win, event):
        self.sprites.redraw_sprites()
        return True

    def _destroy_cb(self, win, event):
        gtk.main_quit()
