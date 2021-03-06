# COPYRIGHT (C) 2020 Nicotine+ Team
# COPYRIGHT (C) 2016-2017 Michael Labouebe <gfarmerfr@free.fr>
# COPYRIGHT (C) 2016-2018 Mutnick <mutnick@techie.com>
# COPYRIGHT (C) 2008-2011 Quinox <quinox@users.sf.net>
# COPYRIGHT (C) 2009 Hedonist <ak@sensi.org>
# COPYRIGHT (C) 2007 Gallows <g4ll0ws@gmail.com>
# COPYRIGHT (C) 2006-2009 Daelstorm <daelstorm@gmail.com>
# COPYRIGHT (C) 2003-2004 Hyriand <hyriand@thegraveyard.org>
# COPYRIGHT (C) 2001-2003 Alexander Kanavin
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

"""
This module contains configuration classes for Nicotine.
"""

import configparser
import os
import pickle
import shelve
import sys
import time
from ast import literal_eval
from gettext import gettext as _
from os.path import exists

import _thread
from pynicotine.logfacility import log

if sys.platform == "win32":
    # Use semidbm for faster shelves on Windows

    def shelve_open_semidbm(filename, flag='c', protocol=None, writeback=False):
        import semidbm
        return shelve.Shelf(semidbm.open(filename, flag), protocol, writeback)

    shelve.open = shelve_open_semidbm


class RestrictedUnpickler(pickle.Unpickler):
    """
    Don't allow code execution from pickles
    """
    def find_class(self, module, name):
        # Forbid all globals
        raise pickle.UnpicklingError("global '%s.%s' is forbidden" %
                                     (module, name))


