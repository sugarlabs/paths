#Copyright (c) 2011 Walter Bender

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# You should have received a copy of the GNU General Public License
# along with this library; if not, write to the Free Software
# Foundation, 51 Franklin Street, Suite 500 Boston, MA 02110-1335 USA

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Gdk
gi.require_version('TelepathyGLib', '0.12')
from gi.repository import TelepathyGLib

import sugar3
from sugar3.activity import activity
from sugar3 import profile
from sugar3.graphics.toolbarbox import ToolbarBox
from sugar3.bundle.activitybundle import ActivityBundle
from sugar3.activity.widgets import ActivityToolbarButton
from sugar3.activity.widgets import StopButton
from sugar3.graphics.toolbarbox import ToolbarButton
from sugar3.graphics.toolbutton import ToolButton
from sugar3.graphics.menuitem import MenuItem
from sugar3.graphics.icon import Icon
from sugar3.datastore import datastore

from toolbar_utils import button_factory, image_factory, label_factory, \
    separator_factory


from dbus.service import signal
from dbus.gi_service import ExportedGObject
from sugar3.presence import presenceservice
from sugar3.presence.tubeconn import TubeConnection

try:
    from sugar3.presence.wrapper import CollabWrapper
except ImportError:
    from collabwrapper.collabwrapper import CollabWrapper

from gettext import gettext as _
import locale
import os.path

from game import Game, TILES
from hand import Hand
from genpieces import generate_xo
from utils import json_load, json_dump, svg_str_to_pixbuf
from constants import ROW, COL

MAX_HANDS = 4

SERVICE = 'org.sugarlabs.PathsActivity'
IFACE = SERVICE
PATH = '/org/augarlabs/PathsActivity'


