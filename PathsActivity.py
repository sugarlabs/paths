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

import telepathy
from dbus.service import signal
from dbus.gobject_service import ExportedGObject
from sugar.presence import presenceservice
from sugar.presence.tubeconn import TubeConnection

from gettext import gettext as _
import locale
import os.path

from game import Game, CARDS
from hand import Hand
from utils import json_load, json_dump
from constants import ROW, COL

MAX_HANDS = 4

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
        self.nick = profile.get_nick_name()
        if profile.get_color() is not None:
            self.colors = profile.get_color().to_string().split(',')
        else:
            self.colors = ['#A0FFA0', '#FF8080']
        self._setup_toolbars(_have_toolbox)
        self._setup_dispatch_table()

        # Create a canvas
        canvas = gtk.DrawingArea()
        canvas.set_size_request(gtk.gdk.screen_width(), \
                                gtk.gdk.screen_height())
        self.set_canvas(canvas)
        canvas.show()
        self.show_all()

        self._game = Game(canvas, parent=self, colors=self.colors)
        self._setup_presence_service()

        # Restore game state from Journal or start new game
        if 'deck' in self.metadata:
            print 'restoring'
            self._restore()
        elif not hasattr(self, 'initiating'):
            print 'no initiating'
            self._game.new_game()
        elif not self.initiating:
            print 'I am not initiating'
            self._game.new_game()
        elif len(self._game.buddies) == 1:
            print 'no buddies'
            self._game.new_game()
        else:
            print 'I am confused'

    def _setup_toolbars(self, have_toolbox):
        """ Setup the toolbars.. """

        self.max_participants = 4

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

        self._new_game_button = _button_factory('new-game',
                                                _('Start a new game.'),
                                                self._new_game_cb, toolbar)

        self.robot_button = _button_factory('robot-off',
                                             _('Play with the computer.'),
                                             self._robot_cb, toolbar)

        self.dialog_button = _button_factory('dialog-ok',
                                             _('Turn complete'),
                                             self._dialog_cb, toolbar)

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
        if not self._game.playing_with_robot:
            self.set_robot_status(True, 'robot-on')
            self._game.new_game()
        else:
            self.set_robot_status(False, 'robot-off')
            self._game.new_game()

    def set_robot_status(self, status, icon):
        ''' Reset robot icon and status '''
        self._game.playing_with_robot = status
        self.robot_button.set_icon(icon)

    def _dialog_cb(self, button=None):
        ''' Send end of turn '''
        if self._game.placed_a_tile:
            print 'placed a tile and click on toolbar button'
            self._game.took_my_turn()
        else:
            print 'need to place a piece'

    def write_file(self, file_path):
        """ Write the grid status to the Journal """
        if not hasattr(self, '_game'):
            return
        self.metadata['deck'] = self._game.deck.serialize()
        self.metadata['grid'] = self._game.grid.serialize()
        if self._game._we_are_sharing():
            for i, hand in enumerate(self._game.hands):
                self.metadata['hand-' + str(i)] = hand.serialize()
        else:
            self.metadata['hand-0'] = self._game.hands[0].serialize()
            if self._game.playing_with_robot:
                self.metadata['hand-1'] = self._game.hands[1].serialize()
            
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

        for i in range(MAX_HANDS):
            if 'hand-' + str(i) in self.metadata:
                if len(self._game.hands) < i + 1:  # Add robot or shared hand?
                    self._game.hands.append(
                        Hand(self._game.card_width, self._game.card_height,
                             remote=True))
                self._game.hands[i].restore(self.metadata['hand-' + str(i)],
                                            self._game.deck)

        self._game.deck.index = ROW * COL - self._game.grid.cards_in_grid()
        for h in self._game.hands:
            self._game.deck.index += (COL - h.cards_in_hand())
        print 'recalculating deck index: %d = %d + ' % (
            self._game.deck.index, ROW * COL - self._game.grid.cards_in_grid())
        for h in self._game.hands:
            print (COL - h.cards_in_hand())

        self._game.last_spr_moved = None
        if 'last' in self.metadata:
            j = int(self.metadata['last'])
            for k in range(ROW * COL):
                if self._game.deck.cards[k].number == j:
                    self._game.last_spr_moved = self._game.deck.cards[k].spr
                    return

    # Collaboration-related methods

    def _setup_presence_service(self):
        """ Setup the Presence Service. """
        self.pservice = presenceservice.get_instance()
        self.initiating = None  # sharing (True) or joining (False)

        owner = self.pservice.get_owner()
        self.owner = owner
        self._game.buddies.append(self.nick)
        self._share = ""
        self.connect('shared', self._shared_cb)
        self.connect('joined', self._joined_cb)

    def _shared_cb(self, activity):
        """ Either set up initial share..."""
        if self._shared_activity is None:
            print("Error: Failed to share or join activity ... \
                _shared_activity is null in _shared_cb()")
            return

        self.initiating = True
        self.waiting_for_hand = False
        print('I am sharing...')

        self.conn = self._shared_activity.telepathy_conn
        self.tubes_chan = self._shared_activity.telepathy_tubes_chan
        self.text_chan = self._shared_activity.telepathy_text_chan

        self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].connect_to_signal\
            ('NewTube', self._new_tube_cb)

        print('This is my activity: making a tube...')
        id = self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].OfferDBusTube(
            SERVICE, {})

        self._new_game_button.set_tooltip(
            _('Start a new game once everyone has joined.'))

        self.robot_button.set_icon('no-robot')
        self.robot_button.set_tooltip(_('The robot is disabled when sharing.'))

    def _joined_cb(self, activity):
        """ ...or join an exisiting share. """
        if self._shared_activity is None:
            print("Error: Failed to share or join activity ... \
                _shared_activity is null in _shared_cb()")
            return

        self.initiating = False
        print('I joined a shared activity.')

        self.conn = self._shared_activity.telepathy_conn
        self.tubes_chan = self._shared_activity.telepathy_tubes_chan
        self.text_chan = self._shared_activity.telepathy_text_chan

        self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].connect_to_signal(\
            'NewTube', self._new_tube_cb)

        print('I am joining an activity: waiting for a tube...')
        self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES].ListTubes(
            reply_handler=self._list_tubes_reply_cb,
            error_handler=self._list_tubes_error_cb)

        self._new_game_button.set_icon('no-new-game')
        self._new_game_button.set_tooltip(
            _('Only the sharer can start a new game.'))

        self.robot_button.set_icon('no-robot')
        self.robot_button.set_tooltip(_('The robot is disabled when sharing.'))

        self.waiting_for_hand = True

    def _list_tubes_reply_cb(self, tubes):
        """ Reply to a list request. """
        for tube_info in tubes:
            self._new_tube_cb(*tube_info)

    def _list_tubes_error_cb(self, e):
        """ Log errors. """
        print('Error: ListTubes() failed: %s', e)

    def _new_tube_cb(self, id, initiator, type, service, params, state):
        """ Create a new tube. """
        print('New tube: ID=%d initator=%d type=%d service=%s params=%r \
state=%d' % (id, initiator, type, service, params, state))

        if (type == telepathy.TUBE_TYPE_DBUS and service == SERVICE):
            if state == telepathy.TUBE_STATE_LOCAL_PENDING:
                self.tubes_chan[ \
                              telepathy.CHANNEL_TYPE_TUBES].AcceptDBusTube(id)

            tube_conn = TubeConnection(self.conn,
                self.tubes_chan[telepathy.CHANNEL_TYPE_TUBES], id, \
                group_iface=self.text_chan[telepathy.CHANNEL_INTERFACE_GROUP])

            self.chattube = ChatTube(tube_conn, self.initiating, \
                self.event_received_cb)

            # Let the sharer know joiner is waiting for a hand.
            if self.waiting_for_hand:
                print 'send event joining (%s)' % (self.nick)
                self.send_event('j|%s' % (self.nick))

    def _setup_dispatch_table(self):
        self._processing_methods = {
            'n': [self._new_game, 'new game'],
            'j': [self._new_joiner, 'new joiner'],
            'b': [self._buddy_list, 'buddy list'],
            'd': [self._sending_deck, 'sending deck'],
            'h': [self._sending_hand, 'sending hand'],
            'p': [self._play_a_piece, 'play a piece'],
            't': [self._take_a_turn, 'take a turn']
            }

    def event_received_cb(self, event_message):
        if len(event_message) == 0:
            return
        try:
            print 'event received', event_message
            command, payload = event_message.split('|', 2)
        except ValueError:
            print('Could not split event message %s' % (event_message))
            return
        print 'calling event', self._processing_methods[command][1]
        self._processing_methods[command][0](payload)

    def _new_joiner(self, payload):
        print payload
        nick = payload
        print("%s has joined" % (nick))
        self.status.set_label(nick + ' ' + _('has joined.'))
        if not nick in self._game.buddies:
            self._game.buddies.append(nick)
        if self.initiating:
            payload = json_dump(self._game.buddies)
            print payload
            self.send_event('b|%s' % (payload))

    def _buddy_list(self, payload):
        buddies = json_load(payload)
        for nick in buddies:
            if not nick in self._game.buddies:
                self._game.buddies.append(nick)
                print 'appending %s to buddy list' % (nick)

    def _new_game(self, payload):
        if not self.initiating:
            print 'starting new game'
            self._game.new_game()

    def _sending_deck(self, payload):
        print 'got a deck'
        self._game.deck.restore(payload)
        print 'reseting cards in new deck'
        for card in self._game.deck.cards:
            card.reset()
            card.hide()

    def _sending_hand(self, payload):
        hand = json_load(payload)
        nick = hand[0]
        if nick == self.nick:
            print 'I got a hand'
            self._game.hands[self._game.buddies.index(nick)].restore(
                payload, self._game.deck, buddy=True)
        else:
            print 'I saw a hand for %s' % (nick)

    def _play_a_piece(self, payload):
        # TO DO: something with buttons and label
        tile_number, orientation, grid_position = json_load(payload)
        print 'moving tile', tile_number, orientation, grid_position
        for i in range(ROW * COL):  # find the tile with this number
            if self._game.deck.cards[i].number == tile_number:
                tile_to_move = i
                break
        self._game.grid.add_card_to_grid(tile_to_move, orientation,
                                         grid_position, self._game.deck)
        self._game.show_connected_tiles()
        if self.initiating:
            self._game.whos_turn += 1
            if self._game.whos_turn == len(self._game.buddies):
                self._game.whos_turn = 0
            print "it is %s's turn" % (self._game.buddies[self._game.whos_turn])
            print 'sending turn event'
            self.send_event('t|%s' % (self._game.buddies[self._game.whos_turn]))
            self._take_a_turn(self._game.buddies[self._game.whos_turn])

    def _take_a_turn(self, payload):
        print 'take a turn event'
        nick = payload
        print "It's %s's turn." % (nick)
        self.status.set_label(nick + ': ' + _('take a turn.'))
        if nick == self.nick:
            self._game.its_my_turn()
        else:
            self._game.its_their_turn(nick)

    def send_event(self, entry):
        """ Send event through the tube. """
        if hasattr(self, 'chattube') and self.chattube is not None:
            self.chattube.SendText(entry)


class ChatTube(ExportedGObject):
    """ Class for setting up tube for sharing """

    def __init__(self, tube, is_initiator, stack_received_cb):
        super(ChatTube, self).__init__(tube, PATH)
        self.tube = tube
        self.is_initiator = is_initiator  # Are we sharing or joining activity?
        self.stack_received_cb = stack_received_cb
        self.stack = ''

        self.tube.add_signal_receiver(self.send_stack_cb, 'SendText', IFACE,
                                      path=PATH, sender_keyword='sender')

    def send_stack_cb(self, text, sender=None):
        if sender == self.tube.get_unique_name():
            return
        self.stack = text
        self.stack_received_cb(text)

    @signal(dbus_interface=IFACE, signature='s')
    def SendText(self, text):
        self.stack = text
        print text
