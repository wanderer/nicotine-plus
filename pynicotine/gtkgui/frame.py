# COPYRIGHT (C) 2020 Nicotine+ Team
# COPYRIGHT (C) 2016-2017 Michael Labouebe <gfarmerfr@free.fr>
# COPYRIGHT (C) 2016-2018 Mutnick <mutnick@techie.com>
# COPYRIGHT (C) 2008-2011 Quinox <quinox@users.sf.net>
# COPYRIGHT (C) 2006-2009 Daelstorm <daelstorm@gmail.com>
# COPYRIGHT (C) 2009 Hedonist <ak@sensi.org>
# COPYRIGHT (C) 2003-2004 Hyriand <hyriand@thegraveyard.org>
#
# GNU GENERAL PUBLIC LICENSE
#    Version 3, 29 June 2007
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from gettext import gettext as _
from urllib.parse import urlencode

import gi
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject as gobject
from gi.repository import Gtk as gtk

import _thread
import pynicotine.utils
from pynicotine import pluginsystem
from pynicotine import slskmessages
from pynicotine import slskproto
from pynicotine.gtkgui import imagedata
from pynicotine.gtkgui import notifications
from pynicotine.gtkgui import nowplaying
from pynicotine.gtkgui import tray
from pynicotine.gtkgui import utils
from pynicotine.gtkgui.chatrooms import ChatRooms
from pynicotine.gtkgui.checklatest import checklatest
from pynicotine.gtkgui.dirchooser import ChooseFile
from pynicotine.gtkgui.dirchooser import SaveFile
from pynicotine.gtkgui.downloads import Downloads
from pynicotine.gtkgui.dialogs import FindDialog
from pynicotine.gtkgui.dialogs import OptionDialog
from pynicotine.gtkgui.fastconfigure import FastConfigureAssistant
from pynicotine.gtkgui.privatechat import PrivateChats
from pynicotine.gtkgui.roomlist import RoomList
from pynicotine.gtkgui.search import Searches
from pynicotine.gtkgui.settingswindow import SettingsWindow
from pynicotine.gtkgui.uploads import Uploads
from pynicotine.gtkgui.userbrowse import UserBrowse
from pynicotine.gtkgui.userinfo import UserInfo
from pynicotine.gtkgui.userinfo import UserTabs
from pynicotine.gtkgui.userlist import UserList
from pynicotine.gtkgui.utils import AppendLine
from pynicotine.gtkgui.utils import BuddiesComboBox
from pynicotine.gtkgui.utils import Humanize
from pynicotine.gtkgui.utils import HumanSpeed
from pynicotine.gtkgui.utils import ImageLabel
from pynicotine.gtkgui.utils import OpenUri
from pynicotine.gtkgui.utils import PopupMenu
from pynicotine.gtkgui.utils import ScrollBottom
from pynicotine.logfacility import log
from pynicotine.pynicotine import NetworkEventProcessor
from pynicotine.upnp import UPnPPortMapping
from pynicotine.utils import unescape
from pynicotine.utils import version