class PathsActivity(activity.Activity):
    """ Path puzzle game """

    def __init__(self, handle):
        """ Initialize the toolbars and the game board """
        super(PathsActivity, self).__init__(handle)

        self.nick = profile.get_nick_name()
        if profile.get_color() is not None:
            self.colors = profile.get_color().to_string().split(',')
        else:
            self.colors = ['#A0FFA0', '#FF8080']

        self._setup_toolbars()
        self._setup_dispatch_table()

        # Create a canvas
        canvas = Gtk.DrawingArea()
        canvas.set_size_request(Gdk.Screen.width(), Gdk.Screen.height())
        self.set_canvas(canvas)
        canvas.show()
        self.show_all()

        self._game = Game(canvas, parent=self, colors=self.colors)
        self._setup_presence_service()

        # Restore game state from Journal or start new game
        if 'deck' in self.metadata:
            self._restore()
        else:
            self._game.new_game()

    def _setup_toolbars(self):
        """ Setup the toolbars. """

        self.max_participants = MAX_HANDS

        toolbox = ToolbarBox()

        # Activity toolbar
        activity_button = ActivityToolbarButton(self)

        toolbox.toolbar.insert(activity_button, 0)
        activity_button.show()

        self.set_toolbar_box(toolbox)
        toolbox.show()
        self.toolbar = toolbox.toolbar

        self._new_game_button = button_factory(
            'new-game', self.toolbar, self._new_game_cb,
            tooltip=_('Start a new game.'))

        self.robot_button = button_factory(
            'robot-off', self.toolbar, self._robot_cb,
            tooltip= _('Play with the robot.'))

        self.player = image_factory(
            svg_str_to_pixbuf(generate_xo(scale=0.8,
                                          colors=['#303030', '#303030'])),
            self.toolbar, tooltip=self.nick)

        self.dialog_button = button_factory(
            'go-next', self.toolbar, self._dialog_cb,
            tooltip=_('Turn complete'))

        self.status = label_factory(self.toolbar, '')

        self.hint_button = button_factory(
            'help-toolbar', self.toolbar, self._hint_cb,
            tooltip=_('Help'))

        self.score = label_factory(self.toolbar, _('Score: ') + '0')

        separator_factory(toolbox.toolbar, True, False)

        stop_button = StopButton(self)
        stop_button.props.accelerator = '<Ctrl>q'
        toolbox.toolbar.insert(stop_button, -1)
        stop_button.show()

    def _new_game_cb(self, button=None):
        ''' Start a new game. '''
        self._game.new_game()

    def _robot_cb(self, button=None):
        ''' Play with the computer (or not). '''
        if not self._game.playing_with_robot:
            self.set_robot_status(True, 'robot-on')
            self._game.new_game()
        else:
            self.set_robot_status(False, 'robot-off')
            self._game.new_game()

    def set_robot_status(self, status, icon):
        ''' Reset robot icon and status '''
        self._game.playing_with_robot = status
        self.robot_button.set_icon_name(icon)

    def _dialog_cb(self, button=None):
        ''' Send end of turn '''
        if self._game.placed_a_tile:
            self._game.took_my_turn()

    def _hint_cb(self, button=None):
        ''' Give a hint as to where to place a tile '''
        if not self._game.placed_a_tile:
            self._game.give_a_hint()

    def write_file(self, file_path):
        """ Write the grid status to the Journal """
        if not hasattr(self, '_game'):
            return
        for i in range(MAX_HANDS):
            if 'hand-' + str(i) in self.metadata:
                del self.metadata['hand-' + str(i)]
        if 'robot' in self.metadata:
            del self.metadata['robot']
        self.metadata['deck'] = self._game.deck.serialize()
        self.metadata['grid'] = self._game.grid.serialize()
        if self._game.we_are_sharing():
            for i, hand in enumerate(self._game.hands):
                self.metadata['hand-' + str(i)] = hand.serialize()
        else:
            self.metadata['hand-0'] = self._game.hands[0].serialize()
            if self._game.playing_with_robot:
                self.metadata['hand-1'] = self._game.hands[1].serialize()
                self.metadata['robot'] = 'True'

        self.metadata['score'] = str(self._game.score)
        self.metadata['index'] = str(self._game.deck.index)
        if self._game.last_spr_moved is not None and \
           self._game.grid.spr_to_grid(self._game.last_spr_moved) is not None:
            self.metadata['last'] = str(self._game.grid.grid[
                self._game.grid.spr_to_grid(self._game.last_spr_moved)].number)

    def _restore(self):
        """ Restore the game state from metadata """
        if 'robot' in self.metadata:
            self.set_robot_status(True, 'robot-on')
        if 'deck' in self.metadata:
            self._game.deck.restore(self.metadata['deck'])
        if 'grid' in self.metadata:
            self._game.grid.restore(self.metadata['grid'], self._game.deck)
        self._game.show_connected_tiles()

        for i in range(MAX_HANDS):
            if 'hand-' + str(i) in self.metadata:
                # hand-0 is already appended
                if i > 0:  # Add robot or shared hand?
                    self._game.hands.append(
                        Hand(self._game.tile_width, self._game.tile_height,
                             remote=True))
                self._game.hands[i].restore(self.metadata['hand-' + str(i)],
                                            self._game.deck)

        if 'index' in self.metadata:
            self._game.deck.index = int(self.metadata['index'])
        else:
            self._game.deck.index = ROW * COL - self._game.grid.tiles_in_grid()
            for hand in self._game.hands:
                self._game.deck.index += (COL - hand.tiles_in_hand())

        if 'score' in self.metadata:
            self._game.score = int(self.metadata['score'])
            self.score.set_label(_('Score: ') + str(self._game.score))

        self._game.last_spr_moved = None
        if 'last' in self.metadata:
            j = int(self.metadata['last'])
            for k in range(ROW * COL):
                if self._game.deck.tiles[k].number == j:
                    self._game.last_spr_moved = self._game.deck.tiles[k].spr
                    break

    # Collaboration-related methods

    def _setup_presence_service(self):
        """ Setup the Presence Service. """
        self.pservice = presenceservice.get_instance()
        self.initiating = None  # sharing (True) or joining (False)

        owner = self.pservice.get_owner()
        self.owner = owner
        self._game.buddies.append(self.nick)
        self._player_colors = [self.colors]
        self._player_pixbuf = [svg_str_to_pixbuf(
                generate_xo(scale=0.8, colors=self.colors))]
        self._share = ""
        self.connect('shared', self._shared_cb)
        self.connect('joined', self._joined_cb)

    def _shared_cb(self, activity):
        """ Either set up initial share..."""
        self._new_tube_common(True)

    def _joined_cb(self, activity):
        """ ...or join an exisiting share. """
        self._new_tube_common(False)

    def _new_tube_common(self, sharer):
        """ Joining and sharing are mostly the same... """
        if self._shared_activity is None:
            print("Error: Failed to share or join activity ... \
                _shared_activity is null in _shared_cb()")
            return

        self.initiating = sharer
        self.waiting_for_hand = not sharer

        self.conn = self._shared_activity.telepathy_conn
        self.tubes_chan = self._shared_activity.telepathy_tubes_chan
        self.text_chan = self._shared_activity.telepathy_text_chan

        self.tubes_chan[TelepathyGLib.IFACE_CHANNEL_TYPE_TUBES].connect_to_signal(
            'NewTube', self._new_tube_cb)

        if sharer:
            print('This is my activity: making a tube...')
            id = self.tubes_chan[TelepathyGLib.IFACE_CHANNEL_TYPE_TUBES].OfferDBusTube(
                SERVICE, {})

            self._new_game_button.set_tooltip(
                _('Start a new game once everyone has joined.'))
        else:
            print('I am joining an activity: waiting for a tube...')
            self.tubes_chan[TelepathyGLib.IFACE_CHANNEL_TYPE_TUBES].ListTubes(
                reply_handler=self._list_tubes_reply_cb,
                error_handler=self._list_tubes_error_cb)

            self._new_game_button.set_icon_name('no-new-game')
            self._new_game_button.set_tooltip(
                _('Only the sharer can start a new game.'))

        self.robot_button.set_icon_name('no-robot')
        self.robot_button.set_tooltip(_('The robot is disabled when sharing.'))

        # display your XO on the toolbar
        self.player.set_from_pixbuf(self._player_pixbuf[0])
        self.toolbar.show_all()

    def _list_tubes_reply_cb(self, tubes):
        """ Reply to a list request. """
        for tube_info in tubes:
            self._new_tube_cb(*tube_info)

    def _list_tubes_error_cb(self, e):
        """ Log errors. """
        print('Error: ListTubes() failed: %s', %(e))

    def _new_tube_cb(self, id, initiator, type, service, params, state):
        """ Create a new tube. """
        print('New tube: ID=%d initator=%d type=%d service=%s params=%r \
state=%d' % (id, initiator, type, service, params, state))

        if (type == TelepathyGLib.TubeType.DBUS and service == SERVICE):
            if state == TelepathyGLib.TubeState.LOCAL_PENDING:
                self.tubes_chan[TelepathyGLib.IFACE_CHANNEL_TYPE_TUBES].AcceptDBusTube(id)

            self.collab = CollabWrapper(self)
            self.collab.message.connect(self.event_received_cb)
            self.collab.setup()

            # Let the sharer know joiner is waiting for a hand.
            if self.waiting_for_hand:
                self.send_event("j", json_dump([self.nick, self.colors]))

    def _setup_dispatch_table(self):
        self._processing_methods = {
            'n': [self._new_game, 'new game'],
            'j': [self._new_joiner, 'new joiner'],
            'b': [self._buddy_list, 'buddy list'],
            'd': [self._sending_deck, 'sending deck'],
            'h': [self._sending_hand, 'sending hand'],
            'p': [self._play_a_piece, 'play a piece'],
            't': [self._take_a_turn, 'take a turn'],
            'g': [self._game_over, 'game over']
            }

    def event_received_cb(self, collab, buddy, msg):
        ''' Data from a tube has arrived. '''
        command = msg.get("command")
        if action is None:
            return

        payload = msg.get("payload")
        self._processing_methods[command][0](payload)

    def _new_joiner(self, payload):
        ''' Someone has joined; sharer adds them to the buddy list. '''
        [nick, colors] = json_load(payload)
        self.status.set_label(nick + ' ' + _('has joined.'))
        self._append_player(nick, colors)
        if self.initiating:
            payload = json_dump([self._game.buddies, self._player_colors])
            self.send_event("b", payload)

    def _append_player(self, nick, colors):
        ''' Keep a list of players, their colors, and an XO pixbuf '''
        if not nick in self._game.buddies:
            self._game.buddies.append(nick)
            self._player_colors.append(colors)
            self._player_pixbuf.append(svg_str_to_pixbuf(
                generate_xo(scale=0.8, colors=colors)))

    def _buddy_list(self, payload):
        ''' Sharer sent the updated buddy list. '''
        [buddies, colors] = json_load(payload)
        for i, nick in enumerate(buddies):
            self._append_player(nick, colors[i])

    def _new_game(self, payload):
        ''' Sharer can start a new game. '''
        if not self.initiating:
            self._game.new_game()

    def _game_over(self, payload):
        ''' Someone cannot plce a tile. '''
        if not self._game.saw_game_over:
            self._game.game_over()

    def _sending_deck(self, payload):
        ''' Sharer sends the deck. '''
        self._game.deck.restore(payload)
        for tile in self._game.deck.tiles:
            tile.reset()
            tile.hide()

    def _sending_hand(self, payload):
        ''' Sharer sends a hand. '''
        hand = json_load(payload)
        nick = hand[0]
        if nick == self.nick:
            self._game.hands[self._game.buddies.index(nick)].restore(
                payload, self._game.deck, buddy=True)

    def _play_a_piece(self, payload):
        ''' When a piece is played, everyone should move it into position. '''
        tile_number, orientation, grid_position = json_load(payload)
        for i in range(ROW * COL):  # find the tile with this number
            if self._game.deck.tiles[i].number == tile_number:
                tile_to_move = i
                break
        self._game.grid.add_tile_to_grid(tile_to_move, orientation,
                                         grid_position, self._game.deck)
        self._game.show_connected_tiles()

        if self.initiating:
            # First, remove the piece from whatever hand it was played.
            for i in range(COL):
                if self._game.hands[self._game.whos_turn].hand[i] is not None \
                   and \
                   self._game.hands[self._game.whos_turn].hand[i].number == \
                        tile_number:
                    self._game.hands[self._game.whos_turn].hand[i] = None
                    break

            # Then let the next player know it is their turn.
            self._game.whos_turn += 1
            if self._game.whos_turn == len(self._game.buddies):
                self._game.whos_turn = 0
            self.status.set_label(self.nick + ': ' + _('take a turn.'))
            self._take_a_turn(self._game.buddies[self._game.whos_turn])
            self.send_event("t", self._game.buddies[self._game.whos_turn])

    def _take_a_turn(self, nick):
        ''' If it is your turn, take it, otherwise, wait. '''
        if nick == self.nick:
            self._game.its_my_turn()
        else:
            self._game.its_their_turn(nick)

    def send_event(self, command, payload):
        """ Send event through the tube. """
        if hasattr(self, 'chattube') and self.collab is not None:
            self.collab.post(dict(
                command=command,
                payload=payload
            ))

    def set_player_on_toolbar(self, nick):
        self.player.set_from_pixbuf(self._player_pixbuf[
                self._game.buddies.index(nick)])
        self.player.set_tooltip_text(nick)

