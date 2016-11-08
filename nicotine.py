#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# COPYRIGHT (c) 2016 Michael Labouebe <gfarmerfr@free.fr>
# COPYRIGHT (c) 2008-2011 Quinox <quinox@users.sf.net>
# COPYRIGHT (c) 2006-2008 eL_vErDe <gandalf@le-vert.net>
# COPYRIGHT (C) 2006-2009 Daelstorm <daelstorm@gmail.com>
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
Nicotine+ Launcher.
"""

import os
import platform
import sys
from pynicotine.logfacility import log
from pynicotine.utils import ApplyTranslation

# Setting gettext and locale
ApplyTranslation()

# Detect if we're running on Windows
win32 = platform.system().startswith("Win")


def checkenv():

    # Require Python 2.7
    try:
        assert sys.version_info[:2] == (2, 7), '.'.join(
            map(str, sys.version_info[:3])
        )
    except AssertionError as e:
        return _("""You're using an unsupported version of Python (%s).
You should install Python 2.7.X.""") % (e)

    # Require GTK+ 2.24
    try:
        import gtk
    except Exception as e:
        return _("Cannot find GTK+ 2.24.X, please install it.")
    else:
        try:
            assert gtk.gtk_version[:2] == (2, 24), '.'.join(
                map(str, gtk.gtk_version[:3])
            )
        except AssertionError as e:
            return _("""You're using an unsupported version of GTK (%s).
You should install GTK 2.24.X.""") % (e)

    # Require PyGTK 2.24
    try:
        import pygtk
    except Exception as e:
        return _("Cannot find PyGTK 2.24.X, please install it.")
    else:
        try:
            assert gtk.pygtk_version[:2] == (2, 24), '.'.join(
                map(str, gtk.pygtk_version[:3])
            )
        except AssertionError as e:
            return _("""You're using an unsupported version of PyGTK (%s).
You should install PyGTK 2.24.X.""") % (e)

    # On windows dbhash might be a good choice
    if win32:
        try:
            import dbhash
        except:
            log.add(
                _("Warning: the Berkeley DB module, dbhash, " +
                  "could not be loaded."))

    # Require pynicotine
    try:
        import pynicotine
    except ImportError, e:
        return _("""Can not find Nicotine+ modules.
Perhaps they're installed in a directory which is not
in an interpreter's module search path.
(there could be a version mismatch between
what version of python was used to build the Nicotine
binary package and what you try to run Nicotine+ with).""")

    # Require GeoIP
    try:
        import GeoIP
    except ImportError:
        try:
            import _GeoIP
        except ImportError:
            msg = _("""Nicotine+ supports a country code blocker.
That requires a (GPL'ed) library called GeoIP. You can find it here:
C library:       http://www.maxmind.com/app/c
Python bindings: http://www.maxmind.com/app/python
(the python bindings require the C library)""")
            log.addwarning(msg)

    return None


def version():
    try:
        import pynicotine.utils
        print _("Nicotine+ version %s" % pynicotine.utils.version)
    except ImportError, error:
        print _("Cannot find the pynicotine.utils module.")


def usage():
    print _("""Nicotine+ is a Soulseek client.
Usage: nicotine [OPTION]...
  -c file, --config=file      Use non-default configuration file
  -p dir,  --plugins=dir      Use non-default directory for plugins
  -t,      --enable-trayicon  Enable the tray icon
  -d,      --disable-trayicon Disable the tray icon
  -r,      --enable-rgba      Enable RGBA mode, for full program transparency
  -x,      --disable-rgba     Disable RGBA mode, default mode
  -h,      --help             Show help and exit
  -s,      --hidden           Start the program hidden so only the tray icon is shown
  -b ip,   --bindip=ip        Bind sockets to the given IP (useful for VPN)
  -v,      --version          Display version and exit""")


def renameprocess(newname, debug=False):

    errors = []

    # Renaming ourselves for ps et al.
    try:
        import procname
        procname.setprocname(newname)
    except:
        errors.append("Failed procname module")

    # Renaming ourselves for pkill et al.
    try:
        import ctypes
        # GNU/Linux style
        libc = ctypes.CDLL('libc.so.6')
        libc.prctl(15, newname, 0, 0, 0)
    except:
        errors.append("Failed GNU/Linux style")

    try:
        import dl
        # FreeBSD style
        libc = dl.open('/lib/libc.so.6')
        libc.call('setproctitle', newname + '\0')
        renamed = True
    except:
        errors.append("Failed FreeBSD style")

    if debug and errors:
        msg = [_("Errors occured while trying to change process name:")]
        for i in errors:
            msg.append("%s" % (i,))
        log.addwarning('\n'.join(msg))


def run():

    renameprocess('nicotine')

    import getopt
    import os.path
    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   "hc:p:tdvswb:",
                                   [
                                    "help",
                                    "config=",
                                    "plugins=",
                                    "profile",
                                    "enable-trayicon",
                                    "disable-trayicon",
                                    "enable-rgba",
                                    "disable-rgba",
                                    "version",
                                    "hidden",
                                    "bindip="
                                   ]
                                   )
    except getopt.GetoptError:
        # print help information and exit
        usage()
        sys.exit(2)

    if win32:
        try:
            mydir = os.path.join(os.environ['APPDATA'], 'nicotine')
        except KeyError:
            mydir, x = os.path.split(sys.argv[0])
        config = os.path.join(mydir, "config", "config")
        plugins = os.path.join(mydir, "plugins")
    else:
        config = os.path.join(os.path.expanduser("~"), '.nicotine', 'config')
        plugins = os.path.join(os.path.expanduser("~"), '.nicotine', 'plugins')

    profile = 0
    trayicon = 1
    tryrgba = False
    hidden = False
    bindip = None

    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        if o in ("-c", "--config"):
            config = a
        if o in ("-p", "--plugins"):
            plugins = a
        if o in ("-b", "--bindip"):
            bindip = a
        if o == "--profile":
            profile = 1
        if o in ("-t", "--enable-trayicon"):
            trayicon = 1
        if o in ("-d", "--disable-trayicon"):
            trayicon = 0
        if o in ('-r', '--enable-rgba'):
            tryrgba = True
        if o in ('-x', '--disable-rgba'):
            tryrgba = False
        if o in ('-s', '--hidden'):
            hidden = True
        if o in ("-v", "--version"):
            version()
            sys.exit()

    result = checkenv()

    if result is None:
        from pynicotine.gtkgui import frame

        app = frame.MainApp(config, plugins, trayicon,
                            tryrgba, hidden, bindip)
        if profile:
            import hotshot
            logfile = os.path.expanduser(config) + ".profile"
            profiler = hotshot.Profile(logfile)
            log.add(_("Starting using the profiler (saving log to %s)") %
                    logfile)
            profiler.runcall(app.MainLoop)
        else:
            app.MainLoop()
    else:
        print result

if __name__ == '__main__':
    try:
        run()
    except SystemExit:
        raise
    except Exception:
        import traceback
        traceback.print_exc()
