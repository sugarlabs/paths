# Copyright (C) 2009 Simon Schampijer
# Copyright (C) 2018 James Cameron
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import os
import time
import logging
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from gi.repository import GLib

from gettext import gettext as _

from sugar3.activity import activity
from sugar3.graphics.toolbarbox import ToolbarBox
from sugar3.graphics.toolbutton import ToolButton
from sugar3.activity.widgets import ActivityButton
from sugar3.activity.widgets import TitleEntry
from sugar3.activity.widgets import StopButton
from sugar3.activity.widgets import ShareButton
from sugar3.activity.widgets import DescriptionItem
from collabwrapper import CollabWrapper


class TestButton(ToolButton):

    def __init__(self, activity, **kwargs):
        ToolButton.__init__(self, 'media-playback-start', **kwargs)
        self.props.tooltip = _('Ping via CollabWrapper')


class SendButton(ToolButton):

    def __init__(self, activity, **kwargs):
        ToolButton.__init__(self, 'transfer-to', **kwargs)
        self.props.tooltip = _('Send via CollabWrapper')


class ClearButton(ToolButton):

    def __init__(self, activity, **kwargs):
        ToolButton.__init__(self, 'edit-clear', **kwargs)
        self.props.tooltip = _('Clear Log')


class CollabWrapperTestActivity(activity.Activity):

    def __init__(self, handle):
        activity.Activity.__init__(self, handle)

        self._make_toolbar_box()
        self._make_canvas()
        self._make_collaboration()
        self._make_automatic_restart()

    def set_data(self, data):
        if data is not 'no specific data':
            logging.error('get_data, set_data: unexpected data %r' % data)

    def get_data(self):
        return 'no specific data'

    def _make_toolbar_box(self):
        toolbar_box = ToolbarBox()

        def tool(callable, pos):
            widget = callable(self)
            toolbar_box.toolbar.insert(widget, pos)
            widget.show()
            return widget

        def bar():
            separator = Gtk.SeparatorToolItem()
            toolbar_box.toolbar.insert(separator, -1)
            separator.show()

        def gap():
            separator = Gtk.SeparatorToolItem()
            separator.props.draw = False
            separator.set_expand(True)
            toolbar_box.toolbar.insert(separator, -1)
            separator.show()

        tool(ActivityButton, 0)
        tool(TitleEntry, -1)
        tool(DescriptionItem, -1)
        tool(ShareButton, -1)
        bar()
        button = tool(TestButton, -1)
        button.props.accelerator = '<ctrl>p'
        button.connect('clicked', self._test_clicked_cb)
        button = tool(SendButton, -1)
        button.connect('clicked', self._send_clicked_cb)
        button = tool(ClearButton, -1)
        button.connect('clicked', self._clear_clicked_cb)
        gap()
        tool(StopButton, -1)

        toolbar_box.show()

        self.set_toolbar_box(toolbar_box)

    def _test_clicked_cb(self, widget):
        now = time.time()
        self._collab.post({'action': 'echo-request', 'text': now})
        self._say('%.6f send echo-request %r\n' % (now, now))

    def _send_clicked_cb(self, widget):
        now = time.time()
        data = 'One Two Three'
        desc = 'Test Data'
        self._collab.send_file_memory(self._last_buddy, data, desc)
        self._say('%.6f send data %r\n' % (now, (data, desc)))

    def _clear_clicked_cb(self, widget):
        self._textbuffer.props.text = ''

    def _make_canvas(self):
        self._textview = Gtk.TextView()
        self._textview.props.editable = False
        self._textbuffer = self._textview.get_buffer()

        sw = Gtk.ScrolledWindow()
        sw.add(self._textview)

        entry = Gtk.Entry()
        entry.connect('activate', self._entry_activate_cb)

        def focus_timer_cb():
            entry.grab_focus()
            return False
        GLib.timeout_add(1500, focus_timer_cb)

        box = Gtk.VBox()
        box.pack_start(sw, True, True, 10)
        box.pack_end(entry, False, False, 10)
        box.show_all()

        self.set_canvas(box)

    def _say(self, string):
        self._textbuffer.begin_user_action()
        self._textbuffer.insert(
            self._textbuffer.get_end_iter(), string, len(string))
        self._textview.scroll_mark_onscreen(self._textbuffer.create_mark(
            None, self._textbuffer.get_end_iter()))
        self._textbuffer.end_user_action()

    def _entry_activate_cb(self, widget):
        text = widget.props.text
        widget.props.text = ''
        self._collab.post({'action': 'chat', 'text': text})
        self._say('%.6f send chat %r\n' % (time.time(), text))

    def _make_collaboration(self):
        def on_activity_joined_cb(me):
            self._say('%.6f activity joined\n' % (time.time()))
        self.connect('joined', on_activity_joined_cb)

        def on_activity_shared_cb(me):
            self._say('%.6f activity shared\n' % (time.time()))
        self.connect('shared', on_activity_shared_cb)

        self._collab = CollabWrapper(self)
        self._collab.connect('message', self._message_cb)

        def on_joined_cb(collab, msg):
            self._say('%.6f joined\n' % (time.time()))
        self._collab.connect('joined', on_joined_cb, 'joined')

        def on_buddy_joined_cb(collab, buddy, msg):
            self._say('%.6f buddy-joined %s@%s\n' %
                      (time.time(), buddy.props.nick, buddy.props.ip4_address))
        self._collab.connect('buddy_joined', on_buddy_joined_cb,
                             'buddy_joined')

        def on_buddy_left_cb(collab, buddy, msg):
            self._say('%.6f buddy-left %s@%s\n' %
                      (time.time(), buddy.props.nick, buddy.props.ip4_address))
        self._collab.connect('buddy_left', on_buddy_left_cb, 'buddy_left')

        def on_incoming_file_cb(collab, ft, desc):
            self._say('%.6f incoming-file %r\n' %
                      (time.time(), desc))

            def on_ready_cb(ft, stream):
                stream.close(None)
                gbytes = stream.steal_as_bytes()
                data = gbytes.get_data()

                self._say('%.6f data %r\n' % (time.time(), data))

            ft.connect('ready', on_ready_cb)
            ft.accept_to_memory()
        self._collab.connect('incoming_file', on_incoming_file_cb)

        self._collab.setup()
        self._last_buddy = None

    def _message_cb(self, collab, buddy, msg):

        def say(string):
            self._say('%.6f recv from %s@%s ' %
                      (time.time(), buddy.props.nick, buddy.props.ip4_address))
            self._say(string)

        self._last_buddy = buddy

        action = msg.get('action')
        if action == 'echo-reply':
            text = msg.get('text')
            latency = (time.time() - float(text)) * 1000.0
            say('%s %r latency=%.3f ms\n' % (action, text, latency))
            return
        if action == 'echo-request':
            text = msg.get('text')
            self._collab.post({'action': 'echo-reply', 'text': text})
            say('%s %r\n' % (action, text))
            return
        if action == 'chat':
            text = msg.get('text')
            say('%s %r\n' % (action, text))
            return
        say('%s\n' % (action))

    def _make_automatic_restart(self):
        ct = os.stat('activity.py').st_ctime

        def restarter():
            if os.stat('activity.py').st_ctime != ct:
                GLib.timeout_add(233, self.close)
                logging.error('-- restart --')
                return False
            return True
        GLib.timeout_add(233, restarter)
