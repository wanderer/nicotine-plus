#!/bin/sh

brew install \
  create-dmg \
  gdk-pixbuf \
  gobject-introspection \
  gspell \
  gtk+3 \
  libnotify \
  miniupnpc \
  pygobject3 \
  taglib \
  upx

# pip should not pick up our setup.cfg
cd pynicotine
pip3 install flake8 pyinstaller==3.6 pytaglib pytest
cd ..