class NicotineFrame:

    def __init__(self, data_dir, config, plugins, use_trayicon, bindip=None, port=None):

        self.clip_data = ""
        self.data_dir = data_dir
        self.configfile = config
        self.transfermsgs = {}
        self.transfermsgspostedtime = 0
        self.manualdisconnect = 0
        self.away = 0
        self.exiting = 0
        self.startup = True
        self.current_tab = 0
        self.rescanning = 0
        self.brescanning = 0
        self.needrescan = False
        self.autoaway = False
        self.awaytimerid = None
        self.chatrooms = None
        self.bindip = bindip
        self.port = port
        self.got_focus = False

        try:
            # Spell checking support
            gi.require_version('Gspell', '1')
            from gi.repository import Gspell  # noqa: F401
            self.gspell = True
        except (ImportError, ValueError):
            self.gspell = False

        self.np = NetworkEventProcessor(
            self,
            self.callback,
            self.logMessage,
            self.SetStatusText,
            self.bindip,
            self.port,
            data_dir,
            config
        )

        config = self.np.config.sections

        utils.DECIMALSEP = config["ui"]["decimalsep"]
        utils.CATCH_URLS = config["urls"]["urlcatching"]
        utils.HUMANIZE_URLS = config["urls"]["humanizeurls"]
        utils.PROTOCOL_HANDLERS = config["urls"]["protocols"].copy()
        utils.PROTOCOL_HANDLERS["slsk"] = self.OnSoulSeek
        utils.USERNAMEHOTSPOTS = config["ui"]["usernamehotspots"]
        utils.NICOTINE = self

        pynicotine.utils.log = self.logMessage

        log.addlistener(self.logCallback)

        self.LoadIcons()

        self.accel_group = gtk.AccelGroup()
        self.roomlist = RoomList(self)

        # Import GtkBuilder widgets
        builder = gtk.Builder()

        builder.set_translation_domain('nicotine')
        builder.add_from_file(os.path.join(os.path.dirname(os.path.realpath(__file__)), "ui", "mainwindow.ui"))

        for i in builder.get_objects():
            try:
                self.__dict__[gtk.Buildable.get_name(i)] = i
            except TypeError:
                pass

        # Disable a few elements until we're logged in (search field, download buttons etc.)
        self.SetWidgetOnlineStatus(False)

        self.MainWindow.set_title(_("Nicotine+") + " " + version)
        self.MainWindow.set_default_icon(self.images["n"])
        self.MainWindow.set_icon(self.images["n"])
        # self.MainWindow.selection_add_target("PRIMARY", "STRING", 1)
        hints_geometry = Gdk.Geometry()
        hints_geometry.base_height = 460
        hints_geometry.base_width = 500
        self.MainWindow.set_geometry_hints(None, hints_geometry, Gdk.WindowHints(Gdk.WindowHints.MIN_SIZE))
        self.MainWindow.connect("focus_in_event", self.OnFocusIn)
        self.MainWindow.connect("focus_out_event", self.OnFocusOut)
        self.MainWindow.connect("configure_event", self.OnWindowChange)
        self.MainWindow.add_accel_group(self.accel_group)

        builder.connect_signals(self)

        width = self.np.config.sections["ui"]["width"]
        height = self.np.config.sections["ui"]["height"]

        self.MainWindow.resize(width, height)

        xpos = self.np.config.sections["ui"]["xposition"]
        ypos = self.np.config.sections["ui"]["yposition"]

        # According to the pygtk doc this will be ignored my many window managers since the move takes place before we do a show()
        if min(xpos, ypos) < 0:
            self.MainWindow.set_position(gtk.WindowPosition.CENTER)
        else:
            self.MainWindow.move(xpos, ypos)

        maximized = self.np.config.sections["ui"]["maximized"]

        if maximized == "True":
            self.MainWindow.maximize()

        # Initialize these windows/dialogs later when necessary
        self.fastconfigure = None
        self.now = None
        self.settingswindow = None

        self.minimized = False
        self.HiddenTabs = {}

        self.clip = gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

        # for iterating buddy changes to the combos
        self.CreateRecommendationsWidgets()

        self.status_context_id = self.Statusbar.get_context_id("")

        self.socket_context_id = self.SocketStatus.get_context_id("")
        self.socket_template = _("%(current)s/%(limit)s Connections")

        self.user_context_id = self.UserStatus.get_context_id("")
        self.down_context_id = self.DownStatus.get_context_id("")
        self.up_context_id = self.UpStatus.get_context_id("")

        self.MainWindow.connect("delete-event", self.on_delete_event)
        self.MainWindow.connect('window-state-event', self.window_state_event_cb)
        self.MainWindow.connect("destroy", self.OnDestroy)
        self.MainWindow.connect("key_press_event", self.OnKeyPress)
        self.MainWindow.connect("motion-notify-event", self.OnButtonPress)

        for thing in config["interests"]["likes"]:
            self.likes[thing] = self.likeslist.append([thing])

        for thing in config["interests"]["dislikes"]:
            self.dislikes[thing] = self.dislikeslist.append([thing])

        # Initialise the Notebooks
        self.ChatNotebook = ChatRooms(self)
        self.PrivatechatNotebook = PrivateChats(self)
        self.UserInfoNotebook = UserTabs(self, UserInfo, self.UserInfoNotebookRaw)
        self.UserBrowseNotebook = UserTabs(self, UserBrowse, self.UserBrowseNotebookRaw)
        self.SearchNotebook = Searches(self)

        for w in self.ChatNotebook, self.PrivatechatNotebook, self.UserInfoNotebook, self.UserBrowseNotebook, self.SearchNotebook:
            w.set_tab_closers(config["ui"]["tabclosers"])
            w.set_reorderable(config["ui"]["tab_reorderable"])
            w.show_images(config["notifications"]["notification_tab_icons"])

        for tab in self.MainNotebook.get_children():
            self.MainNotebook.set_tab_reorderable(tab, config["ui"]["tab_reorderable"])

        # Translation for the labels of tabs
        translated_tablabels = {
            self.ChatTabLabel: _("Chat rooms"),
            self.PrivateChatTabLabel: _("Private chat"),
            self.SearchTabLabel: _("Search files"),
            self.UserInfoTabLabel: _("User info"),
            self.DownloadsTabLabel: _("Downloads"),
            self.UploadsTabLabel: _("Uploads"),
            self.UserBrowseTabLabel: _("User browse"),
            self.InterestsTabLabel: _("Interests")
        }

        # Mapping between the pseudo tabs and their vbox/hbox
        map_tablabels_to_box = {
            self.ChatTabLabel: "chathbox",
            self.PrivateChatTabLabel: "privatevbox",
            self.SearchTabLabel: "searchvbox",
            self.UserInfoTabLabel: "userinfovbox",
            self.DownloadsTabLabel: "downloadsvbox",
            self.UploadsTabLabel: "uploadsvbox",
            self.UserBrowseTabLabel: "userbrowsevbox",
            self.InterestsTabLabel: "interestsvbox"
        }

        # Initialize tabs labels
        for label_tab in [
            self.ChatTabLabel,
            self.PrivateChatTabLabel,
            self.SearchTabLabel,
            self.UserInfoTabLabel,
            self.DownloadsTabLabel,
            self.UploadsTabLabel,
            self.UserBrowseTabLabel,
            self.InterestsTabLabel
        ]:
            # Initialize the image label
            img_label = ImageLabel(translated_tablabels[label_tab], self.images["empty"])
            img_label.show()

            # Add it to the eventbox
            label_tab.add(img_label)

            # Set tab icons, angle and text color
            img_label.show_image(config["notifications"]["notification_tab_icons"])
            img_label.set_angle(config["ui"]["labelmain"])
            img_label.set_text_color(0)

            # Set the menu to hide the tab
            eventbox_name = gtk.Buildable.get_name(label_tab)

            label_tab.connect('button_press_event', self.on_tab_click, eventbox_name + "Menu", map_tablabels_to_box[label_tab])

            self.__dict__[eventbox_name + "Menu"] = popup = utils.PopupMenu(self)

            popup.setup(
                (
                    "#" + _("Hide %(tab)s") % {"tab": translated_tablabels[label_tab]}, self.HideTab, [label_tab, map_tablabels_to_box[label_tab]]
                )
            )

            popup.set_user(map_tablabels_to_box[label_tab])

        self.LogScrolledWindow = gtk.ScrolledWindow()
        self.LogScrolledWindow.set_min_content_height(90)
        self.LogScrolledWindow.set_policy(gtk.PolicyType.AUTOMATIC, gtk.PolicyType.AUTOMATIC)
        self.LogScrolledWindow.show()

        self.LogWindow = gtk.TextView()

        self.LogWindow.set_pixels_above_lines(1)
        self.LogWindow.set_pixels_below_lines(1)
        self.LogWindow.set_left_margin(10)
        self.LogWindow.set_right_margin(10)
        self.LogWindow.set_top_margin(5)
        self.LogWindow.set_bottom_margin(5)

        self.LogWindow.set_wrap_mode(gtk.WrapMode.WORD)
        self.LogWindow.set_cursor_visible(False)
        self.LogWindow.set_editable(False)

        self.LogScrolledWindow.add(self.LogWindow)
        self.LogWindow.connect("button-press-event", self.OnPopupLogMenu)

        # Popup menu on the log windows
        self.logpopupmenu = PopupMenu(self).setup(
            ("#" + _("Find"), self.OnFindLogWindow),
            ("", None),
            ("#" + _("Copy"), self.OnCopyLogWindow),
            ("#" + _("Copy All"), self.OnCopyAllLogWindow),
            ("", None),
            ("#" + _("Clear log"), self.OnClearLogWindow)
        )

        self.debugLogBox.pack_start(self.LogScrolledWindow, True, True, 0)
        self.debugWarnings.set_active((1 in config["logging"]["debugmodes"]))
        self.debugSearches.set_active((2 in config["logging"]["debugmodes"]))
        self.debugConnections.set_active((3 in config["logging"]["debugmodes"]))
        self.debugMessages.set_active((4 in config["logging"]["debugmodes"]))
        self.debugTransfers.set_active((5 in config["logging"]["debugmodes"]))
        self.debugStatistics.set_active((6 in config["logging"]["debugmodes"]))
        self.debugButtonsBox.hide()

        if config["logging"]["logcollapsed"]:
            self.show_log_window1.set_active(False)
        else:
            self.show_log_window1.set_active(True)

        self.LogWindow.show()
        self.OnShowLog(self.show_log_window1)

        self.show_debug_info1.set_active(self.np.config.sections["logging"]["debug"])

        self.chatrooms = self.ChatNotebook
        self.chatrooms.show()

        # Create Search combo ListStores
        self.SearchEntryCombo_List = gtk.ListStore(gobject.TYPE_STRING)
        self.SearchEntryCombo.set_model(self.SearchEntryCombo_List)
        self.SearchEntryCombo.set_entry_text_column(0)

        self.SearchEntry = self.SearchEntryCombo.get_child()
        self.SearchEntry.connect("activate", self.OnSearch)

        self.RoomSearchCombo_List = gtk.ListStore(gobject.TYPE_STRING)
        self.RoomSearchCombo.set_model(self.RoomSearchCombo_List)
        self.RoomSearchCombo.set_entry_text_column(0)

        self.SearchMethod_List = gtk.ListStore(gobject.TYPE_STRING)
        self.SearchMethod.set_model(self.SearchMethod_List)
        renderer_text = gtk.CellRendererText()
        self.SearchMethod.pack_start(renderer_text, True)
        self.SearchMethod.add_attribute(renderer_text, "text", 0)

        self.Searches = self.SearchNotebook
        self.Searches.show()
        self.Searches.LoadConfig()

        self.downloads = Downloads(self)
        self.uploads = Uploads(self)
        self.userlist = UserList(self)

        self.UpdateColours(1)

        self.privatechats = self.PrivatechatNotebook
        self.privatechats.show()

        self.userinfo = self.UserInfoNotebook
        self.userinfo.show()

        self.userbrowse = self.UserBrowseNotebook
        self.userbrowse.show()

        self.userinfo.SetTabLabel(self.UserInfoTabLabel)
        self.userbrowse.SetTabLabel(self.UserBrowseTabLabel)

        self.sUserinfoButton.connect("clicked", self.OnGetUserInfo)
        self.UserInfoCombo.get_child().connect("activate", self.OnGetUserInfo)

        self.sPrivateChatButton.connect("clicked", self.OnGetPrivateChat)
        self.UserPrivateCombo.get_child().connect("activate", self.OnGetPrivateChat)

        self.sSharesButton.connect("clicked", self.OnGetShares)
        self.UserBrowseCombo.get_child().connect("activate", self.OnGetShares)

        if config["ui"]["roomlistcollapsed"]:
            self.show_room_list1.set_active(False)
        else:
            self.vpaned3.pack2(self.roomlist.vbox2, True, True)
            self.show_room_list1.set_active(True)

        buddylist = config["ui"]["buddylistinchatrooms"]
        if buddylist == 1:
            self.buddylist_in_chatrooms1.set_active(True)
        elif buddylist == 2:
            self.buddylist_always_visible.set_active(True)
        elif buddylist == 3:
            self.buddylist_hidden.set_active(True)
        elif buddylist == 0:
            self.buddylist_in_tab.set_active(True)

        if config["columns"]["hideflags"]:
            self.ShowFlags.set_active(False)
        else:
            self.ShowFlags.set_active(True)

        self.SetUserStatus(_("Offline"))

        self.Notifications = notifications.Notifications(self)
        self.TrayApp = tray.TrayApp(self)

        self.hilites = {
            "rooms": [],
            "private": []
        }

        self.users_template = _("Users: %s")
        self.files_template = _("Files: %s")
        self.down_template = _("Down: %(num)i users, %(speed).1f KB/s")
        self.up_template = _("Up: %(num)i users, %(speed).1f KB/s")
        self.tray_tooltip_template = _("Nicotine+ Transfers: %(speeddown).1f KB/s Down, %(speedup).1f KB/s Up")

        self.UpdateBandwidth()
        self.ShowTransferButtons.set_active(self.np.config.sections["transfers"]["enabletransferbuttons"])
        self.UpdateTransferButtons()

        # Search Methods
        self.searchroomslist = {}
        self.searchmethods = {}

        # Create a list of objects of the BuddiesComboBox class
        # This add a few methods to add/remove entries on all combobox at once
        self.BuddiesComboEntries = [
            BuddiesComboBox(self, self.UserSearchCombo),
            BuddiesComboBox(self, self.UserPrivateCombo),
            BuddiesComboBox(self, self.UserInfoCombo),
            BuddiesComboBox(self, self.UserBrowseCombo)
        ]

        # Initial filling of the buddies combobox
        _thread.start_new_thread(self.BuddiesCombosFill, ("",))

        self.SearchMethod_List.clear()

        # Space after Joined Rooms is important, so it doesn't conflict
        # with any possible real room, but if it's not translated with the space
        # nothing awful will happen
        self.searchroomslist[_("Joined Rooms ")] = self.RoomSearchCombo_List.append([_("Joined Rooms ")])
        self.RoomSearchCombo.set_active_iter(self.searchroomslist[_("Joined Rooms ")])

        for method in [_("Global"), _("Buddies"), _("Rooms"), _("User")]:
            self.searchmethods[method] = self.SearchMethod_List.append([method])

        self.SearchMethod.set_active_iter(self.searchmethods[_("Global")])
        self.SearchMethod.connect("changed", self.OnSearchMethod)

        self.UserSearchCombo.hide()
        self.RoomSearchCombo.hide()

        self.disconnect1.set_sensitive(0)
        self.awayreturn1.set_sensitive(0)
        self.check_privileges1.set_sensitive(0)
        self.get_privileges1.set_sensitive(0)

        self.pluginhandler = pluginsystem.PluginHandler(self, plugins)

        if config["transfers"]["rescanonstartup"]:

            # Rescan public shares if needed
            if not self.np.config.sections["transfers"]["friendsonly"] and self.np.config.sections["transfers"]["shared"]:
                self.OnRescan()

            # Rescan buddy shares if needed
            if self.np.config.sections["transfers"]["enablebuddyshares"]:
                self.OnBuddyRescan()

        self.SetTabPositions()

        # Test if we want to do a port mapping
        if self.np.config.sections["server"]["upnp"]:

            # Initialise a UPnPPortMapping object
            upnp = UPnPPortMapping()

            # Check if we can do a port mapping
            (self.upnppossible, errors) = upnp.IsPossible()

            # Test if we are able to do a port mapping
            if self.upnppossible:
                # Do the port mapping
                _thread.start_new_thread(upnp.AddPortMapping, (self, self.np))
            else:
                # Display errors
                if errors is not None:
                    for err in errors:
                        log.addwarning(err)

        ConfigUnset = self.np.config.needConfig()
        if ConfigUnset:
            if ConfigUnset > 1:
                self.connect1.set_sensitive(False)
                self.rescan_public.set_sensitive(True)

                # Set up fast configure dialog
                self.OnFastConfigure(None, show=False)
            else:
                # Connect anyway
                self.OnConnect(-1)
        else:
            self.OnConnect(-1)

        self.UpdateDownloadFilters()

        # Create the trayicon if needed
        if use_trayicon and config["ui"]["trayicon"]:
            self.TrayApp.Create()

        # Deactivate public shares related menu entries if we don't use them
        if self.np.config.sections["transfers"]["friendsonly"] or not self.np.config.sections["transfers"]["shared"]:
            self.rescan_public.set_sensitive(False)
            self.browse_public_shares.set_sensitive(False)

        # Deactivate buddy shares related menu entries if we don't use them
        if not self.np.config.sections["transfers"]["enablebuddyshares"]:
            self.rescan_buddy.set_sensitive(False)
            self.browse_buddy_shares.set_sensitive(False)

        self.SetMainTabsOrder()
        self.SetMainTabsVisibility()
        self.SetLastSessionTab()

        self.MainNotebook.connect("page-removed", self.OnPageRemoved)
        self.MainNotebook.connect("page-reordered", self.OnPageReordered)
        self.MainNotebook.connect("page-added", self.OnPageAdded)

        self.startup = False

    def AddDebugLevel(self, debugLevel):
        if debugLevel not in self.np.config.sections["logging"]["debugmodes"]:
            self.np.config.sections["logging"]["debugmodes"].append(debugLevel)

    def RemoveDebugLevel(self, debugLevel):
        if debugLevel in self.np.config.sections["logging"]["debugmodes"]:
            self.np.config.sections["logging"]["debugmodes"].remove(debugLevel)

    def OnDebugWarnings(self, widget):
        if self.startup:
            return
        if widget.get_active():
            self.AddDebugLevel(1)
        else:
            self.RemoveDebugLevel(1)

    def OnDebugSearches(self, widget):
        if self.startup:
            return
        if widget.get_active():
            self.AddDebugLevel(2)
        else:
            self.RemoveDebugLevel(2)

    def OnDebugConnections(self, widget):
        if self.startup:
            return
        if widget.get_active():
            self.AddDebugLevel(3)
        else:
            self.RemoveDebugLevel(3)

    def OnDebugMessages(self, widget):
        if self.startup:
            return
        if widget.get_active():
            self.AddDebugLevel(4)
        else:
            self.RemoveDebugLevel(4)

    def OnDebugTransfers(self, widget):
        if self.startup:
            return
        if widget.get_active():
            self.AddDebugLevel(5)
        else:
            self.RemoveDebugLevel(5)

    def OnDebugStatistics(self, widget):
        if self.startup:
            return
        if widget.get_active():
            self.AddDebugLevel(6)
        else:
            self.RemoveDebugLevel(6)

    def on_delete_event(self, widget, event):

        if not self.np.config.sections["ui"]["exitdialog"]:
            return False

        if self.TrayApp.IsTrayIconVisible() and self.np.config.sections["ui"]["exitdialog"] == 2:
            if self.MainWindow.get_property("visible"):
                self.MainWindow.hide()
            return True

        if self.TrayApp.IsTrayIconVisible():
            OptionDialog(
                parent=self.MainWindow,
                title=_('Close Nicotine+?'),
                message=_('Are you sure you wish to exit Nicotine+ at this time?'),
                third=_("Send to tray"),
                checkbox_label=_("Remember choice"),
                callback=self.on_quit_response
            )
        else:
            OptionDialog(
                parent=self.MainWindow,
                title=_('Close Nicotine+?'),
                message=_('Are you sure you wish to exit Nicotine+ at this time?'),
                checkbox_label=_("Remember choice"),
                callback=self.on_quit_response
            )

        return True

    def window_state_event_cb(self, window, event):
        if event.changed_mask and Gdk.WindowState.ICONIFIED:
            if event.new_window_state and Gdk.WindowState.ICONIFIED:
                self.minimized = 1
            else:
                self.minimized = 0

    def LoadIcons(self):
        self.images = {}
        self.icons = {}
        self.flag_images = {}
        self.flag_users = {}
        scale = None

        def loadStatic(name):
            loader = GdkPixbuf.PixbufLoader()
            data = getattr(imagedata, "%s" % (name,))
            loader.write(data)
            loader.close()
            pixbuf = loader.get_pixbuf()
            if scale:
                w, h = pixbuf.get_width(), pixbuf.get_height()
                if w == h:
                    pixbuf = pixbuf.scale_simple(scale, scale, Gdk.INTERP_BILINEAR)
            return pixbuf

        names = [
            "empty",
            "away",
            "online",
            "offline",
            "hilite",
            "hilite3",
            "trayicon_away",
            "trayicon_connect",
            "trayicon_disconnect",
            "trayicon_msg",
            "n",
            "notify"
        ]

        if self.np.config.sections["ui"].get("icontheme"):
            extensions = ["jpg", "jpeg", "bmp", "png", "svg"]
            for name in names:
                path = None
                exts = extensions[:]
                loaded = False
                while not path or (exts and not loaded):
                    path = os.path.expanduser(os.path.join(self.np.config.sections["ui"]["icontheme"], "%s.%s" % (name, exts.pop())))
                    if os.path.exists(path):
                        data = open(path, 'rb')
                        s = data.read()
                        data.close()
                        loader = GdkPixbuf.PixbufLoader()
                        try:
                            loader.write(s)
                            loader.close()
                            pixbuf = loader.get_pixbuf()
                            if scale:
                                w, h = pixbuf.get_width(), pixbuf.get_height()
                                if w == h:
                                    pixbuf = pixbuf.scale_simple(scale, scale, Gdk.INTERP_BILINEAR)
                            self.images[name] = pixbuf
                            loaded = True
                        except gobject.GError:
                            pass
                        del loader
                        del s
                if name not in self.images:
                    self.images[name] = loadStatic(name)
        else:
            for name in names:
                self.images[name] = loadStatic(name)

    def SaveColumns(self):
        for i in [self.userbrowse, self.userlist, self.chatrooms.roomsctrl, self.downloads, self.uploads, self.Searches]:
            i.saveColumns()
        self.np.config.writeConfiguration()

    def OnSearchMethod(self, widget):

        act = False
        search_mode = self.SearchMethod.get_model().get(self.SearchMethod.get_active_iter(), 0)[0]

        if search_mode == _("User"):
            self.UserSearchCombo.show()
            act = True
        else:
            self.UserSearchCombo.hide()

        self.UserSearchCombo.set_sensitive(act)

        act = False
        if search_mode == _("Rooms"):
            act = True
            self.RoomSearchCombo.show()
        else:
            self.RoomSearchCombo.hide()

        self.RoomSearchCombo.set_sensitive(act)

    def CreateRecommendationsWidgets(self):

        self.likes = {}
        self.likeslist = gtk.ListStore(gobject.TYPE_STRING)
        self.likeslist.set_sort_column_id(0, gtk.SortType.ASCENDING)

        cols = utils.InitialiseColumns(
            self.LikesList,
            [_("I like") + ":", 0, "text", self.CellDataFunc]
        )

        cols[0].set_sort_column_id(0)
        self.LikesList.set_model(self.likeslist)

        self.til_popup_menu = popup = utils.PopupMenu(self)

        popup.setup(
            ("#" + _("_Remove this item"), self.OnRemoveThingILike),
            ("#" + _("Re_commendations for this item"), self.OnRecommendItem),
            ("", None),
            ("#" + _("_Search for this item"), self.OnRecommendSearch)
        )

        self.LikesList.connect("button_press_event", self.OnPopupTILMenu)

        self.dislikes = {}
        self.dislikeslist = gtk.ListStore(gobject.TYPE_STRING)
        self.dislikeslist.set_sort_column_id(0, gtk.SortType.ASCENDING)

        cols = utils.InitialiseColumns(
            self.DislikesList,
            [_("I dislike") + ":", 0, "text", self.CellDataFunc]
        )

        cols[0].set_sort_column_id(0)
        self.DislikesList.set_model(self.dislikeslist)

        self.tidl_popup_menu = popup = utils.PopupMenu(self)

        popup.setup(
            ("#" + _("_Remove this item"), self.OnRemoveThingIDislike),
            ("", None),
            ("#" + _("_Search for this item"), self.OnRecommendSearch)
        )

        self.DislikesList.connect("button_press_event", self.OnPopupTIDLMenu)

        cols = utils.InitialiseColumns(
            self.RecommendationsList,
            [_("Item"), 0, "text", self.CellDataFunc],
            [_("Rating"), 75, "text", self.CellDataFunc]
        )

        cols[0].set_sort_column_id(0)
        cols[1].set_sort_column_id(2)

        self.recommendationslist = gtk.ListStore(
            gobject.TYPE_STRING,
            gobject.TYPE_STRING,
            gobject.TYPE_INT
        )
        self.RecommendationsList.set_model(self.recommendationslist)

        self.r_popup_menu = popup = utils.PopupMenu(self)

        popup.setup(
            ("$" + _("I _like this"), self.OnLikeRecommendation),
            ("$" + _("I _don't like this"), self.OnDislikeRecommendation),
            ("#" + _("_Recommendations for this item"), self.OnRecommendRecommendation),
            ("", None),
            ("#" + _("_Search for this item"), self.OnRecommendSearch)
        )

        self.RecommendationsList.connect("button_press_event", self.OnPopupRMenu)

        cols = utils.InitialiseColumns(
            self.UnrecommendationsList,
            [_("Item"), 0, "text", self.CellDataFunc],
            [_("Rating"), 75, "text", self.CellDataFunc]
        )

        cols[0].set_sort_column_id(0)
        cols[1].set_sort_column_id(2)

        self.unrecommendationslist = gtk.ListStore(
            gobject.TYPE_STRING,
            gobject.TYPE_STRING,
            gobject.TYPE_INT
        )
        self.UnrecommendationsList.set_model(self.unrecommendationslist)

        self.ur_popup_menu = popup = utils.PopupMenu(self)

        popup.setup(
            ("$" + _("I _like this"), self.OnLikeRecommendation),
            ("$" + _("I _don't like this"), self.OnDislikeRecommendation),
            ("#" + _("_Recommendations for this item"), self.OnRecommendRecommendation),
            ("", None),
            ("#" + _("_Search for this item"), self.OnRecommendSearch)
        )

        self.UnrecommendationsList.connect("button_press_event", self.OnPopupUnRecMenu)

        statusiconwidth = self.images["offline"].get_width() + 4

        cols = utils.InitialiseColumns(
            self.RecommendationUsersList,
            ["", statusiconwidth, "pixbuf"],
            [_("User"), 100, "text", self.CellDataFunc],
            [_("Speed"), 0, "text", self.CellDataFunc],
            [_("Files"), 0, "text", self.CellDataFunc],
        )

        cols[0].set_sort_column_id(4)
        cols[1].set_sort_column_id(1)
        cols[2].set_sort_column_id(5)
        cols[3].set_sort_column_id(6)

        self.recommendationusers = {}
        self.recommendationuserslist = gtk.ListStore(
            gobject.TYPE_OBJECT,
            gobject.TYPE_STRING,
            gobject.TYPE_STRING,
            gobject.TYPE_STRING,
            gobject.TYPE_INT,
            gobject.TYPE_INT,
            gobject.TYPE_INT
        )
        self.RecommendationUsersList.set_model(self.recommendationuserslist)
        self.recommendationuserslist.set_sort_column_id(1, gtk.SortType.ASCENDING)

        self.ru_popup_menu = popup = utils.PopupMenu(self)
        popup.setup(
            ("#" + _("Send _message"), popup.OnSendMessage),
            ("", None),
            ("#" + _("Show IP a_ddress"), popup.OnShowIPaddress),
            ("#" + _("Get user i_nfo"), popup.OnGetUserInfo),
            ("#" + _("Brow_se files"), popup.OnBrowseUser),
            ("#" + _("Gi_ve privileges"), popup.OnGivePrivileges),
            ("", None),
            ("$" + _("_Add user to list"), popup.OnAddToList),
            ("$" + _("_Ban this user"), popup.OnBanUser),
            ("$" + _("_Ignore this user"), popup.OnIgnoreUser)
        )

        self.RecommendationUsersList.connect("button_press_event", self.OnPopupRUMenu)

    def download_large_folder(self, username, folder, numfiles, msg):
        OptionDialog(
            parent=self.MainWindow,
            title=_("Download %(num)i files?") % {'num': numfiles},
            message=_("Are you sure you wish to download %(num)i files from %(user)s's folder %(folder)s?") % {'num': numfiles, 'user': username, 'folder': folder},
            callback=self.folder_download_response,
            callback_data=msg
        )

    def folder_download_response(self, dialog, response, data):

        if response == gtk.ResponseType.OK:
            self.np.transfers.FolderContentsResponse(data)

        dialog.destroy()

    def on_quit_response(self, dialog, response, data):
        checkbox = dialog.checkbox.get_active()

        if response == gtk.ResponseType.OK:

            if checkbox:
                self.np.config.sections["ui"]["exitdialog"] = 0

            if self.TrayApp.trayicon:
                self.TrayApp.destroy_trayicon()

            self.MainWindow.destroy()

        elif response == gtk.ResponseType.CANCEL:
            pass

        elif response == gtk.ResponseType.REJECT:
            if checkbox:
                self.np.config.sections["ui"]["exitdialog"] = 2
            if self.MainWindow.get_property("visible"):
                self.MainWindow.hide()

        dialog.destroy()

    def on_clear_response(self, dialog, response, direction):

        if response == gtk.ResponseType.OK:
            if direction == "down":
                self.downloads.ClearTransfers(["Queued"])
            elif direction == "up":
                self.uploads.ClearTransfers(["Queued"])

        dialog.destroy()

    def onOpenRoomList(self, dialog, response):
        dialog.destroy()
        if response == gtk.ResponseType.OK:
            self.show_room_list1.set_active(True)

    def OnGetUserInfo(self, widget):
        text = self.UserInfoCombo.get_child().get_text()
        if not text:
            return
        self.LocalUserInfoRequest(text)
        self.UserInfoCombo.get_child().set_text("")

    def OnGetShares(self, widget):
        text = self.UserBrowseCombo.get_child().get_text()
        if not text:
            return
        self.BrowseUser(text)
        self.UserBrowseCombo.get_child().set_text("")

    def OnLoadFromDisk(self, widget):
        sharesdir = os.path.join(self.data_dir, "usershares")
        try:
            if not os.path.exists(sharesdir):
                os.makedirs(sharesdir)
        except Exception as msg:
            log.addwarning(_("Can't create directory '%(folder)s', reported error: %(error)s") % {'folder': sharesdir, 'error': msg})

        shares = ChooseFile(self.MainWindow.get_toplevel(), sharesdir, multiple=True)
        if shares is None:
            return
        for share in shares:
            try:
                import pickle as mypickle
                import bz2
                sharefile = bz2.BZ2File(share)
                mylist = mypickle.load(sharefile)
                sharefile.close()
                if not isinstance(mylist, (list, dict)):
                    raise TypeError("Bad data in file %(sharesdb)s" % {'sharesdb': share})
                username = share.split(os.sep)[-1]
                self.userbrowse.InitWindow(username, None)
                if username in self.userbrowse.users:
                    self.userbrowse.users[username].LoadShares(mylist)
            except Exception as msg:
                log.addwarning(_("Loading Shares from disk failed: %(error)s") % {'error': msg})

    def OnNowPlayingConfigure(self, widget):
        if self.now is None:
            self.now = nowplaying.NowPlaying(self)

        self.now.NowPlaying.show()
        self.now.NowPlaying.deiconify()

    def OnGetPrivateChat(self, widget):
        text = self.UserPrivateCombo.get_child().get_text()
        if not text:
            return
        self.privatechats.SendMessage(text, None, 1)
        self.UserPrivateCombo.get_child().set_text("")

    def button_press(self, widget, event):
        try:

            if event.type == Gdk.EventType.BUTTON_PRESS:
                widget.popup(None, None, None, None, event.button, event.time)

                # Tell calling code that we have handled this event the buck
                # stops here.
                return True
                # Tell calling code that we have not handled this event pass it on.
            return False
        except Exception as e:
            log.addwarning(_("button_press error, %(error)s") % {'error': e})

    def OnPageRemoved(self, MainNotebook, child, page_num):
        name = self.MatchMainNotebox(child)
        self.np.config.sections["ui"]["modes_visible"][name] = 0
        self.OnPageReordered(MainNotebook, child, page_num)

    def OnPageAdded(self, MainNotebook, child, page_num):
        name = self.MatchMainNotebox(child)
        self.np.config.sections["ui"]["modes_visible"][name] = 1
        self.OnPageReordered(MainNotebook, child, page_num)

    def OnPageReordered(self, MainNotebook, child, page_num):
        if self.exiting:
            return

        tabs = []
        for children in self.MainNotebook.get_children():
            tabs.append(self.MatchMainNotebox(children))

        self.np.config.sections["ui"]["modes_order"] = tabs

        if MainNotebook.get_n_pages() == 0:
            MainNotebook.set_show_tabs(False)
        else:
            MainNotebook.set_show_tabs(True)

    def SetMainTabsOrder(self):
        tabs = self.np.config.sections["ui"]["modes_order"]
        order = 0

        for name in tabs:
            tab = self.MatchMainNamePage(name)

            # Ensure that the tab exists (Buddy List tab may be hidden)
            if tab is None or self.MainNotebook.page_num(tab) == -1:
                continue

            self.MainNotebook.reorder_child(tab, order)
            order += 1

    def SetMainTabsVisibility(self):
        visible = self.np.config.sections["ui"]["modes_visible"]

        for name in visible:
            tab = self.MatchMainNamePage(name)
            if tab is None:
                continue

            if not visible[name]:
                if tab not in self.MainNotebook.get_children():
                    continue

                if tab in self.HiddenTabs:
                    continue

                self.HiddenTabs[tab] = self.MainNotebook.get_tab_label(tab)
                num = self.MainNotebook.page_num(tab)
                self.MainNotebook.remove_page(num)

        if self.MainNotebook.get_n_pages() == 0:
            self.MainNotebook.set_show_tabs(False)

    def SetLastSessionTab(self):
        try:
            if self.np.config.sections["ui"]["tab_select_previous"]:
                lasttabid = int(self.np.config.sections["ui"]["last_tab_id"])

                if 0 <= lasttabid <= self.MainNotebook.get_n_pages():
                    self.MainNotebook.set_current_page(lasttabid)
                    return
        except Exception:
            pass

        self.MainNotebook.set_current_page(0)

    def HideTab(self, widget, lista):
        eventbox, child = lista
        tab = self.__dict__[child]

        if tab not in self.MainNotebook.get_children():
            return

        if tab in self.HiddenTabs:
            return

        self.HiddenTabs[tab] = eventbox

        num = self.MainNotebook.page_num(tab)
        self.MainNotebook.remove_page(num)

    def ShowTab(self, widget, lista):
        name, child = lista

        if child in self.MainNotebook.get_children():
            return

        if child not in self.HiddenTabs:
            return

        eventbox = self.HiddenTabs[child]

        self.MainNotebook.append_page(child, eventbox)
        self.MainNotebook.set_tab_reorderable(child, self.np.config.sections["ui"]["tab_reorderable"])

        del self.HiddenTabs[child]

    def on_tab_click(self, widget, event, id, child):
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 3:
            self.__dict__[id].popup(None, None, None, None, event.button, event.time)

        pass

    def BuddiesCombosFill(self, nothing):
        for widget in self.BuddiesComboEntries:
            GLib.idle_add(widget.Fill)

    def RemoveAwayTimer(self, timerid):
        # Check that the away timer hasn't been destroyed already
        # Happens if the timer expires
        context = GLib.MainContext.default()
        if context.find_source_by_id(timerid) is not None:
            GLib.source_remove(timerid)

    def OnAutoAway(self):
        if not self.away:
            self.autoaway = True
            self.OnAway(None)
        return False

    def OnButtonPress(self, widget, event):
        if self.autoaway:
            self.OnAway(None)
            self.autoaway = False
        if self.awaytimerid is not None:
            self.RemoveAwayTimer(self.awaytimerid)

            autoaway = self.np.config.sections["server"]["autoaway"]
            if autoaway > 0:
                self.awaytimerid = GLib.timeout_add(1000 * 60 * autoaway, self.OnAutoAway)
            else:
                self.awaytimerid = None

    def OnKeyPress(self, widget, event):
        self.OnButtonPress(None, None)
        if event.state & (Gdk.ModifierType.MOD1_MASK | Gdk.ModifierType.CONTROL_MASK) != Gdk.ModifierType.MOD1_MASK:
            return False
        for i in range(1, 10):
            if event.keyval == Gdk.keyval_from_name(str(i)):
                self.MainNotebook.set_current_page(i - 1)
                widget.stop_emission_by_name("key_press_event")
                return True
        return False

    def OnNetworkEvent(self, msgs):
        for i in msgs:
            if i.__class__ in self.np.events:
                self.np.events[i.__class__](i)
            else:
                self.logMessage("No handler for class %s %s" % (i.__class__, dir(i)))

    def callback(self, msgs):
        if len(msgs) > 0:
            GLib.idle_add(self.OnNetworkEvent, msgs)

    def networkcallback(self, msgs):
        curtime = time.time()
        for i in msgs[:]:
            if i.__class__ is slskmessages.DownloadFile or i.__class__ is slskmessages.UploadFile:
                self.transfermsgs[i.conn] = i
                msgs.remove(i)
            if i.__class__ is slskmessages.ConnClose:
                msgs = self.postTransferMsgs(msgs, curtime)
        if curtime - self.transfermsgspostedtime > 1.0:
            msgs = self.postTransferMsgs(msgs, curtime)
        if len(msgs) > 0:
            GLib.idle_add(self.OnNetworkEvent, msgs)

    def postTransferMsgs(self, msgs, curtime):
        trmsgs = []
        for (key, value) in self.transfermsgs.items():
            trmsgs.append(value)
        msgs = trmsgs + msgs
        self.transfermsgs = {}
        self.transfermsgspostedtime = curtime
        return msgs

    def CellDataFunc(self, column, cellrenderer, model, iter, dummy="dummy"):
        colour = self.np.config.sections["ui"]["search"]
        if colour == "":
            colour = None
        cellrenderer.set_property("foreground", colour)

    def ChangeListFont(self, listview, font):
        for c in listview.get_columns():
            for r in c.get_cells():
                if type(r) in (gtk.CellRendererText, gtk.CellRendererCombo):
                    r.set_property("font", font)

    def UpdateColours(self, first=0):
        if first:
            self.tag_log = self.LogWindow.get_buffer().create_tag()

        color = self.np.config.sections["ui"]["chatremote"]

        if color == "":
            color = None

        self.tag_log.set_property("foreground", color)

        font = self.np.config.sections["ui"]["chatfont"]
        self.tag_log.set_property("font", font)

        # self.ChangeListFont( self.UserList, self.frame.np.config.sections["ui"]["listfont"])
        for listview in [
            self.userlist.UserList,
            self.RecommendationsList,
            self.UnrecommendationsList,
            self.RecommendationUsersList,
            self.LikesList,
            self.DislikesList,
            self.roomlist.RoomsList
        ]:
            self.ChangeListFont(listview, self.np.config.sections["ui"]["listfont"])

        self.SetTextBG(self.UserPrivateCombo.get_child())
        self.SetTextBG(self.UserInfoCombo.get_child())
        self.SetTextBG(self.UserBrowseCombo.get_child())
        self.SetTextBG(self.SearchEntry)
        self.SetTextBG(self.AddLikeEntry)
        self.SetTextBG(self.AddDislikeEntry)

    def SetTextBG(self, widget, bgcolor="", fgcolor=""):
        if bgcolor == "" and self.np.config.sections["ui"]["textbg"] == "":
            rgba = None
        else:
            if bgcolor == "":
                bgcolor = self.np.config.sections["ui"]["textbg"]
            rgba = Gdk.RGBA()
            rgba.parse(bgcolor)

        widget.override_background_color(gtk.StateFlags.NORMAL, rgba)
        widgetlist = [gtk.Entry, gtk.SpinButton]
        if type(widget) in widgetlist:
            if fgcolor != "":
                rgba = Gdk.RGBA()
                rgba.parse(fgcolor)
            elif fgcolor == "" and self.np.config.sections["ui"]["inputcolor"] == "":
                rgba = None
            elif fgcolor == "" and self.np.config.sections["ui"]["inputcolor"] != "":
                fgcolor = self.np.config.sections["ui"]["inputcolor"]
                rgba = Gdk.RGBA()
                rgba.parse(fgcolor)

            widget.override_color(gtk.StateFlags.NORMAL, rgba)

        if type(widget) is gtk.TreeView:
            colour = self.np.config.sections["ui"]["search"]
            if colour == "":
                colour = None
            for c in widget.get_columns():
                for r in c.get_cells():
                    if type(r) in (gtk.CellRendererText, gtk.CellRendererCombo):
                        r.set_property("foreground", colour)

    def PopupMessage(self, popup):
        dialog = gtk.MessageDialog(type=gtk.MessageType.WARNING, buttons=gtk.ButtonsType.OK, message_format=popup.title)
        dialog.format_secondary_text(popup.message)
        dialog.connect('response', lambda dialog, response: dialog.destroy())
        dialog.show()

    def logCallback(self, timestamp, level, msg):
        GLib.idle_add(self.updateLog, msg, level, priority=GLib.PRIORITY_DEFAULT)

    def logMessage(self, msg, debugLevel=0):
        log.add(msg, debugLevel)

    def updateLog(self, msg, debugLevel=None):
        '''For information about debug levels see
        pydoc pynicotine.logfacility.logger.add
        '''

        logcollapsed = self.np.config.sections["logging"]["logcollapsed"]

        if logcollapsed:
            # Make sure we don't attempt to scroll in the log window
            # if it's hidden, to prevent those nasty GTK warnings :)
            shouldscroll = False
        else:
            shouldscroll = True

        if self.np.config.sections["logging"]["debug"]:
            if debugLevel in (None, 0) or debugLevel in self.np.config.sections["logging"]["debugmodes"]:
                AppendLine(self.LogWindow, msg, self.tag_log, scroll=shouldscroll)

                if logcollapsed:
                    self.SetStatusText(msg)
        else:
            if debugLevel in (None, 0, 1):
                try:
                    AppendLine(self.LogWindow, msg, self.tag_log, scroll=shouldscroll)

                    if logcollapsed:
                        self.SetStatusText(msg)
                except Exception as e:
                    print(e)
        return False

    def SetStatusText(self, msg):
        self.Statusbar.pop(self.status_context_id)
        self.Statusbar.push(self.status_context_id, msg)
        self.Statusbar.set_tooltip_text(msg)

    def OnWindowChange(self, widget, blag):
        (width, height) = self.MainWindow.get_size()
        self.np.config.sections["ui"]["height"] = height
        self.np.config.sections["ui"]["width"] = width
        (xpos, ypos) = self.MainWindow.get_position()
        self.np.config.sections["ui"]["xposition"] = xpos
        self.np.config.sections["ui"]["yposition"] = ypos

    def OnDestroy(self, widget):
        self.np.config.sections["ui"]["maximized"] = self.MainWindow.is_maximized()

        self.SaveColumns()

        self.np.config.sections["ui"]["last_tab_id"] = self.MainNotebook.get_current_page()

        self.np.config.sections["privatechat"]["users"] = list(self.privatechats.users.keys())
        self.np.protothread.abort()
        self.np.StopTimers()

        if not self.manualdisconnect:
            self.OnDisconnect(None)

        self.np.config.writeConfig()

        # Cleaning up the trayicon
        if self.TrayApp.trayicon:
            self.TrayApp.destroy_trayicon()

        # Closing up all shelves db
        for db in [
            "sharedfiles", "sharedfilesstreams", "wordindex",
            "fileindex", "sharedmtimes",
            "bsharedfiles", "bsharedfilesstreams", "bwordindex",
            "bfileindex", "bsharedmtimes"
        ]:
            self.np.config.sections["transfers"][db].close()

    def OnConnect(self, widget):

        self.TrayApp.tray_status["status"] = "connect"
        self.TrayApp.SetImage()

        if self.np.serverconn is not None:
            return

        if widget != -1:
            while not self.np.queue.empty():
                self.np.queue.get(0)

        self.SetUserStatus("...")
        server = self.np.config.sections["server"]["server"]
        self.SetStatusText(_("Connecting to %(host)s:%(port)s") % {'host': server[0], 'port': server[1]})
        self.np.queue.put(slskmessages.ServerConn(None, server))

        if self.np.servertimer is not None:
            self.np.servertimer.cancel()
            self.np.servertimer = None

    def OnDisconnect(self, event):
        self.disconnect1.set_sensitive(0)
        self.manualdisconnect = 1
        self.np.queue.put(slskmessages.ConnClose(self.np.serverconn))

    def FetchUserListStatus(self):
        for i in self.np.config.sections["server"]["userlist"]:
            user = i[0]
            self.np.queue.put(slskmessages.AddUser(user))

        return False

    def ConnClose(self, conn, addr):

        if self.awaytimerid is not None:
            self.RemoveAwayTimer(self.awaytimerid)
            self.awaytimerid = None

        if self.autoaway:
            self.autoaway = self.away = False

        self.SetWidgetOnlineStatus(False)

        self.SetUserStatus(_("Offline"))

        self.TrayApp.tray_status["status"] = "disconnect"
        self.TrayApp.SetImage()

        self.Searches.WishList.interval = 0
        self.chatrooms.ConnClose()
        self.privatechats.ConnClose()
        self.Searches.WishList.conn_close()
        self.uploads.ConnClose()
        self.downloads.ConnClose()
        self.userlist.ConnClose()
        self.userinfo.ConnClose()
        self.userbrowse.ConnClose()

    def SetWidgetOnlineStatus(self, status):

        self.connect1.set_sensitive(not status)
        self.disconnect1.set_sensitive(status)
        self.awayreturn1.set_sensitive(status)
        self.check_privileges1.set_sensitive(status)
        self.get_privileges1.set_sensitive(status)
        self.roomlist.RoomsList.set_sensitive(status)
        self.roomlist.SearchRooms.set_sensitive(status)
        self.roomlist.RefreshButton.set_sensitive(status)
        self.roomlist.AcceptPrivateRoom.set_sensitive(status)
        self.UserPrivateCombo.set_sensitive(status)
        self.sPrivateChatButton.set_sensitive(status)
        self.UserBrowseCombo.set_sensitive(status)
        self.sSharesButton.set_sensitive(status)
        self.UserInfoCombo.set_sensitive(status)
        self.sUserinfoButton.set_sensitive(status)

        self.UserSearchCombo.set_sensitive(status)
        self.SearchEntryCombo.set_sensitive(status)

        self.SearchButton.set_sensitive(status)
        self.SimilarUsersButton.set_sensitive(status)
        self.GlobalRecommendationsButton.set_sensitive(status)
        self.RecommendationsButton.set_sensitive(status)

        self.DownloadButtons.set_sensitive(status)
        self.UploadButtons.set_sensitive(status)

    def ConnectError(self, conn):

        self.SetWidgetOnlineStatus(False)

        self.SetUserStatus(_("Offline"))

        self.TrayApp.tray_status["status"] = "disconnect"
        self.TrayApp.SetImage()

        self.uploads.ConnClose()
        self.downloads.ConnClose()

    def SetUserStatus(self, status):
        self.UserStatus.pop(self.user_context_id)
        self.UserStatus.push(self.user_context_id, status)

    def SetSocketStatus(self, status):
        self.SocketStatus.pop(self.socket_context_id)
        self.SocketStatus.push(self.socket_context_id, self.socket_template % {'current': status, 'limit': slskproto.MAXFILELIMIT})

    def InitInterface(self, msg):

        if self.away == 0:
            self.SetUserStatus(_("Online"))

            self.TrayApp.tray_status["status"] = "connect"
            self.TrayApp.SetImage()

            autoaway = self.np.config.sections["server"]["autoaway"]

            if autoaway > 0:
                self.awaytimerid = GLib.timeout_add(1000 * 60 * autoaway, self.OnAutoAway)
            else:
                self.awaytimerid = None
        else:
            self.SetUserStatus(_("Away"))

            self.TrayApp.tray_status["status"] = "away"
            self.TrayApp.SetImage()

        self.SetWidgetOnlineStatus(True)

        self.uploads.InitInterface(self.np.transfers.uploads)
        self.downloads.InitInterface(self.np.transfers.downloads)
        GLib.idle_add(self.FetchUserListStatus)

        if msg.banner != "":
            AppendLine(self.LogWindow, msg.banner, self.tag_log)

        return self.privatechats, self.chatrooms, self.userinfo, self.userbrowse, self.Searches, self.downloads, self.uploads, self.userlist

    def GetStatusImage(self, status):
        if status == 1:
            return self.images["away"]
        elif status == 2:
            return self.images["online"]
        else:
            return self.images["offline"]

    def HasUserFlag(self, user, flag):
        if flag not in self.flag_images:
            self.GetFlagImage(flag)
        if flag not in self.flag_images:
            return
        self.flag_users[user] = flag
        self.chatrooms.roomsctrl.SetUserFlag(user, flag)
        self.userlist.SetUserFlag(user, flag)

    def GetUserFlag(self, user):
        if user not in self.flag_users:
            for i in self.np.config.sections["server"]["userlist"]:
                if user == i[0] and i[6] is not None:
                    return i[6]
            return "flag_"
        else:
            return self.flag_users[user]

    def GetFlagImage(self, flag):

        if flag is None:
            return

        if flag not in self.flag_images:
            if hasattr(imagedata, flag):
                img = None
                try:
                    loader = GdkPixbuf.PixbufLoader()
                    data = getattr(imagedata, flag)
                    loader.write(data)
                    loader.close()
                    img = loader.get_pixbuf()
                except Exception as e:
                    log.addwarning(_("Error loading image for %(flag)s: %(error)s") % {'flag': flag, 'error': e})
                self.flag_images[flag] = img
                return img
            else:
                return None
        else:
            return self.flag_images[flag]

    def OnShowDebug(self, widget):
        if not self.startup:
            self.np.config.sections["logging"]["debug"] = self.show_debug_info1.get_active()
        if self.show_debug_info1.get_active():
            self.debugButtonsBox.show()
        else:
            self.debugButtonsBox.hide()

    def OnAway(self, widget):

        self.away = (self.away + 1) % 2

        if self.away == 0:
            self.SetUserStatus(_("Online"))

            self.TrayApp.tray_status["status"] = "connect"
            self.TrayApp.SetImage()
        else:
            self.SetUserStatus(_("Away"))

            self.TrayApp.tray_status["status"] = "away"
            self.TrayApp.SetImage()

        self.np.queue.put(slskmessages.SetStatus(self.away and 1 or 2))
        self.privatechats.UpdateColours()

    def OnExit(self, widget):
        self.exiting = 1
        self.MainWindow.destroy()

    def OnSearch(self, widget):
        self.Searches.OnSearch()

    def OnClearSearchHistory(self, widget):
        self.Searches.OnClearSearchHistory()

    def ChatRequestIcon(self, status=0, widget=None):

        if status == 1 and not self.got_focus:
            self.MainWindow.set_icon(self.images["hilite"])

        if self.MainNotebook.get_current_page() == self.MainNotebook.page_num(self.chathbox):
            return

        tablabel = self.GetTabLabel(self.ChatTabLabel)
        if not tablabel:
            return

        if status == 0:
            if tablabel.get_image() == self.images["hilite"]:
                return

        tablabel.set_image(status == 1 and self.images["hilite"] or self.images["hilite3"])
        tablabel.set_text_color(status + 1)

    def GetTabLabel(self, TabLabel):

        tablabel = None

        if type(TabLabel) is ImageLabel:
            tablabel = TabLabel
        elif type(TabLabel) is gtk.EventBox:
            tablabel = TabLabel.get_child()

        return tablabel

    def RequestIcon(self, TabLabel, widget=None):
        if TabLabel == self.PrivateChatTabLabel and not self.got_focus:
            self.MainWindow.set_icon(self.images["hilite"])
        tablabel = self.GetTabLabel(TabLabel)
        if not tablabel:
            return

        if self.current_tab != TabLabel:
            tablabel.set_image(self.images["hilite"])
            tablabel.set_text_color(2)

    def OnSwitchPage(self, notebook, page, page_nr):

        tabLabels = []
        tabs = self.MainNotebook.get_children()

        for i in tabs:
            tabLabels.append(self.MainNotebook.get_tab_label(i))

        l = tabLabels[page_nr]  # noqa: E741

        compare = {
            self.ChatTabLabel: self.ChatNotebook,
            self.PrivateChatTabLabel: self.PrivatechatNotebook,
            self.DownloadsTabLabel: None,
            self.UploadsTabLabel: None,
            self.SearchTabLabel: self.SearchNotebook,
            self.UserInfoTabLabel: self.UserInfoNotebook,
            self.UserBrowseTabLabel: self.UserBrowseNotebook,
            self.InterestsTabLabel: None
        }

        if "BuddiesTabLabel" in self.__dict__:
            compare[self.BuddiesTabLabel] = None

        n = compare[l]
        self.current_tab = l

        if l is not None:
            if type(l) is ImageLabel:
                l.set_image(self.images["empty"])
                l.set_text_color(0)
            elif type(l) is gtk.EventBox:
                l.get_child().set_image(self.images["empty"])
                l.get_child().set_text_color(0)

        if n is not None:
            n.popup_disable()
            n.popup_enable()
            if n.get_current_page() != -1:
                n.dismiss_icon(n, None, n.get_current_page())

        if page_nr == self.MainNotebook.page_num(self.chathbox):
            if self.chatrooms:
                p = n.get_current_page()
                self.chatrooms.roomsctrl.OnSwitchPage(n.Notebook, None, p, 1)
        elif page_nr == self.MainNotebook.page_num(self.privatevbox):
            p = n.get_current_page()
            if "privatechats" in self.__dict__:
                self.privatechats.OnSwitchPage(n.Notebook, None, p, 1)
        elif page_nr == self.MainNotebook.page_num(self.uploadsvbox):
            self.uploads._update()
        elif page_nr == self.MainNotebook.page_num(self.downloadsvbox):
            self.downloads._update()

    def UpdateBandwidth(self):

        def _bandwidth(line):
            bandwidth = 0.0

            for i in line:
                speed = i.speed
                if speed is not None:
                    bandwidth = bandwidth + speed

            return bandwidth

        def _users(transfers, users):
            return len(users), len(transfers)

        if self.np.transfers is not None:
            down = _bandwidth(self.np.transfers.downloads)
            up = _bandwidth(self.np.transfers.uploads)
            total_usersdown, filesdown = _users(self.np.transfers.downloads, self.downloads.users)
            total_usersup, filesup = _users(self.np.transfers.uploads, self.uploads.users)
        else:
            down = up = 0.0
            filesup = filesdown = total_usersdown = total_usersup = 0

        self.DownloadUsers.set_text(self.users_template % total_usersdown)
        self.UploadUsers.set_text(self.users_template % total_usersup)
        self.DownloadFiles.set_text(self.files_template % filesdown)
        self.UploadFiles.set_text(self.files_template % filesup)

        self.DownStatus.pop(self.down_context_id)
        self.UpStatus.pop(self.up_context_id)
        self.DownStatus.push(self.down_context_id, self.down_template % {'num': total_usersdown, 'speed': down})
        self.UpStatus.push(self.up_context_id, self.up_template % {'num': total_usersup, 'speed': up})

        self.TrayApp.SetToolTip(self.tray_tooltip_template % {'speeddown': down, 'speedup': up})

    def BanUser(self, user):
        if self.np.transfers is not None:
            self.np.transfers.BanUser(user)

    def UserIpIsBlocked(self, user):
        for ip, username in list(self.np.config.sections["server"]["ipblocklist"].items()):
            if user == username:
                return True
        return False

    def BlockedUserIp(self, user):
        for ip, username in list(self.np.config.sections["server"]["ipblocklist"].items()):
            if user == username:
                return ip
        return None

    def UserIpIsIgnored(self, user):
        for ip, username in list(self.np.config.sections["server"]["ipignorelist"].items()):
            if user == username:
                return True
        return False

    def IgnoredUserIp(self, user):
        for ip, username in list(self.np.config.sections["server"]["ipignorelist"].items()):
            if user == username:
                return ip
        return None

    def IgnoreIP(self, ip):
        if ip is None or ip == "" or ip.count(".") != 3:
            return
        ipignorelist = self.np.config.sections["server"]["ipignorelist"]
        if ip not in ipignorelist:
            ipignorelist[ip] = ""
            self.np.config.writeConfiguration()

            if self.settingswindow is not None:
                self.settingswindow.pages["Ignore List"].SetSettings(self.np.config.sections)

    def OnIgnoreIP(self, user):
        if user not in self.np.users or type(self.np.users[user].addr) is not tuple:
            if user not in self.np.ipignore_requested:
                self.np.ipignore_requested[user] = 0
            self.np.queue.put(slskmessages.GetPeerAddress(user))
            return
        ipignorelist = self.np.config.sections["server"]["ipignorelist"]
        ip, port = self.np.users[user].addr
        if ip not in ipignorelist or self.np.config.sections["server"]["ipignorelist"][ip] != user:
            self.np.config.sections["server"]["ipignorelist"][ip] = user
            self.np.config.writeConfiguration()

            if self.settingswindow is not None:
                self.settingswindow.pages["Ignore List"].SetSettings(self.np.config.sections)

    def OnUnIgnoreIP(self, user):
        ipignorelist = self.np.config.sections["server"]["ipignorelist"]
        if self.UserIpIsIgnored(user):
            ip = self.IgnoredUserIp(user)
            if ip is not None:
                del ipignorelist[ip]
                self.np.config.writeConfiguration()

                if self.settingswindow is not None:
                    self.settingswindow.pages["Ignore List"].SetSettings(self.np.config.sections)
                return True

        if user not in self.np.users:
            if user not in self.np.ipignore_requested:
                self.np.ipignore_requested[user] = 1
            self.np.queue.put(slskmessages.GetPeerAddress(user))
            return

        if not type(self.np.users[user].addr) is tuple:
            return

        ip, port = self.np.users[user].addr
        if ip in ipignorelist:
            del ipignorelist[ip]
            self.np.config.writeConfiguration()

            if self.settingswindow is not None:
                self.settingswindow.pages["Ignore List"].SetSettings(self.np.config.sections)

    def OnBlockUser(self, user):
        if user not in self.np.users or type(self.np.users[user].addr) is not tuple:
            if user not in self.np.ipblock_requested:
                self.np.ipblock_requested[user] = 0
            self.np.queue.put(slskmessages.GetPeerAddress(user))
            return

        ip, port = self.np.users[user].addr
        if ip not in self.np.config.sections["server"]["ipblocklist"] or self.np.config.sections["server"]["ipblocklist"][ip] != user:
            self.np.config.sections["server"]["ipblocklist"][ip] = user
            self.np.config.writeConfiguration()

            if self.settingswindow is not None:
                self.settingswindow.pages["Ban List"].SetSettings(self.np.config.sections)

    def OnUnBlockUser(self, user):
        if self.UserIpIsBlocked(user):
            ip = self.BlockedUserIp(user)
            if ip is not None:
                del self.np.config.sections["server"]["ipblocklist"][ip]
                self.np.config.writeConfiguration()

                if self.settingswindow is not None:
                    self.settingswindow.pages["Ban List"].SetSettings(self.np.config.sections)
                return True

        if user not in self.np.users:
            if user not in self.np.ipblock_requested:
                self.np.ipblock_requested[user] = 1
            self.np.queue.put(slskmessages.GetPeerAddress(user))
            return

        if not type(self.np.users[user].addr) is tuple:
            return

        ip, port = self.np.users[user].addr
        if ip in self.np.config.sections["server"]["ipblocklist"]:
            del self.np.config.sections["server"]["ipblocklist"][ip]
            self.np.config.writeConfiguration()

            if self.settingswindow is not None:
                self.settingswindow.pages["Ban List"].SetSettings(self.np.config.sections)

    def UnbanUser(self, user):
        if user in self.np.config.sections["server"]["banlist"]:
            self.np.config.sections["server"]["banlist"].remove(user)
            self.np.config.writeConfiguration()

    def IgnoreUser(self, user):
        if user not in self.np.config.sections["server"]["ignorelist"]:
            self.np.config.sections["server"]["ignorelist"].append(user)
            self.np.config.writeConfiguration()

    def UnignoreUser(self, user):
        if user in self.np.config.sections["server"]["ignorelist"]:
            self.np.config.sections["server"]["ignorelist"].remove(user)
            self.np.config.writeConfiguration()

    def OnRescan(self, widget=None, rebuild=False):

        if self.rescanning:
            return

        self.rescanning = 1

        self.rescan_public.set_sensitive(False)
        self.browse_public_shares.set_sensitive(False)

        self.logMessage(_("Rescanning started"))

        shared = self.np.config.sections["transfers"]["shared"][:]

        if self.np.config.sections["transfers"]["sharedownloaddir"]:
            shared.append((_('Downloaded'), self.np.config.sections["transfers"]["downloaddir"]))

        cleanedshares = []
        for combo in shared:
            if combo not in cleanedshares:
                cleanedshares.append(combo)

        msg = slskmessages.RescanShares(cleanedshares, lambda: None)
        _thread.start_new_thread(self.np.shares.RescanShares, (msg, rebuild))

    def OnBuddyRescan(self, widget=None, rebuild=False):

        if self.brescanning:
            return

        self.brescanning = 1

        self.rescan_buddy.set_sensitive(False)
        self.browse_buddy_shares.set_sensitive(False)

        self.logMessage(_("Rescanning Buddy Shares started"))

        shared = self.np.config.sections["transfers"]["buddyshared"][:] + self.np.config.sections["transfers"]["shared"][:]

        if self.np.config.sections["transfers"]["sharedownloaddir"]:
            shared.append((_('Downloaded'), self.np.config.sections["transfers"]["downloaddir"]))

        cleanedshares = []
        for i in shared:
            if i not in cleanedshares:
                cleanedshares.append(i)

        msg = slskmessages.RescanBuddyShares(cleanedshares, lambda: None)
        _thread.start_new_thread(self.np.shares.RescanBuddyShares, (msg, rebuild))

    def _BuddyRescanFinished(self, files, streams, wordindex, fileindex, mtimes):

        self.np.config.setBuddyShares(files, streams, wordindex, fileindex, mtimes)

        if self.np.config.sections["transfers"]["enablebuddyshares"]:
            self.rescan_buddy.set_sensitive(True)
            self.browse_buddy_shares.set_sensitive(True)

        if self.np.transfers is not None:
            self.np.shares.sendNumSharedFoldersFiles()

        self.brescanning = 0
        self.logMessage(_("Rescanning Buddy Shares finished"))

        self.BuddySharesProgress.hide()

        self.np.shares.CompressShares("buddy")

    def _RescanFinished(self, files, streams, wordindex, fileindex, mtimes):

        self.np.config.setShares(files, streams, wordindex, fileindex, mtimes)

        if self.np.config.sections["transfers"]["shared"]:
            self.rescan_public.set_sensitive(True)
            self.browse_public_shares.set_sensitive(True)

        self.rescanning = 0
        self.logMessage(_("Rescanning finished"))

        self.SharesProgress.hide()

        self.np.shares.CompressShares("normal")

        if self.np.transfers is not None:
            self.np.shares.sendNumSharedFoldersFiles()

    def RescanFinished(self, files, streams, wordindex, fileindex, mtimes, type):
        if type == "buddy":
            GLib.idle_add(self._BuddyRescanFinished, files, streams, wordindex, fileindex, mtimes)
        elif type == "normal":
            GLib.idle_add(self._RescanFinished, files, streams, wordindex, fileindex, mtimes)

    def OnSettingsShares(self, widget):
        self.OnSettings(widget, 'Shares')

    def OnSettingsSearches(self, widget):
        self.OnSettings(widget, 'Searches')

    def OnSettingsDownloads(self, widget):
        self.OnSettings(widget, 'Downloads')

    def OnSettingsUploads(self, widget):
        self.OnSettings(widget, 'Uploads')

    def OnSettingsUserinfo(self, widget):
        self.OnSettings(widget, 'User Info')

    def OnSettingsLogging(self, widget):
        self.OnSettings(widget, 'Logging')

    def OnSettingsIgnore(self, widget):
        self.OnSettings(widget, 'Ingore List')

    def OnSettingsBanIgnore(self, widget):
        self.OnSettings(widget, 'Ban List')

    def OnFastConfigure(self, widget, show=True):
        if self.fastconfigure is None:
            self.fastconfigure = FastConfigureAssistant(self)

        if self.settingswindow is not None and self.settingswindow.SettingsWindow.get_property("visible"):
            return

        if show:
            self.fastconfigure.show()

    def OnSettings(self, widget, page=None):
        if self.settingswindow is None:
            self.settingswindow = SettingsWindow(self)
            self.settingswindow.SettingsWindow.connect("settings-closed", self.OnSettingsClosed)

        if self.fastconfigure is not None and self.fastconfigure.window.get_property("visible"):
            return

        self.settingswindow.SetSettings(self.np.config.sections)
        if page:
            self.settingswindow.SwitchToPage(page)
        self.settingswindow.SettingsWindow.show()
        self.settingswindow.SettingsWindow.deiconify()

    def OnSettingsClosed(self, widget, msg):

        if msg == "cancel":
            self.settingswindow.SettingsWindow.hide()
            return

        output = self.settingswindow.GetSettings()

        if type(output) is not tuple:
            return

        if msg == "ok":
            self.settingswindow.SettingsWindow.hide()

        needrescan, needcolors, needcompletion, config = output

        for (key, data) in list(config.items()):
            self.np.config.sections[key].update(data)

        config = self.np.config.sections

        # Write utils.py options
        utils.DECIMALSEP = config["ui"]["decimalsep"]
        utils.CATCH_URLS = config["urls"]["urlcatching"]
        utils.HUMANIZE_URLS = config["urls"]["humanizeurls"]
        utils.PROTOCOL_HANDLERS = config["urls"]["protocols"].copy()
        utils.PROTOCOL_HANDLERS["slsk"] = self.OnSoulSeek
        utils.USERNAMEHOTSPOTS = config["ui"]["usernamehotspots"]
        uselimit = config["transfers"]["uselimit"]
        uploadlimit = config["transfers"]["uploadlimit"]
        limitby = config["transfers"]["limitby"]

        if config["transfers"]["geoblock"]:
            panic = config["transfers"]["geopanic"]
            cc = config["transfers"]["geoblockcc"]
            self.np.queue.put(slskmessages.SetGeoBlock([panic, cc]))
        else:
            self.np.queue.put(slskmessages.SetGeoBlock(None))

        self.np.queue.put(slskmessages.SetUploadLimit(uselimit, uploadlimit, limitby))
        self.np.queue.put(slskmessages.SetDownloadLimit(config["transfers"]["downloadlimit"]))
        self.np.ToggleRespondDistributed(None, settings=True)

        if self.SearchNotebook:
            self.SearchNotebook.maxdisplayedresults = config["searches"]["max_displayed_results"]
            self.SearchNotebook.maxstoredresults = config["searches"]["max_stored_results"]

        # Modify GUI
        self.UpdateDownloadFilters()
        self.np.config.writeConfiguration()

        if not config["ui"]["trayicon"] and self.TrayApp.IsTrayIconVisible():
            self.TrayApp.destroy_trayicon()
        elif config["ui"]["trayicon"] and not self.TrayApp.IsTrayIconVisible():
            self.TrayApp.Load()
            self.TrayApp.Draw()

        if needcompletion:
            self.chatrooms.roomsctrl.UpdateCompletions()
            self.privatechats.UpdateCompletions()

        if needcolors:
            self.chatrooms.roomsctrl.UpdateColours()
            self.privatechats.UpdateColours()
            self.Searches.UpdateColours()
            self.downloads.UpdateColours()
            self.uploads.UpdateColours()
            self.userinfo.UpdateColours()
            self.userbrowse.UpdateColours()
            self.settingswindow.UpdateColours()
            self.userlist.UpdateColours()
            self.UpdateColours()

        self.OnShowChatButtons()

        for w in [self.ChatNotebook, self.PrivatechatNotebook, self.UserInfoNotebook, self.UserBrowseNotebook, self.SearchNotebook]:
            w.set_tab_closers(config["ui"]["tabclosers"])
            w.set_reorderable(config["ui"]["tab_reorderable"])
            w.show_images(config["notifications"]["notification_tab_icons"])
            w.set_text_colors(None)

        try:
            for tab in self.MainNotebook.get_children():
                self.MainNotebook.set_tab_reorderable(tab, config["ui"]["tab_reorderable"])
        except Exception:
            # Old gtk
            pass

        tabLabels = [
            self.ChatTabLabel,
            self.PrivateChatTabLabel,
            self.DownloadsTabLabel,
            self.UploadsTabLabel,
            self.SearchTabLabel,
            self.UserInfoTabLabel,
            self.UserBrowseTabLabel,
            self.InterestsTabLabel
        ]

        if "BuddiesTabLabel" in self.__dict__:
            tabLabels.append(self.BuddiesTabLabel)

        for label_tab in tabLabels:
            if type(label_tab) is ImageLabel:
                label_tab.show_image(config["notifications"]["notification_tab_icons"])
                label_tab.set_text_color(None)
            elif type(label_tab) is gtk.EventBox:
                label_tab.get_child().show_image(config["notifications"]["notification_tab_icons"])
                label_tab.get_child().set_text_color(None)

        self.SetTabPositions()

        if self.np.transfers is not None:
            self.np.transfers.checkUploadQueue()

        if needrescan:
            self.needrescan = True

        if msg == "ok" and self.needrescan:

            self.needrescan = False

            # Rescan public shares if needed
            if not self.np.config.sections["transfers"]["friendsonly"]:
                self.OnRescan()

            # Rescan buddy shares if needed
            if self.np.config.sections["transfers"]["enablebuddyshares"]:
                self.OnBuddyRescan()

        ConfigUnset = self.np.config.needConfig()

        if ConfigUnset > 1:
            if self.np.transfers is not None:
                self.connect1.set_sensitive(0)
            self.OnFastConfigure(None)
        else:
            if self.np.transfers is None:
                self.connect1.set_sensitive(1)

    def OnChangePassword(self, password):
        self.np.queue.put(slskmessages.ChangePassword(password))

    def OnBackupConfig(self, widget=None):
        response = SaveFile(
            self.MainWindow.get_toplevel(),
            os.path.dirname(self.np.config.filename),
            title="Pick a filename for config backup, or cancel to use a timestamp"
        )
        if response:
            error, message = self.np.config.writeConfigBackup(response[0])
        else:
            error, message = self.np.config.writeConfigBackup()
        if error:
            self.logMessage("Error backing up config: %s" % message)
        else:
            self.logMessage("Config backed up to: %s" % message)

    def AutoReplace(self, message):
        if self.np.config.sections["words"]["replacewords"]:
            autoreplaced = self.np.config.sections["words"]["autoreplaced"]
            for word, replacement in list(autoreplaced.items()):
                message = message.replace(word, replacement)

        return message

    def CensorChat(self, message):
        if self.np.config.sections["words"]["censorwords"]:
            filler = self.np.config.sections["words"]["censorfill"]
            censored = self.np.config.sections["words"]["censored"]
            for word in censored:
                message = message.replace(word, filler * len(word))

        return message

    def getTabPosition(self, string):
        if string in ("Top", "top", _("Top")):
            position = gtk.PositionType.TOP
        elif string in ("Bottom", "bottom", _("Bottom")):
            position = gtk.PositionType.BOTTOM
        elif string in ("Left", "left", _("Left")):
            position = gtk.PositionType.LEFT
        elif string in ("Right", "right", _("Right")):
            position = gtk.PositionType.RIGHT
        else:
            position = gtk.PositionType.TOP
        return position

    def SetTabPositions(self):

        ui = self.np.config.sections["ui"]

        self.ChatNotebook.set_tab_pos(self.getTabPosition(ui["tabrooms"]))
        self.ChatNotebook.set_tab_angle(ui["labelrooms"])

        self.MainNotebook.set_tab_pos(self.getTabPosition(ui["tabmain"]))

        for label_tab in [
            self.ChatTabLabel,
            self.PrivateChatTabLabel,
            self.SearchTabLabel,
            self.UserInfoTabLabel,
            self.DownloadsTabLabel,
            self.UploadsTabLabel,
            self.UserBrowseTabLabel,
            self.InterestsTabLabel
        ]:
            label_tab.get_child().set_angle(ui["labelmain"])

        if "BuddiesTabLabel" in self.__dict__:
            self.BuddiesTabLabel.set_angle(ui["labelmain"])

        self.PrivatechatNotebook.set_tab_pos(self.getTabPosition(ui["tabprivate"]))
        self.PrivatechatNotebook.set_tab_angle(ui["labelprivate"])
        self.UserInfoNotebook.set_tab_pos(self.getTabPosition(ui["tabinfo"]))
        self.UserInfoNotebook.set_tab_angle(ui["labelinfo"])
        self.UserBrowseNotebook.set_tab_pos(self.getTabPosition(ui["tabbrowse"]))
        self.UserBrowseNotebook.set_tab_angle(ui["labelbrowse"])
        self.SearchNotebook.set_tab_pos(self.getTabPosition(ui["tabsearch"]))
        self.SearchNotebook.set_tab_angle(ui["labelsearch"])

    def CreateIconButton(self, icon, icontype, callback, label=None):
        button = gtk.Button()
        button.connect_object("clicked", callback, "")
        button.show()

        Alignment = gtk.Alignment(xalign=0.5, yalign=0.5, xscale=0, yscale=0)
        Alignment.show()

        Hbox = gtk.Box.new(gtk.Orientation.HORIZONTAL, 2)
        Hbox.show()
        Hbox.set_spacing(2)

        image = gtk.Image()

        if icontype == "stock":
            image.set_from_stock(icon, 4)
        else:
            image.set_from_pixbuf(icon)

        image.show()
        Hbox.pack_start(image, False, False, 0)
        Alignment.add(Hbox)
        if label:
            Label = gtk.Label.new(label)
            Label.show()
            Hbox.pack_start(Label, False, False, 0)
        button.add(Alignment)

        return button

    def UpdateDownloadFilters(self):
        proccessedfilters = []
        outfilter = "(\\\\("
        failed = {}
        df = self.np.config.sections["transfers"]["downloadfilters"]
        df.sort()
        # Get Filters from config file and check their escaped status
        # Test if they are valid regular expressions and save error messages

        for item in df:
            filter, escaped = item
            if escaped:
                dfilter = re.escape(filter)
                dfilter = dfilter.replace("\\*", ".*")
            else:
                dfilter = filter
            try:
                re.compile("(" + dfilter + ")")
                outfilter += dfilter
                proccessedfilters.append(dfilter)
            except Exception as e:
                failed[dfilter] = e

            proccessedfilters.append(dfilter)

            if item is not df[-1]:
                outfilter += "|"

        # Crop trailing pipes
        while outfilter[-1] == "|":
            outfilter = outfilter[:-1]

        outfilter += ")$)"
        try:
            re.compile(outfilter)
            self.np.config.sections["transfers"]["downloadregexp"] = outfilter
            # Send error messages for each failed filter to log window
            if len(failed) >= 1:
                errors = ""
                for filter, error in list(failed.items()):
                    errors += "Filter: %s Error: %s " % (filter, error)
                error = _("Error: %(num)d Download filters failed! %(error)s " % {'num': len(failed), 'error': errors})
                self.logMessage(error)
        except Exception as e:
            # Strange that individual filters _and_ the composite filter both fail
            self.logMessage(_("Error: Download Filter failed! Verify your filters. Reason: %s" % e))
            self.np.config.sections["transfers"]["downloadregexp"] = ""

    def UpdateTransferButtons(self):
        if self.np.config.sections["transfers"]["enabletransferbuttons"]:
            self.DownloadButtons.show()
            self.UploadButtons.show()
        else:
            self.UploadButtons.hide()
            self.DownloadButtons.hide()

    def OnCheckLatest(self, widget):
        checklatest(self.MainWindow)

    def OnReportBug(self, widget):
        url = "https://github.com/Nicotine-Plus/nicotine-plus/issues"
        OpenUri(url, self.MainWindow)

    def OnAbout(self, widget):
        builder = gtk.Builder()
        builder.set_translation_domain('nicotine')
        builder.add_from_file(os.path.join(os.path.dirname(os.path.realpath(__file__)), "ui", "about", "about.ui"))

        self.About = builder.get_object("About")

        # Remove non-functional close button added by GTK
        buttons = self.About.get_action_area().get_children()
        if buttons:
            buttons[-1].destroy()

        self.About.set_transient_for(self.MainWindow)
        self.About.set_version(version)
        self.About.show()

    def OnAboutChatroomCommands(self, widget):
        builder = gtk.Builder()
        builder.set_translation_domain('nicotine')
        builder.add_from_file(os.path.join(os.path.dirname(os.path.realpath(__file__)), "ui", "about", "chatroomcommands.ui"))

        self.AboutChatroomCommands = builder.get_object("AboutChatRoomCommands")
        self.AboutChatroomCommands.set_transient_for(self.MainWindow)
        self.AboutChatroomCommands.show()

    def OnAboutPrivateChatCommands(self, widget):
        builder = gtk.Builder()
        builder.set_translation_domain('nicotine')
        builder.add_from_file(os.path.join(os.path.dirname(os.path.realpath(__file__)), "ui", "about", "privatechatcommands.ui"))

        self.AboutPrivateChatCommands = builder.get_object("AboutPrivateChatCommands")
        self.AboutPrivateChatCommands.set_transient_for(self.MainWindow)
        self.AboutPrivateChatCommands.show()

    def OnAboutFilters(self, widget):
        builder = gtk.Builder()
        builder.set_translation_domain('nicotine')
        builder.add_from_file(os.path.join(os.path.dirname(os.path.realpath(__file__)), "ui", "about", "searchfilters.ui"))

        self.AboutSearchFilters = builder.get_object("AboutSearchFilters")
        self.AboutSearchFilters.set_transient_for(self.MainWindow)
        self.AboutSearchFilters.show()

    def OnShowChatButtons(self, widget=None):
        if widget is not None:
            show = widget.get_active()
            self.np.config.sections["ui"]["chat_hidebuttons"] = (not show)
        if self.chatrooms is None:
            return
        for room in list(self.chatrooms.roomsctrl.joinedrooms.values()):
            room.OnShowChatButtons(not self.np.config.sections["ui"]["chat_hidebuttons"])

        self.np.config.writeConfiguration()

    def OnShowLog(self, widget):

        show = widget.get_active()
        self.np.config.sections["logging"]["logcollapsed"] = (not show)

        if not show:
            if self.debugLogBox in self.vpaned1.get_children():
                self.vpaned1.remove(self.debugLogBox)
        else:
            if self.debugLogBox not in self.vpaned1.get_children():
                self.vpaned1.pack2(self.debugLogBox, True, True)
                ScrollBottom(self.LogScrolledWindow)

        self.np.config.writeConfiguration()

    def OnShowFlags(self, widget):
        if self.chatrooms is None:
            return
        show = widget.get_active()
        self.np.config.sections["columns"]["hideflags"] = (not show)
        for room in self.chatrooms.roomsctrl.joinedrooms:
            self.chatrooms.roomsctrl.joinedrooms[room].cols[1].set_visible(show)
            self.np.config.sections["columns"]["chatrooms"][room][1] = int(show)
        self.userlist.cols[1].set_visible(show)
        self.np.config.sections["columns"]["userlist"][1] = int(show)
        self.np.config.writeConfiguration()

    def OnShowTransferButtons(self, widget):

        show = widget.get_active()

        self.np.config.sections["transfers"]["enabletransferbuttons"] = show
        self.UpdateTransferButtons()
        self.np.config.writeConfiguration()

    def OnShowRoomList(self, widget):

        show = widget.get_active()
        self.np.config.sections["ui"]["roomlistcollapsed"] = (not show)

        if not show:
            if self.roomlist.vbox2 in self.vpaned3.get_children():
                self.vpaned3.remove(self.roomlist.vbox2)

            if self.userlist.userlistvbox not in self.vpaned3.get_children():
                self.vpaned3.hide()
        else:
            if self.roomlist.vbox2 not in self.vpaned3.get_children():
                self.vpaned3.pack2(self.roomlist.vbox2, True, True)
                self.vpaned3.show()

        self.np.config.writeConfiguration()

    def OnToggleBuddyList(self, widget):
        """ Function used to switch around the UI the BuddyList position """

        tab = always = chatrooms = hidden = False

        if self.buddylist_in_tab.get_active():
            tab = True
        if self.buddylist_always_visible.get_active():
            always = True
        if self.buddylist_in_chatrooms1.get_active():
            chatrooms = True
        if self.buddylist_hidden.get_active():
            hidden = True

        if self.userlist.userlistvbox in self.MainNotebook.get_children():
            if tab:
                return
            self.MainNotebook.remove_page(self.MainNotebook.page_num(self.userlist.userlistvbox))

        if self.userlist.userlistvbox in self.vpanedm.get_children():
            if always:
                return
            self.vpanedm.remove(self.userlist.userlistvbox)

        if self.userlist.userlistvbox in self.vpaned3.get_children():
            if chatrooms:
                return
            self.vpaned3.remove(self.userlist.userlistvbox)

        if not self.show_room_list1.get_active():
            if not chatrooms:
                self.vpaned3.hide()

        if tab:
            self.BuddiesTabLabel = ImageLabel(_("Buddy list"), self.images["empty"])
            self.BuddiesTabLabel.show()

            if self.userlist.userlistvbox not in self.MainNotebook.get_children():
                self.MainNotebook.append_page(self.userlist.userlistvbox, self.BuddiesTabLabel)

            if self.userlist.userlistvbox in self.MainNotebook.get_children():
                self.MainNotebook.set_tab_reorderable(self.userlist.userlistvbox, self.np.config.sections["ui"]["tab_reorderable"])

            self.userlist.BuddiesLabel.hide()

            self.np.config.sections["ui"]["buddylistinchatrooms"] = 0

        if chatrooms:
            self.vpaned3.show()
            if self.userlist.userlistvbox not in self.vpaned3.get_children():
                self.vpaned3.pack1(self.userlist.userlistvbox, True, True)

            self.userlist.BuddiesLabel.show()
            self.np.config.sections["ui"]["buddylistinchatrooms"] = 1

        if always:
            self.vpanedm.show()
            if self.userlist.userlistvbox not in self.vpanedm.get_children():
                self.vpanedm.pack2(self.userlist.userlistvbox, True, True)

            self.userlist.BuddiesLabel.show()
            self.np.config.sections["ui"]["buddylistinchatrooms"] = 2
        else:
            self.vpanedm.hide()

        if hidden:
            # Work already done by the else statement above, just save the choice to config
            self.np.config.sections["ui"]["buddylistinchatrooms"] = 3

        self.np.config.writeConfiguration()

    def OnCheckPrivileges(self, widget):
        self.np.queue.put(slskmessages.CheckPrivileges())

    def OnGetPrivileges(self, widget):
        url = "%(url)s" % {
            'url': 'https://www.slsknet.org/userlogin.php?' + urlencode({
                'username': self.np.config.sections["server"]["login"]
            })
        }
        OpenUri(url, self.MainWindow)

    def OnSoulSeek(self, url):
        try:
            user, file = urllib.request.url2pathname(url[7:]).split("/", 1)
            if file[-1] == "/":
                self.np.ProcessRequestToPeer(user, slskmessages.FolderContentsRequest(None, file[:-1].replace("/", "\\")))
            else:
                self.np.transfers.getFile(user, file.replace("/", "\\"), "")
        except Exception:
            self.logMessage(_("Invalid SoulSeek meta-url: %s") % url)

    def SetClipboardURL(self, user, path):
        self.clip.set_text("slsk://" + urllib.request.pathname2url("%s/%s" % (user, path.replace("\\", "/"))), -1)
        self.clip_data = "slsk://" + urllib.request.pathname2url("%s/%s" % (user, path.replace("\\", "/")))

    def OnSelectionGet(self, widget, data, info, timestamp):
        data.set_text(self.clip_data, -1)

    def LocalUserInfoRequest(self, user):
        # Hack for local userinfo requests, for extra security
        if user == self.np.config.sections["server"]["login"]:
            try:
                if self.np.config.sections["userinfo"]["pic"] != "":
                    userpic = self.np.config.sections["userinfo"]["pic"]
                    if os.path.exists(userpic):
                        has_pic = True
                        f = open(userpic, 'rb')
                        pic = f.read()
                        f.close()
                    else:
                        has_pic = False
                        pic = None
                else:
                    has_pic = False
                    pic = None
            except Exception:
                pic = None

            descr = unescape(self.np.config.sections["userinfo"]["descr"])

            if self.np.transfers is not None:

                totalupl = self.np.transfers.getTotalUploadsAllowed()
                queuesize = self.np.transfers.getUploadQueueSizes()[0]
                slotsavail = self.np.transfers.allowNewUploads()
                ua = self.np.config.sections["transfers"]["remotedownloads"]
                if ua:
                    uploadallowed = self.np.config.sections["transfers"]["uploadallowed"]
                else:
                    uploadallowed = ua
                self.userinfo.ShowLocalInfo(user, descr, has_pic, pic, totalupl, queuesize, slotsavail, uploadallowed)

        else:
            self.np.ProcessRequestToPeer(user, slskmessages.UserInfoRequest(None), self.userinfo)

    def BrowseUser(self, user):
        """ Browse a user shares """

        login = self.np.config.sections["server"]["login"]

        if user is not None:
            if user == login:
                self.OnBrowsePublicShares(None)
            else:
                self.np.ProcessRequestToPeer(user, slskmessages.GetSharedFileList(None), self.userbrowse)

    def OnBrowsePublicShares(self, widget):
        """ Browse your own public shares """

        login = self.np.config.sections["server"]["login"]

        # Deactivate if we only share with buddies
        if self.np.config.sections["transfers"]["friendsonly"]:
            m = slskmessages.SharedFileList(None, {})
        else:
            m = slskmessages.SharedFileList(None, self.np.config.sections["transfers"]["sharedfilesstreams"])

        m.parseNetworkMessage(m.makeNetworkMessage(nozlib=1), nozlib=1)
        self.userbrowse.ShowInfo(login, m)

    def OnBrowseBuddyShares(self, widget):
        """ Browse your own buddy shares """

        login = self.np.config.sections["server"]["login"]

        # Show public shares if we don't have specific shares for buddies
        if not self.np.config.sections["transfers"]["enablebuddyshares"]:
            m = slskmessages.SharedFileList(None, self.np.config.sections["transfers"]["sharedfilesstreams"])
        else:
            m = slskmessages.SharedFileList(None, self.np.config.sections["transfers"]["bsharedfilesstreams"])

        m.parseNetworkMessage(m.makeNetworkMessage(nozlib=1), nozlib=1)
        self.userbrowse.ShowInfo(login, m)

    def PrivateRoomRemoveUser(self, room, user):
        self.np.queue.put(slskmessages.PrivateRoomRemoveUser(room, user))

    def PrivateRoomAddUser(self, room, user):
        self.np.queue.put(slskmessages.PrivateRoomAddUser(room, user))

    def PrivateRoomAddOperator(self, room, user):
        self.np.queue.put(slskmessages.PrivateRoomAddOperator(room, user))

    def PrivateRoomRemoveOperator(self, room, user):
        self.np.queue.put(slskmessages.PrivateRoomRemoveOperator(room, user))

    def OnFocusIn(self, widget, event):
        self.MainWindow.set_icon(self.images["n"])
        self.got_focus = True
        if self.MainWindow.get_urgency_hint():
            self.MainWindow.set_urgency_hint(False)

    def OnFocusOut(self, widget, event):
        self.got_focus = False

    def EntryCompletionFindMatch(self, completion, entry_text, iter, widget):
        model = completion.get_model()
        item_text = model.get_value(iter, 0)
        ix = widget.get_position()
        config = self.np.config.sections["words"]

        if entry_text is None or entry_text == "" or entry_text.isspace() or item_text is None:
            return False
        # Get word to the left of current position
        if " " in entry_text:
            split_key = entry_text[:ix].split(" ")[-1]
        else:
            split_key = entry_text
        if split_key.isspace() or split_key == "" or len(split_key) < config["characters"]:
            return False
        # case-insensitive matching
        if item_text.lower().startswith(split_key) and item_text.lower() != split_key:
            return True
        return False

    def EntryCompletionFoundMatch(self, completion, model, iter, widget):
        current_text = widget.get_text()
        ix = widget.get_position()
        # if more than a word has been typed, we throw away the
        # one to the left of our current position because we want
        # to replace it with the matching word

        if " " in current_text:
            prefix = " ".join(current_text[:ix].split(" ")[:-1])
            suffix = " ".join(current_text[ix:].split(" "))

            # add the matching word
            new_text = "%s %s%s" % (prefix, model[iter][0], suffix)
            # set back the whole text
            widget.set_text(new_text)
            # move the cursor at the end
            widget.set_position(len(prefix) + len(model[iter][0]) + 1)
        else:
            new_text = "%s" % (model[iter][0])
            widget.set_text(new_text)
            widget.set_position(-1)
        # stop the event propagation
        return True

    def OnPopupLogMenu(self, widget, event):
        if event.button != 3:
            return False
        widget.stop_emission_by_name("button-press-event")
        self.logpopupmenu.popup(None, None, None, None, event.button, event.time)
        return True

    #
    # Everything related to the log window
    #
    def OnFindLogWindow(self, widget):
        self.OnFindTextview(None, self.LogWindow)

    def OnCopyLogWindow(self, widget):
        bound = self.LogWindow.get_buffer().get_selection_bounds()
        if bound is not None and len(bound) == 2:
            start, end = bound
            log = self.LogWindow.get_buffer().get_text(start, end, True)
            self.clip.set_text(log, -1)

    def OnCopyAllLogWindow(self, widget):
        start, end = self.LogWindow.get_buffer().get_bounds()
        log = self.LogWindow.get_buffer().get_text(start, end, True)
        self.clip.set_text(log, -1)

    def OnClearLogWindow(self, widget):
        self.LogWindow.get_buffer().set_text("")

    #
    # Finding text in a text view
    # Used in private msg, chatrooms and log window
    #
    def OnFindTextview(self, widget, textview, repeat=False):

        if "FindDialog" not in self.__dict__:
            self.FindDialog = FindDialog(
                self,
                _('Enter the string to search for:'),
                "",
                textview=textview,
                modal=False
            )
            self.FindDialog.set_title(_('Nicotine+: Find string'))
            self.FindDialog.show()
            self.FindDialog.connect("find-click", self.OnFindClicked)
            return

        if textview is not self.FindDialog.textview:
            repeat = False

        self.FindDialog.textview = textview
        self.FindDialog.currentPosition = None
        self.FindDialog.nextPosition = None

        self.FindDialog.show()
        self.FindDialog.deiconify()

        if repeat:
            self.OnFindClicked(widget, self.FindDialog.lastdirection)
        else:
            self.FindDialog.entry.set_text("")

    def OnFindClicked(self, widget, direction):

        if self.FindDialog.textview is None:
            return

        self.FindDialog.lastdirection = direction
        textview = self.FindDialog.textview
        buffer = textview.get_buffer()
        start, end = buffer.get_bounds()
        query = self.FindDialog.entry.get_text()

        textview.emit("select-all", False)

        if self.FindDialog.currentPosition is None:
            self.FindDialog.currentPosition = buffer.create_mark(None, start, False)
            self.FindDialog.nextPosition = buffer.create_mark(None, start, False)

        if direction == "next":
            current = buffer.get_mark("insert")
            iter = buffer.get_iter_at_mark(current)
            match1 = iter.forward_search(query, gtk.TextSearchFlags.TEXT_ONLY | gtk.TextSearchFlags.CASE_INSENSITIVE, limit=None)

            if match1 is not None and len(match1) == 2:
                match_start, match_end = match1
                buffer.place_cursor(match_end)
                buffer.select_range(match_end, match_start)
                textview.scroll_to_iter(match_start, 0, False, 0.5, 0.5)
            else:
                iter = start
                match1 = iter.forward_search(query, gtk.TextSearchFlags.TEXT_ONLY | gtk.TextSearchFlags.CASE_INSENSITIVE, limit=None)

                if match1 is not None and len(match1) == 2:
                    match_start, match_end = match1
                    buffer.place_cursor(match_end)
                    buffer.select_range(match_end, match_start)
                    textview.scroll_to_iter(match_start, 0, False, 0.5, 0.5)

        elif direction == "previous":

            current = buffer.get_mark("insert")
            iter = buffer.get_iter_at_mark(current)
            match1 = iter.backward_search(query, gtk.TextSearchFlags.TEXT_ONLY | gtk.TextSearchFlags.CASE_INSENSITIVE, limit=None)

            if match1 is not None and len(match1) == 2:
                match_start, match_end = match1
                buffer.place_cursor(match_start)
                buffer.select_range(match_start, match_end)
                textview.scroll_to_iter(match_start, 0, False, 0.5, 0.5)
            else:
                iter = end
                match1 = iter.backward_search(query, gtk.TextSearchFlags.TEXT_ONLY | gtk.TextSearchFlags.CASE_INSENSITIVE, limit=None)

                if match1 is not None and len(match1) == 2:
                    match_start, match_end = match1
                    buffer.place_cursor(match_start)
                    buffer.select_range(match_start, match_end)
                    textview.scroll_to_iter(match_start, 0, False, 0.5, 0.5)
            return

    def OnAddThingILike(self, widget):
        thing = self.AddLikeEntry.get_text()
        self.AddLikeEntry.set_text("")

        if thing and thing.lower() not in self.np.config.sections["interests"]["likes"]:
            thing = thing.lower()
            self.np.config.sections["interests"]["likes"].append(thing)
            self.likes[thing] = self.likeslist.append([thing])
            self.np.config.writeConfiguration()
            self.np.queue.put(slskmessages.AddThingILike(thing))

    def OnAddThingIDislike(self, widget):
        thing = self.AddDislikeEntry.get_text()
        self.AddDislikeEntry.set_text("")

        if thing and thing.lower() not in self.np.config.sections["interests"]["dislikes"]:
            thing = thing.lower()
            self.np.config.sections["interests"]["dislikes"].append(thing)
            self.dislikes[thing] = self.dislikeslist.append([thing])
            self.np.config.writeConfiguration()
            self.np.queue.put(slskmessages.AddThingIHate(thing))

    def SetRecommendations(self, title, recom):
        self.recommendationslist.clear()
        for (thing, rating) in recom.items():
            self.recommendationslist.append([thing, Humanize(rating), rating])
        self.recommendationslist.set_sort_column_id(2, gtk.SortType.DESCENDING)

    def SetUnrecommendations(self, title, recom):
        self.unrecommendationslist.clear()
        for (thing, rating) in recom.items():
            self.unrecommendationslist.append([thing, Humanize(rating), rating])
        self.unrecommendationslist.set_sort_column_id(2, gtk.SortType.ASCENDING)

    def GlobalRecommendations(self, msg):
        self.SetRecommendations("Global recommendations", msg.recommendations)
        self.SetUnrecommendations("Unrecommendations", msg.unrecommendations)

    def Recommendations(self, msg):
        self.SetRecommendations("Recommendations", msg.recommendations)
        self.SetUnrecommendations("Unrecommendations", msg.unrecommendations)

    def ItemRecommendations(self, msg):
        self.SetRecommendations(_("Recommendations for %s") % msg.thing, msg.recommendations)
        self.SetUnrecommendations("Unrecommendations", msg.unrecommendations)

    def OnGlobalRecommendationsClicked(self, widget):
        self.np.queue.put(slskmessages.GlobalRecommendations())

    def OnRecommendationsClicked(self, widget):
        self.np.queue.put(slskmessages.Recommendations())

    def OnSimilarUsersClicked(self, widget):
        self.np.queue.put(slskmessages.SimilarUsers())

    def SimilarUsers(self, msg):
        self.recommendationuserslist.clear()
        self.recommendationusers = {}
        for user in msg.users:
            iter = self.recommendationuserslist.append([self.images["offline"], user, "0", "0", 0, 0, 0])
            self.recommendationusers[user] = iter
            self.np.queue.put(slskmessages.AddUser(user))

    def ItemSimilarUsers(self, msg):
        self.recommendationuserslist.clear()
        self.recommendationusers = {}
        for user in msg.users:
            iter = self.recommendationuserslist.append([self.images["offline"], user, "0", "0", 0, 0, 0])
            self.recommendationusers[user] = iter
            self.np.queue.put(slskmessages.AddUser(user))

    def GetUserStatus(self, msg):
        if msg.user not in self.recommendationusers:
            return
        img = self.GetStatusImage(msg.status)
        self.recommendationuserslist.set(self.recommendationusers[msg.user], 0, img, 4, msg.status)

    def GetUserStats(self, msg):
        if msg.user not in self.recommendationusers:
            return
        self.recommendationuserslist.set(self.recommendationusers[msg.user], 2, HumanSpeed(msg.avgspeed), 3, Humanize(msg.files), 5, msg.avgspeed, 6, msg.files)

    def OnPopupRUMenu(self, widget, event):
        items = self.ru_popup_menu.get_children()
        d = self.RecommendationUsersList.get_path_at_pos(int(event.x), int(event.y))
        if not d:
            return
        path, column, x, y = d
        user = self.recommendationuserslist.get_value(self.recommendationuserslist.get_iter(path), 1)
        if event.button != 3:
            if event.type == Gdk.EventType._2BUTTON_PRESS:
                self.privatechats.SendMessage(user)
                self.ChangeMainPage(None, "private")
            return
        self.ru_popup_menu.set_user(user)
        items[7].set_active(user in [i[0] for i in self.np.config.sections["server"]["userlist"]])
        items[8].set_active(user in self.np.config.sections["server"]["banlist"])
        items[9].set_active(user in self.np.config.sections["server"]["ignorelist"])
        self.ru_popup_menu.popup(None, None, None, None, event.button, event.time)

    def OnRemoveThingILike(self, widget):
        thing = self.til_popup_menu.get_user()
        if thing not in self.np.config.sections["interests"]["likes"]:
            return
        self.likeslist.remove(self.likes[thing])
        del self.likes[thing]
        self.np.config.sections["interests"]["likes"].remove(thing)
        self.np.config.writeConfiguration()
        self.np.queue.put(slskmessages.RemoveThingILike(thing))

    def OnRecommendItem(self, widget):
        thing = self.til_popup_menu.get_user()
        self.np.queue.put(slskmessages.ItemRecommendations(thing))
        self.np.queue.put(slskmessages.ItemSimilarUsers(thing))

    def OnPopupTILMenu(self, widget, event):
        if event.button != 3:
            return
        d = self.LikesList.get_path_at_pos(int(event.x), int(event.y))
        if not d:
            return
        path, column, x, y = d
        iter = self.likeslist.get_iter(path)
        thing = self.likeslist.get_value(iter, 0)
        self.til_popup_menu.set_user(thing)
        self.til_popup_menu.popup(None, None, None, None, event.button, event.time)

    def OnRemoveThingIDislike(self, widget):
        thing = self.tidl_popup_menu.get_user()
        if thing not in self.np.config.sections["interests"]["dislikes"]:
            return
        self.dislikeslist.remove(self.dislikes[thing])
        del self.dislikes[thing]
        self.np.config.sections["interests"]["dislikes"].remove(thing)
        self.np.config.writeConfiguration()
        self.np.queue.put(slskmessages.RemoveThingIHate(thing))

    def OnPopupTIDLMenu(self, widget, event):
        if event.button != 3:
            return
        d = self.DislikesList.get_path_at_pos(int(event.x), int(event.y))
        if not d:
            return
        path, column, x, y = d
        iter = self.dislikeslist.get_iter(path)
        thing = self.dislikeslist.get_value(iter, 0)
        self.tidl_popup_menu.set_user(thing)
        self.tidl_popup_menu.popup(None, None, None, None, event.button, event.time)

    def OnLikeRecommendation(self, widget):
        thing = widget.get_parent().get_user()
        if widget.get_active() and thing not in self.np.config.sections["interests"]["likes"]:
            self.np.config.sections["interests"]["likes"].append(thing)
            self.likes[thing] = self.likeslist.append([thing])
            self.np.config.writeConfiguration()
            self.np.queue.put(slskmessages.AddThingILike(thing))
        elif not widget.get_active() and thing in self.np.config.sections["interests"]["likes"]:
            self.likeslist.remove(self.likes[thing])
            del self.likes[thing]
            self.np.config.sections["interests"]["likes"].remove(thing)
            self.np.config.writeConfiguration()
            self.np.queue.put(slskmessages.RemoveThingILike(thing))

    def OnDislikeRecommendation(self, widget):
        thing = widget.get_parent().get_user()
        if widget.get_active() and thing not in self.np.config.sections["interests"]["dislikes"]:
            self.np.config.sections["interests"]["dislikes"].append(thing)
            self.dislikes[thing] = self.dislikeslist.append([thing])
            self.np.config.writeConfiguration()
            self.np.queue.put(slskmessages.AddThingIHate(thing))
        elif not widget.get_active() and thing in self.np.config.sections["interests"]["dislikes"]:
            self.dislikeslist.remove(self.dislikes[thing])
            del self.dislikes[thing]
            self.np.config.sections["interests"]["dislikes"].remove(thing)
            self.np.config.writeConfiguration()
            self.np.queue.put(slskmessages.RemoveThingIHate(thing))

    def OnRecommendRecommendation(self, widget):
        thing = self.r_popup_menu.get_user()
        self.np.queue.put(slskmessages.ItemRecommendations(thing))
        self.np.queue.put(slskmessages.ItemSimilarUsers(thing))

    def OnRecommendSearch(self, widget):
        thing = widget.get_parent().get_user()
        self.SearchEntry.set_text(thing)
        self.ChangeMainPage(None, "search")

    def OnPopupRMenu(self, widget, event):
        if event.button != 3:
            return
        d = self.RecommendationsList.get_path_at_pos(int(event.x), int(event.y))
        if not d:
            return
        path, column, x, y = d
        iter = self.recommendationslist.get_iter(path)
        thing = self.recommendationslist.get_value(iter, 0)
        items = self.r_popup_menu.get_children()
        self.r_popup_menu.set_user(thing)
        items[0].set_active(thing in self.np.config.sections["interests"]["likes"])
        items[1].set_active(thing in self.np.config.sections["interests"]["dislikes"])
        self.r_popup_menu.popup(None, None, None, None, event.button, event.time)

    def OnPopupUnRecMenu(self, widget, event):
        if event.button != 3:
            return
        d = self.UnrecommendationsList.get_path_at_pos(int(event.x), int(event.y))
        if not d:
            return
        path, column, x, y = d
        iter = self.unrecommendationslist.get_iter(path)
        thing = self.unrecommendationslist.get_value(iter, 0)
        items = self.ur_popup_menu.get_children()
        self.ur_popup_menu.set_user(thing)
        items[0].set_active(thing in self.np.config.sections["interests"]["likes"])
        items[1].set_active(thing in self.np.config.sections["interests"]["dislikes"])
        self.ur_popup_menu.popup(None, None, None, None, event.button, event.time)

    def RecommendationsExpanderStatus(self, widget):
        if widget.get_property("expanded"):
            self.RecommendationsVbox.set_child_packing(widget, False, True, 0, 0)
        else:
            self.RecommendationsVbox.set_child_packing(widget, True, True, 0, 0)

    def GivePrivileges(self, user, days):
        self.np.queue.put(slskmessages.GivePrivileges(user, days))

    def MatchMainNotebox(self, tab):

        if tab == self.chathbox:
            name = "chatrooms"  # Chatrooms
        elif tab == self.privatevbox:
            name = "private"  # Private rooms
        elif tab == self.downloadsvbox:
            name = "downloads"  # Downloads
        elif tab == self.uploadsvbox:
            name = "uploads"  # Uploads
        elif tab == self.searchvbox:
            name = "search"  # Searches
        elif tab == self.userinfovbox:
            name = "userinfo"  # Userinfo
        elif tab == self.userbrowsevbox:
            name = "userbrowse"  # User browse
        elif tab == self.interestsvbox:
            name = "interests"   # Interests
        elif tab == self.userlist.userlistvbox:
            name = "userlist"   # Buddy list
        else:
            # this should never happen, unless you've renamed a widget
            return

        return name

    def MatchMainNamePage(self, tab):

        if tab == "chatrooms":
            child = self.chathbox  # Chatrooms
        elif tab == "private":
            child = self.privatevbox  # Private rooms
        elif tab == "downloads":
            child = self.downloadsvbox  # Downloads
        elif tab == "uploads":
            child = self.uploadsvbox  # Uploads
        elif tab == "search":
            child = self.searchvbox  # Searches
        elif tab == "userinfo":
            child = self.userinfovbox  # Userinfo
        elif tab == "userbrowse":
            child = self.userbrowsevbox  # User browse
        elif tab == "interests":
            child = self.interestsvbox  # Interests
        elif tab == "userlist":
            child = self.userlist.userlistvbox  # Buddy list
        else:
            # this should never happen, unless you've renamed a widget
            return
        return child

    def ChangeMainPage(self, widget, tab):

        page_num = self.MainNotebook.page_num

        if tab == "chatrooms":
            child = self.chathbox  # Chatrooms
        elif tab == "private":
            child = self.privatevbox  # Private rooms
        elif tab == "downloads":
            child = self.downloadsvbox  # Downloads
        elif tab == "uploads":
            child = self.uploadsvbox  # Uploads
        elif tab == "search":
            child = self.searchvbox  # Searches
        elif tab == "userinfo":
            child = self.userinfovbox  # Userinfo
        elif tab == "userbrowse":
            child = self.userbrowsevbox  # User browse
        elif tab == "interests":
            child = self.interestsvbox  # Interests
        elif tab == "userlist":
            child = self.userlist.userlistvbox  # Buddy list
        else:
            # this should never happen, unless you've renamed a widget
            return

        if child in self.MainNotebook.get_children():
            self.MainNotebook.set_current_page(page_num(child))
        else:
            self.ShowTab(widget, [tab, child])

    def OnChatRooms(self, widget):
        self.ChangeMainPage(widget, "chatrooms")

    def OnPrivateChat(self, widget):
        self.ChangeMainPage(widget, "private")

    def OnDownloads(self, widget):
        self.ChangeMainPage(widget, "downloads")

    def OnUploads(self, widget):
        self.ChangeMainPage(widget, "uploads")

    def OnSearchFiles(self, widget):
        self.ChangeMainPage(widget, "search")

    def OnUserInfo(self, widget):
        self.ChangeMainPage(widget, "userinfo")

    def OnUserBrowse(self, widget):
        self.ChangeMainPage(widget, "userbrowse")

    def OnInterests(self, widget):
        self.ChangeMainPage(widget, "interests")

    def OnUserList(self, widget):
        self.buddylist_in_tab.set_active(True)

        self.OnToggleBuddyList(widget)
        self.ChangeMainPage(widget, "userlist")


class MainApp(gtk.Application):
    def __init__(self, data_dir, config, plugins, trayicon, start_hidden, bindip, port):
        gtk.Application.__init__(self, application_id="org.nicotine_plus.Nicotine",
                                 flags=Gio.ApplicationFlags.FLAGS_NONE)

        self.connect(
            "activate",
            self.OnActivate,
            data_dir,
            config,
            plugins,
            trayicon,
            start_hidden,
            bindip,
            port
        )

    def OnActivate(self, data, data_dir, config, plugins, trayicon, start_hidden, bindip, port):
        if not self.get_windows():
            # Only allow one instance of the main window

            self.frame = NicotineFrame(
                data_dir,
                config,
                plugins,
                trayicon,
                bindip,
                port
            )

            self.add_window(self.frame.MainWindow)

        if not start_hidden:
            self.frame.MainWindow.show()

            if self.frame.fastconfigure is not None:
                self.frame.fastconfigure.show()
