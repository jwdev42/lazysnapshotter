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


import sys
from pathlib import Path


config_backups = Path('/etc/lazysnapshotter/backups.conf')
debug_mode = False
default_snapshots = 2
max_snapshots = sys.maxsize - 1


class Bug(Exception):
    """Exception that is thrown if the program enters an invalid state likely caused by a programming error"""
    pass
