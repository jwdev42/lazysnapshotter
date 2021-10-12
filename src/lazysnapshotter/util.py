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


def str_to_loglevel(loglevel: str):
    if loglevel == 'CRITICAL':
        return logging.CRITICAL
    elif loglevel == 'ERROR':
        return logging.ERROR
    elif loglevel == 'WARNING':
        return logging.WARNING
    elif loglevel == 'INFO':
        return logging.INFO
    elif loglevel == 'DEBUG':
        return logging.DEBUG
    else:
        return None
