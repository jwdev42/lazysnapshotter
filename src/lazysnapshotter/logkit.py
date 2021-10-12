#!/usr/bin/env python

# lazysnapshotter - a backup tool using btrfs
# Copyright (C) 2020 Joerg Walter
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see https://www.gnu.org/licenses.

import logging
import sys
from pathlib import Path

from . import verify

log = None


class LogKit:

    datestr = '%Y-%m-%d %H:%M:%S'
    prestr = '%(asctime)s: %(levelname)s'
    poststr = '%(message)s'

    def __init__(self, loglevel):
        self.fmtstrs = dict()
        self.handlers = list()
        self.loglevel_priority = 0
        self.formatter = logging.Formatter(fmt='{} - {}'.format(LogKit.prestr, LogKit.poststr),
                                           datefmt=LogKit.datestr, style='%')
        messagehandler = logging.StreamHandler(sys.stderr)
        messagehandler.setFormatter(self.formatter)
        self.handlers.append(messagehandler)
        self.rootlogger = logging.getLogger()
        self.rootlogger.setLevel(loglevel)
        self.rootlogger.addHandler(messagehandler)

    def _updateFormatter(self):
        fstr = LogKit.prestr
        for v in self.fmtstrs.values():
            fstr = "{}, {}".format(fstr, v)
        fstr = "{} - {}".format(fstr, LogKit.poststr)
        self.formatter = logging.Formatter(
            fmt=fstr, datefmt=LogKit.datestr, style='%')
        for h in self.handlers:
            h.setFormatter(self.formatter)

    def addLogFile(self, path: Path):
        verify.requireAbsolutePath(path)
        fh = logging.FileHandler(path)
        fh.setFormatter(self.formatter)
        self.rootlogger.addHandler(fh)
        self.handlers.append(fh)

    def setLevel(self, loglevel, priority):
        if priority >= self.loglevel_priority:
            self.loglevel_priority = priority
            self.rootlogger.setLevel(loglevel)

    def fmtAppend(self, key: str, value: str):
        self.fmtstrs[key] = value
        self._updateFormatter()