class Config:
    """
    This class holds configuration information and provides the
    following methods:

    needConfig() - returns true if configuration information is incomplete
    readConfig() - reads configuration information from file
    setConfig(config_info_dict) - sets configuration information
    writeConfiguration - writes configuration information to file
    writeDownloadQueue - writes download queue to file
    writeConfig - calls writeConfiguration followed by writeDownloadQueue

    The actual configuration information is stored as a two-level dictionary.
    First-level keys are config sections, second-level keys are config
    parameters.
    """

    def __init__(self, filename, data_dir):

        self.config_lock = _thread.allocate_lock()
        self.config_lock.acquire()
        self.frame = None
        self.filename = filename
        self.data_dir = data_dir
        self.parser = configparser.RawConfigParser()

        try:
            self.parser.read([self.filename], encoding="utf-8")
        except UnicodeDecodeError:
            self.convertConfig()
            self.parser.read([self.filename], encoding="utf-8")

        LOGDIR = os.path.join(data_dir, "logs")

        self.sections = {
            "server": {
                "server": ('server.slsknet.org', 2242),
                "login": '',
                "passw": '',
                "firewalled": 0,
                "ctcpmsgs": 0,
                "autosearch": [],
                "autoreply": "",
                "portrange": (2234, 2239),
                "upnp": True,
                "userlist": [],
                "banlist": [],
                "ignorelist": [],
                "ipignorelist": {},
                "ipblocklist": {"72.172.88.*": "MediaDefender Bots"},
                "autojoin": ["nicotine"],
                "autoaway": 15,
                "private_chatrooms": 0
            },

            "transfers": {
                "incompletedir": os.path.join(data_dir, 'incompletefiles'),
                "downloaddir": os.path.join(os.path.expanduser("~"), 'nicotine-downloads'),
                "uploaddir": os.path.join(os.path.expanduser("~"), 'nicotine-uploads'),
                "sharedownloaddir": 0,
                "shared": [],
                "buddyshared": [],
                "uploadbandwidth": 10,
                "uselimit": 0,
                "uploadlimit": 150,
                "downloadlimit": 0,
                "preferfriends": 0,
                "useupslots": 0,
                "uploadslots": 2,
                "afterfinish": "",
                "afterfolder": "",
                "lock": 1,
                "reverseorder": 0,
                "prioritize": 0,
                "fifoqueue": 0,
                "usecustomban": 0,
                "limitby": 1,
                "customban": "Banned, don't bother retrying",
                "queuelimit": 10000,
                "filelimit": 1000,
                "friendsonly": 0,
                "friendsnolimits": 0,
                "enablebuddyshares": 0,
                "enabletransferbuttons": 1,
                "groupdownloads": True,
                "groupuploads": True,
                "geoblock": 0,
                "geopanic": 0,
                "geoblockcc": [""],
                "remotedownloads": 1,
                "uploadallowed": 2,
                "autoclear_downloads": 0,
                "autoclear_uploads": 0,
                "downloads": [],
                "sharedfiles": {},
                "sharedfilesstreams": {},
                "uploadsinsubdirs": 1,
                "wordindex": {},
                "fileindex": {},
                "sharedmtimes": {},
                "bsharedfiles": {},
                "bsharedfilesstreams": {},
                "bwordindex": {},
                "bfileindex": {},
                "bsharedmtimes": {},
                "rescanonstartup": 0,
                "enablefilters": 1,
                "downloadregexp": "",
                "downloadfilters": [
                    ["desktop.ini", 1],
                    ["folder.jpg", 1],
                    ["*.url", 1],
                    ["thumbs.db", 1],
                    ["albumart(_{........-....-....-....-............}_)?(_?(large|small))?\\.jpg", 0]
                ],
                "download_doubleclick": 1,
                "upload_doubleclick": 1,
                "downloadsexpanded": True,
                "uploadsexpanded": True
            },

            "userinfo": {
                "descr": "''",
                "pic": ""
            },

            "words": {
                "censored": [],
                "autoreplaced": {
                    "teh ": "the ",
                    "taht ": "that ",
                    "tihng": "thing",
                    "youre": "you're",
                    "jsut": "just",
                    "thier": "their",
                    "tihs": "this"
                },
                "censorfill": "*",
                "censorwords": False,
                "replacewords": False,
                "tab": True,
                "cycle": False,
                "dropdown": True,
                "characters": 2,
                "roomnames": True,
                "buddies": True,
                "roomusers": True,
                "commands": True,
                "aliases": True,
                "onematch": True
            },

            "logging": {
                "debug": False,
                "debugmodes": [0, 1],
                "logcollapsed": 0,
                "logsdir": LOGDIR,
                "rooms_timestamp": "%H:%M:%S",
                "private_timestamp": "%Y-%m-%d %H:%M:%S",
                "log_timestamp": "%Y-%m-%d %H:%M:%S",
                "timestamps": 1,
                "privatechat": 0,
                "chatrooms": 0,
                "transfers": 0,
                "roomlogsdir": os.path.join(LOGDIR, "rooms"),
                "privatelogsdir": os.path.join(LOGDIR, "private"),
                "readroomlogs": 1,
                "readroomlines": 15,
                "readprivatelines": 15,
                "rooms": []
            },

            "privatechat": {
                "store": 0,
                "users": []
            },

            "columns": {
                "userbrowse": [1, 1, 1, 1],
                "userbrowse_widths": [600, 100, 70, 0],
                "userlist": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
                "userlist_widths": [0, 25, 180, 0, 0, 0, 0, 0, 160, 0],
                "chatrooms": {},
                "chatrooms_widths": {},
                "download_columns": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
                "download_widths": [200, 250, 250, 140, 50, 70, 170, 90, 140, 0],
                "upload_columns": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
                "upload_widths": [200, 250, 250, 140, 50, 70, 170, 90, 140, 0],
                "filesearch_columns": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
                "filesearch_widths": [50, 200, 25, 50, 90, 90, 400, 400, 100, 100, 0],
                "hideflags": False
            },

            "searches": {
                "expand_searches": True,
                "group_searches": True,
                "maxresults": 50,
                "re_filter": 0,
                "history": [],
                "enablefilters": 0,
                "defilter": ["", "", "", "", 0, ""],
                "filtercc": [],
                "reopen_tabs": False,
                "filterin": [],
                "filterout": [],
                "filtersize": [],
                "filterbr": [],
                "distrib_timer": 0,
                "distrib_ignore": 60,
                "search_results": 1,
                "max_displayed_results": 1000,
                "max_stored_results": 1500,
                "remove_special_chars": True
            },

            "ui": {
                "icontheme": "",
                "chatme": "FOREST GREEN",
                "chatremote": "",
                "chatlocal": "BLUE",
                "chathilite": "red",
                "urlcolor": "#3D2B7F",
                "useronline": "BLACK",
                "useraway": "ORANGE",
                "useroffline": "#aa0000",
                "usernamehotspots": 1,
                "usernamestyle": "bold",
                "textbg": "",
                "search": "",
                "searchq": "GREY",
                "inputcolor": "",
                "spellcheck": 1,
                "exitdialog": 1,
                "notexists": 1,
                "tab_default": "",
                "tab_hilite": "red",
                "tab_changed": "#0000ff",
                "tab_select_previous": 1,
                "tab_reorderable": 1,
                "tabmain": "Top",
                "tabrooms": "Top",
                "tabprivate": "Top",
                "tabinfo": "Top",
                "tabbrowse": "Top",
                "tabsearch": "Top",
                "tab_status_icons": 1,
                "chat_hidebuttons": 0,
                "labelmain": 0,
                "labelrooms": 0,
                "labelprivate": 0,
                "labelinfo": 0,
                "labelbrowse": 0,
                "labelsearch": 0,
                "decimalsep": ",",
                "chatfont": "",
                "roomlistcollapsed": 0,
                "tabclosers": 1,
                "searchfont": "",
                "listfont": "",
                "browserfont": "",
                "transfersfont": "",
                "last_tab_id": 0,
                "modes_visible": {
                    "chatrooms": 1,
                    "private": 1,
                    "downloads": 1,
                    "uploads": 1,
                    "search": 1,
                    "userinfo": 1,
                    "userbrowse": 1,
                    "interests": 1
                },
                "modes_order": [
                    "chatrooms",
                    "private",
                    "downloads",
                    "uploads",
                    "search",
                    "userinfo",
                    "userbrowse",
                    "interests",
                    "userlist"
                ],
                "showaway": 0,
                "buddylistinchatrooms": 0,
                "trayicon": 1,
                "filemanager": "xdg-open $",
                "speechenabled": 0,
                "speechprivate": "%(user)s told you.. %(message)s",
                "speechrooms": "In %(room)s, %(user)s said %(message)s",
                "speechcommand": "flite -t $",
                "width": 1000,
                "height": 600,
                "xposition": -1,
                "yposition": -1,
                "maximized": "True",
                "urgencyhint": True
            },

            "private_rooms": {
                "rooms": {},
                "enabled": 0
            },

            "urls": {
                "urlcatching": 1,
                "protocols": {},
                "humanizeurls": 1
            },

            "interests": {
                "likes": [],
                "dislikes": []
            },

            "ticker": {
                "default": "",
                "rooms": {},
                "hide": 0
            },

            "players": {
                "default": "xdg-open $",
                "npothercommand": "",
                "npplayer": "",
                "npformatlist": [],
                "npformat": ""
            },

            "notifications": {
                "notification_window_title": 1,
                "notification_tab_colors": 0,
                "notification_tab_icons": 1,
                "notification_popup_sound": 1,
                "notification_popup_file": 1,
                "notification_popup_folder": 1,
                "notification_popup_private_message": 1,
                "notification_popup_chatroom": 0,
                "notification_popup_chatroom_mention": 1
            },

            "plugins": {
                "enable": 1,
                "enabled": []
            }
        }

        # Windows specific stuff
        if sys.platform.startswith('win'):
            self.sections['ui']['filemanager'] = 'explorer $'

        self.defaults = {}
        for key, value in list(self.sections.items()):
            if type(value) is dict:
                if key not in self.defaults:
                    self.defaults[key] = {}

                for key2, value2 in list(value.items()):
                    self.defaults[key][key2] = value2
            else:
                self.defaults[key] = value

        try:
            f = open(filename + ".alias", 'rb')
            self.aliases = RestrictedUnpickler(f).load()
            f.close()
        except Exception:
            self.aliases = {}

        self.config_lock.release()

    def convertConfig(self):
        """ Converts the config to utf-8.
        Mainly for upgrading Windows build. (22 July, 2020) """

        try:
            from chardet import detect
        except ImportError:
            return

        os.rename(self.filename, self.filename + ".conv")

        with open(self.filename + ".conv", 'rb') as f:
            rawdata = f.read()

        from_encoding = detect(rawdata)['encoding']

        with open(self.filename + ".conv", 'r', encoding=from_encoding) as fr:
            with open(self.filename, 'w', encoding="utf-8") as fw:
                for line in fr:
                    fw.write(line[:-1] + '\r\n')

        os.remove(self.filename + ".conv")

    def needConfig(self):

        errorlevel = 0

        try:
            for i in list(self.sections.keys()):
                for j in list(self.sections[i].keys()):

                    if type(self.sections[i][j]) not in [type(None), type("")]:
                        continue

                    if self.sections[i][j] is None or self.sections[i][j] == '' \
                       and i not in ("userinfo", "ui", "ticker", "players") \
                       and j not in ("incompletedir", "autoreply", 'afterfinish', 'afterfolder', 'geoblockcc', 'downloadregexp'):

                        # Repair options set to None with defaults
                        if self.sections[i][j] is None and self.defaults[i][j] is not None:

                            self.sections[i][j] = self.defaults[i][j]
                            self.frame.logMessage(
                                _("Config option reset to default: Section: %(section)s, Option: %(option)s, to: %(default)s") % {
                                    'section': i,
                                    'option': j,
                                    'default': self.sections[i][j]
                                }
                            )

                            if errorlevel == 0:
                                errorlevel = 1
                        else:

                            if errorlevel < 2:
                                self.frame.logMessage(
                                    _("You need to configure your settings (Server, Username, Password, Download Directory) before connecting...")
                                )
                                errorlevel = 2

                            if self.frame.settingswindow is not None:
                                self.frame.settingswindow.InvalidSettings(i, j)

        except Exception as error:
            message = _("Config error: %s") % error
            self.frame.logMessage(message)
            if errorlevel < 3:
                errorlevel = 3

        if errorlevel > 1 and self.frame.settingswindow is not None:
            self.frame.settingswindow.SetSettings(self.sections)

        return errorlevel

    def readConfig(self):

        self.config_lock.acquire()

        self.sections['transfers']['downloads'] = []

        if exists(os.path.join(self.data_dir, 'transfers.pickle')):
            # <1.2.13 stored transfers inside the main config
            try:
                handle = open(os.path.join(self.data_dir, 'transfers.pickle'), 'rb')
            except IOError as inst:
                log.addwarning(_("Something went wrong while opening your transfer list: %(error)s") % {'error': str(inst)})
            else:
                try:
                    self.sections['transfers']['downloads'] = RestrictedUnpickler(handle).load()
                except (IOError, EOFError, ValueError) as inst:
                    log.addwarning(_("Something went wrong while reading your transfer list: %(error)s") % {'error': str(inst)})
            try:
                handle.close()
            except Exception:
                pass

        path, fn = os.path.split(self.filename)
        try:
            if not os.path.isdir(path):
                os.makedirs(path)
        except OSError as msg:
            log.addwarning("Can't create directory '%s', reported error: %s" % (path, msg))

        try:
            if not os.path.isdir(self.data_dir):
                os.makedirs(self.data_dir)
        except OSError as msg:
            log.addwarning("Can't create directory '%s', reported error: %s" % (path, msg))

        # Transition from 1.2.16 -> 1.4.0
        # Do the cleanup early so we don't get the annoying
        # 'Unknown config option ...' message
        self.removeOldOption("transfers", "pmqueueddir")
        self.removeOldOption("server", "lastportstatuscheck")
        self.removeOldOption("server", "serverlist")
        self.removeOldOption("userinfo", "descrutf8")
        self.removeOldOption("ui", "enabletrans")
        self.removeOldOption("ui", "mozembed")
        self.removeOldOption("ui", "open_in_mozembed")
        self.removeOldOption("ui", "tooltips")
        self.removeOldOption("ui", "transalpha")
        self.removeOldOption("ui", "transfilter")
        self.removeOldOption("ui", "transtint")
        self.removeOldOption("language", "language")
        self.removeOldOption("language", "setlanguage")
        self.removeOldSection("language")

        # Transition from 1.4.1 -> 1.4.2
        self.removeOldOption("columns", "downloads")
        self.removeOldOption("columns", "uploads")

        # Remove old encoding settings (1.4.3)
        self.removeOldOption("server", "enc")
        self.removeOldOption("server", "fallbackencodings")
        self.removeOldOption("server", "roomencoding")
        self.removeOldOption("server", "userencoding")

        # Remove soundcommand config, replaced by GSound (1.4.3)
        self.removeOldOption("ui", "soundcommand")

        # Remove old column widths in preparation for "group by folder"-feature
        self.removeOldOption("columns", "search")
        self.removeOldOption("columns", "search_widths")
        self.removeOldOption("columns", "downloads_columns")
        self.removeOldOption("columns", "downloads_widths")
        self.removeOldOption("columns", "uploads_columns")
        self.removeOldOption("columns", "uploads_widths")

        # Remove auto-retry failed downloads-option, this is now default behavior
        self.removeOldOption("transfers", "autoretry_downloads")

        # Remove old notification/sound settings
        self.removeOldOption("transfers", "shownotification")
        self.removeOldOption("transfers", "shownotificationperfolder")
        self.removeOldOption("ui", "soundenabled")
        self.removeOldOption("ui", "soundtheme")
        self.removeOldOption("ui", "tab_colors")
        self.removeOldOption("ui", "tab_icons")

        # Remove dropped offline user text color in search results
        self.removeOldOption("ui", "searchoffline")

        # Checking for unknown section/options
        unknown1 = [
            'login', 'passw', 'enc', 'downloaddir', 'uploaddir', 'customban',
            'descr', 'pic', 'logsdir', 'roomlogsdir', 'privatelogsdir',
            'incompletedir', 'autoreply', 'afterfinish', 'downloadregexp',
            'afterfolder', 'default', 'chatfont', 'npothercommand', 'npplayer',
            'npformat', 'private_timestamp', 'rooms_timestamp', 'log_timestamp'
        ]

        unknown2 = {
            'ui': [
                "roomlistcollapsed", "tab_select_previous", "tabclosers",
                "tab_colors", "tab_reorderable", "buddylistinchatrooms", "trayicon",
                "showaway", "usernamehotspots", "exitdialog",
                "tab_icons", "spellcheck", "modes_order", "modes_visible",
                "chat_hidebuttons", "tab_status_icons", "notexists",
                "speechenabled", "enablefilters", "width",
                "height", "xposition", "yposition", "labelmain", "labelrooms",
                "labelprivate", "labelinfo", "labelbrowse", "labelsearch"
            ],
            'words': [
                "completion", "censorwords", "replacewords", "autoreplaced",
                "censored", "characters", "tab", "cycle", "dropdown",
                "roomnames", "buddies", "roomusers", "commands",
                "aliases", "onematch"
            ]
        }

        for i in self.parser.sections():
            for j in self.parser.options(i):
                val = self.parser.get(i, j, raw=1)
                if i not in self.sections:
                    log.addwarning(_("Unknown config section '%s'") % i)
                elif j not in self.sections[i] and not (j == "filter" or i in ('plugins',)):
                    log.addwarning(_("Unknown config option '%(option)s' in section '%(section)s'") % {'option': j, 'section': i})
                elif j in unknown1 or (i in unknown2 and j not in unknown2[i]):
                    if val is not None and val != "None":
                        self.sections[i][j] = val
                    else:
                        self.sections[i][j] = None
                else:
                    try:
                        self.sections[i][j] = literal_eval(val)
                    except Exception:
                        self.sections[i][j] = None
                        log.addwarning("CONFIG ERROR: Couldn't decode '%s' section '%s' value '%s'" % (str(j), str(i), str(val)))

        # Convert fs-based shared to virtual shared (pre 1.4.0)
        def _convert_to_virtual(x):
            if isinstance(x, tuple):
                return x
            virtual = x.replace('/', '_').replace('\\', '_').strip('_')
            log.addwarning("Renaming shared folder '%s' to '%s'. A rescan of your share is required." % (x, virtual))
            return (virtual, x)

        self.sections["transfers"]["shared"] = [_convert_to_virtual(x) for x in self.sections["transfers"]["shared"]]
        self.sections["transfers"]["buddyshared"] = [_convert_to_virtual(x) for x in self.sections["transfers"]["buddyshared"]]

        sharedfiles = None
        bsharedfiles = None
        sharedfilesstreams = None
        bsharedfilesstreams = None
        wordindex = None
        bwordindex = None
        fileindex = None
        bfileindex = None
        sharedmtimes = None
        bsharedmtimes = None

        shelves = [
            os.path.join(self.data_dir, "files.db"),
            os.path.join(self.data_dir, "buddyfiles.db"),
            os.path.join(self.data_dir, "streams.db"),
            os.path.join(self.data_dir, "buddystreams.db"),
            os.path.join(self.data_dir, "wordindex.db"),
            os.path.join(self.data_dir, "buddywordindex.db"),
            os.path.join(self.data_dir, "fileindex.db"),
            os.path.join(self.data_dir, "buddyfileindex.db"),
            os.path.join(self.data_dir, "mtimes.db"),
            os.path.join(self.data_dir, "buddymtimes.db")
        ]

        _opened_shelves = []
        _errors = []
        for shelvefile in shelves:
            try:
                _opened_shelves.append(shelve.open(shelvefile, protocol=pickle.HIGHEST_PROTOCOL))
            except Exception:
                _errors.append(shelvefile)
                try:
                    os.unlink(shelvefile)
                    _opened_shelves.append(shelve.open(shelvefile, flag='n', protocol=pickle.HIGHEST_PROTOCOL))
                except Exception as ex:
                    print(("Failed to unlink %s: %s" % (shelvefile, ex)))

        sharedfiles = _opened_shelves.pop(0)
        bsharedfiles = _opened_shelves.pop(0)
        sharedfilesstreams = _opened_shelves.pop(0)
        bsharedfilesstreams = _opened_shelves.pop(0)
        wordindex = _opened_shelves.pop(0)
        bwordindex = _opened_shelves.pop(0)
        fileindex = _opened_shelves.pop(0)
        bfileindex = _opened_shelves.pop(0)
        sharedmtimes = _opened_shelves.pop(0)
        bsharedmtimes = _opened_shelves.pop(0)

        if _errors:
            log.addwarning(_("Failed to process the following databases: %(names)s") % {'names': '\n'.join(_errors)})

            files = self.clearShares(
                sharedfiles, bsharedfiles, sharedfilesstreams, bsharedfilesstreams,
                wordindex, bwordindex, fileindex, bfileindex, sharedmtimes, bsharedmtimes
            )

            if files is not None:
                sharedfiles, bsharedfiles, sharedfilesstreams, bsharedfilesstreams, wordindex, bwordindex, fileindex, bfileindex, sharedmtimes, bsharedmtimes = files

            log.addwarning(_("Shared files database seems to be corrupted, rescan your shares"))

        self.sections["transfers"]["sharedfiles"] = sharedfiles
        self.sections["transfers"]["sharedfilesstreams"] = sharedfilesstreams
        self.sections["transfers"]["wordindex"] = wordindex
        self.sections["transfers"]["fileindex"] = fileindex
        self.sections["transfers"]["sharedmtimes"] = sharedmtimes

        self.sections["transfers"]["bsharedfiles"] = bsharedfiles
        self.sections["transfers"]["bsharedfilesstreams"] = bsharedfilesstreams
        self.sections["transfers"]["bwordindex"] = bwordindex
        self.sections["transfers"]["bfileindex"] = bfileindex
        self.sections["transfers"]["bsharedmtimes"] = bsharedmtimes

        # Setting the port range in numerical order
        self.sections["server"]["portrange"] = (min(self.sections["server"]["portrange"]), max(self.sections["server"]["portrange"]))

        self.config_lock.release()

    def removeOldOption(self, section, option):
        if section in self.parser.sections():
            if option in self.parser.options(section):
                self.parser.remove_option(section, option)

    def removeOldSection(self, section):
        if section in self.parser.sections():
            self.parser.remove_section(section)

    def clearShares(
        self, sharedfiles, bsharedfiles, sharedfilesstreams, bsharedfilesstreams,
        wordindex, bwordindex, fileindex, bfileindex, sharedmtimes, bsharedmtimes
    ):

        try:
            if sharedfiles:
                sharedfiles.close()
            try:
                os.unlink(os.path.join(self.data_dir, 'files.db'))
            except Exception:
                pass
            sharedfiles = shelve.open(os.path.join(self.data_dir, "files.db"), flag='n', protocol=pickle.HIGHEST_PROTOCOL)

            if bsharedfiles:
                bsharedfiles.close()
            try:
                os.unlink(os.path.join(self.data_dir, 'buddyfiles.db'))
            except Exception:
                pass
            bsharedfiles = shelve.open(os.path.join(self.data_dir, "buddyfiles.db"), flag='n', protocol=pickle.HIGHEST_PROTOCOL)

            if sharedfilesstreams:
                sharedfilesstreams.close()
            try:
                os.unlink(os.path.join(self.data_dir, 'streams.db'))
            except Exception:
                pass
            sharedfilesstreams = shelve.open(os.path.join(self.data_dir, "streams.db"), flag='n', protocol=pickle.HIGHEST_PROTOCOL)

            if bsharedfilesstreams:
                bsharedfilesstreams.close()
            try:
                os.unlink(os.path.join(self.data_dir, 'buddystreams.db'))
            except Exception:
                pass
            bsharedfilesstreams = shelve.open(os.path.join(self.data_dir, "buddystreams.db"), flag='n', protocol=pickle.HIGHEST_PROTOCOL)

            if wordindex:
                wordindex.close()
            try:
                os.unlink(os.path.join(self.data_dir, 'wordindex.db'))
            except Exception:
                pass
            wordindex = shelve.open(os.path.join(self.data_dir, "wordindex.db"), flag='n', protocol=pickle.HIGHEST_PROTOCOL)

            if bwordindex:
                bwordindex.close()
            try:
                os.unlink(os.path.join(self.data_dir, 'buddywordindex.db'))
            except Exception:
                pass
            bwordindex = shelve.open(os.path.join(self.data_dir, "buddywordindex.db"), flag='n', protocol=pickle.HIGHEST_PROTOCOL)

            if fileindex:
                fileindex.close()
            try:
                os.unlink(os.path.join(self.data_dir, 'fileindex.db'))
            except Exception:
                pass
            fileindex = shelve.open(os.path.join(self.data_dir, "fileindex.db"), flag='n', protocol=pickle.HIGHEST_PROTOCOL)

            if bfileindex:
                bfileindex.close()
            try:
                os.unlink(os.path.join(self.data_dir, 'buddyfileindex.db'))
            except Exception:
                pass
            bfileindex = shelve.open(os.path.join(self.data_dir, "buddyfileindex.db"), flag='n', protocol=pickle.HIGHEST_PROTOCOL)

            if sharedmtimes:
                sharedmtimes.close()
            try:
                os.unlink(os.path.join(self.data_dir, 'mtimes.db'))
            except Exception:
                pass
            sharedmtimes = shelve.open(os.path.join(self.data_dir, "mtimes.db"), flag='n', protocol=pickle.HIGHEST_PROTOCOL)

            if bsharedmtimes:
                bsharedmtimes.close()
            try:
                os.unlink(os.path.join(self.data_dir, 'buddymtimes.db'))
            except Exception:
                pass
            bsharedmtimes = shelve.open(os.path.join(self.data_dir, "buddymtimes.db"), flag='n', protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as error:
            log.addwarning(_("Error while writing database files: %s") % error)
            return None
        return sharedfiles, bsharedfiles, sharedfilesstreams, bsharedfilesstreams, wordindex, bwordindex, fileindex, bfileindex, sharedmtimes, bsharedmtimes

    def writeConfig(self):
        self.writeConfiguration()
        self.writeDownloadQueue()

    def writeDownloadQueue(self):
        self.config_lock.acquire()
        realfile = os.path.join(self.data_dir, 'transfers.pickle')
        tmpfile = realfile + '.tmp'
        backupfile = realfile + ' .backup'
        try:
            handle = open(tmpfile, 'wb')
        except Exception as inst:
            log.addwarning(_("Something went wrong while opening your transfer list: %(error)s") % {'error': str(inst)})
        else:
            try:
                pickle.dump(self.sections['transfers']['downloads'], handle, protocol=pickle.HIGHEST_PROTOCOL)
                handle.close()
                try:
                    # Please let it be atomic...
                    os.rename(tmpfile, realfile)
                except Exception:
                    # ...ugh. Okay, how about...
                    try:
                        os.unlink(backupfile)
                    except Exception:
                        pass
                    os.rename(realfile, backupfile)
                    os.rename(tmpfile, realfile)
            except Exception as inst:
                log.addwarning(_("Something went wrong while writing your transfer list: %(error)s") % {'error': str(inst)})
        finally:
            try:
                handle.close()
            except Exception:
                pass
        self.config_lock.release()

    def writeConfiguration(self):

        self.config_lock.acquire()

        external_sections = [
            "sharedfiles", "sharedfilesstreams", "wordindex", "fileindex",
            "sharedmtimes", "bsharedfiles", "bsharedfilesstreams",
            "bwordindex", "bfileindex", "bsharedmtimes", "downloads"
        ]

        for i in list(self.sections.keys()):
            if not self.parser.has_section(i):
                self.parser.add_section(i)
            for j in list(self.sections[i].keys()):
                if j not in external_sections:
                    self.parser.set(i, j, self.sections[i][j])
                else:
                    self.parser.remove_option(i, j)

        path, fn = os.path.split(self.filename)
        try:
            if not os.path.isdir(path):
                os.makedirs(path)
        except OSError as msg:
            log.addwarning(_("Can't create directory '%(path)s', reported error: %(error)s") % {'path': path, 'error': msg})

        oldumask = os.umask(0o077)

        try:
            f = open(self.filename + ".new", "w", encoding="utf-8")
        except IOError as e:
            log.addwarning(_("Can't save config file, I/O error: %s") % e)
            self.config_lock.release()
            return
        else:
            try:
                self.parser.write(f)
            except IOError as e:
                log.addwarning(_("Can't save config file, I/O error: %s") % e)
                self.config_lock.release()
                return
            else:
                f.close()

        os.umask(oldumask)

        # A paranoid precaution since config contains the password
        try:
            os.chmod(self.filename, 0o600)
        except Exception:
            pass

        try:
            s = os.stat(self.filename)
            if s.st_size > 0:
                try:
                    if os.path.exists(self.filename + ".old"):
                        os.remove(self.filename + ".old")
                except OSError:
                    log.addwarning(_("Can't remove %s" % self.filename + ".old"))
                try:
                    os.rename(self.filename, self.filename + ".old")
                except OSError as error:
                    log.addwarning(_("Can't back config file up, error: %s") % error)
        except OSError:
            pass

        try:
            os.rename(self.filename + ".new", self.filename)
        except OSError as error:
            log.addwarning(_("Can't rename config file, error: %s") % error)

        self.config_lock.release()

    def writeConfigBackup(self, filename=None):

        self.config_lock.acquire()

        if filename is None:
            filename = "%s backup %s.tar.bz2" % (self.filename, time.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            if filename[-8:-1] != ".tar.bz2":
                filename += ".tar.bz2"
        try:
            if os.path.exists(filename):
                raise BaseException("File %s exists" % filename)
            import tarfile
            tar = tarfile.open(filename, "w:bz2")
            if not os.path.exists(self.filename):
                raise BaseException("Config file missing")
            tar.add(self.filename)
            if os.path.exists(self.filename + ".alias"):
                tar.add(self.filename + ".alias")

            tar.close()
        except Exception as e:
            print(e)
            self.config_lock.release()
            return (1, "Cannot write backup archive: %s" % e)
        self.config_lock.release()
        return (0, filename)

    def setBuddyShares(self, files, streams, wordindex, fileindex, mtimes):

        storable_objects = [
            (files, "bsharedfiles", "buddyfiles.db"),
            (streams, "bsharedfilesstreams", "buddystreams.db"),
            (mtimes, "bsharedmtimes", "buddymtimes.db"),
            (wordindex, "bwordindex", "buddywordindex.db"),
            (fileindex, "bfileindex", "buddyfileindex.db")
        ]

        self.storeObjects(storable_objects)

    def setShares(self, files, streams, wordindex, fileindex, mtimes):

        storable_objects = [
            (files, "sharedfiles", "files.db"),
            (streams, "sharedfilesstreams", "streams.db"),
            (mtimes, "sharedmtimes", "mtimes.db"),
            (wordindex, "wordindex", "wordindex.db"),
            (fileindex, "fileindex", "fileindex.db")
        ]

        self.storeObjects(storable_objects)

    def storeObjects(self, storable_objects):

        self.config_lock.acquire()

        for (source, destination, filename) in storable_objects:
            try:
                self.sections["transfers"][destination].close()
                self.sections["transfers"][destination] = shelve.open(os.path.join(self.data_dir, filename), flag='n', protocol=pickle.HIGHEST_PROTOCOL)

                if "fileindex" in destination:
                    index = 0

                    for value in source:
                        # The file index db is a list
                        self.sections["transfers"][destination][str(index)] = value
                        index += 1
                else:
                    for key in source:
                        self.sections["transfers"][destination][key] = source[key]
            except Exception as e:
                log.addwarning(_("Can't save %s: %s") % (filename, e))
                return

        self.config_lock.release()

    def pushHistory(self, history, text, max):
        if text in history:
            history.remove(text)
        elif len(history) >= max:
            del history[-1]
        history.insert(0, text)
        self.writeConfig()

    def writeAliases(self):
        self.config_lock.acquire()
        try:
            f = open(self.filename + ".alias", "wb")
        except Exception as e:
            log.addwarning(_("Something went wrong while opening your alias file: %s") % e)
        else:
            try:
                pickle.dump(self.aliases, f, protocol=pickle.HIGHEST_PROTOCOL)
                f.close()
            except Exception as e:
                log.addwarning(_("Something went wrong while saving your alias file: %s") % e)
        finally:
            try:
                f.close()
            except Exception:
                pass
        self.config_lock.release()

    def AddAlias(self, rest):
        if rest:
            args = rest.split(" ", 1)
            if len(args) == 2:
                if args[0] in ("alias", "unalias"):
                    return "I will not alias that!\n"
                self.aliases[args[0]] = args[1]
                self.writeAliases()
            if args[0] in self.aliases:
                return "Alias %s: %s\n" % (args[0], self.aliases[args[0]])
            else:
                return _("No such alias (%s)") % rest + "\n"
        else:
            m = "\n" + _("Aliases:") + "\n"
            for (key, value) in self.aliases.items():
                m = m + "%s: %s\n" % (key, value)
            return m + "\n"

    def Unalias(self, rest):
        if rest and rest in self.aliases:
            x = self.aliases[rest]
            del self.aliases[rest]
            self.writeAliases()
            return _("Removed alias %(alias)s: %(action)s\n") % {'alias': rest, 'action': x}
        else:
            return _("No such alias (%(alias)s)\n") % {'alias': rest}
