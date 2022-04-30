#!/usr/bin/env python

# lazysnapshotter - a backup tool using btrfs
# Copyright (C) 2020-2022 Joerg Walter
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

"""Python bindings for mount() and umount()"""

from pathlib import Path

import subprocess


class MountError(Exception):
    '''Thrown if mount or umount returns an error'''
    pass


def mount(source: Path, target: Path):
    '''Mount source to target'''
    cmd = ['mount']
    cmd.append(str(source))
    cmd.append(str(target))
    ret = subprocess.run(cmd)
    if ret.returncode != 0:
        raise MountError(f'mount failed with status {ret.returncode}')


def umount(target: Path):
    '''Unmount target'''
    cmd = ['umount']
    cmd.append(str(target))
    ret = subprocess.run(cmd)
    if ret.returncode != 0:
        raise MountError(f'umount failed with status {ret.returncode}')
