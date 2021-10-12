#!/usr/bin/env python

# lazysnapshotter - a backup tool using btrfs
# Copyright (C) 2021 Joerg Walter
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

import fcntl
import subprocess
import os
from enum import Enum
from pathlib import Path

from lazysnapshotter import mount


def create_file(path: Path, size: int):
    """Create a file in "path" filled by zeroed bytes times "size\""""
    def create_bytes(size: int) -> bytes:
        return bytes([0] * size)
    units = 0
    times = 0
    for x in (1310720, 65536, 4096, 128, 8, 4, 2, 1):
        if size % x == 0:
            units = x
            times = int(size / x)
            break
    with open(path, 'wb') as f:
        for x in range(times):
            f.write(create_bytes(units))


def make_btrfs(dev: Path, label: str = None):
    cmd = ['mkfs.btrfs']
    if label is not None:
        cmd.append('--label')
        cmd.append(label)
    cmd.append(str(dev))
    subprocess.run(cmd).check_returncode()


def make_volume(dir_struct: dict, name: str, size: int):
    f = File(dir_struct[DirKey.LOOP_FILES].joinpath(name), size)
    loop = Loop(File(dir_struct[DirKey.LOOP_FILES].joinpath(name), size))
    loop.activate()
    make_btrfs(loop.device(), label=name)
    return Volume(loop)


def setup_dirs(base_path: Path) -> dict:
    dirs = dict()
    dirs[DirKey.ROOT] = base_path.resolve()
    dirs[DirKey.LOOP_FILES] = base_path.joinpath('loop')
    dirs[DirKey.MOUNTS] = base_path.joinpath('mnt')
    os.makedirs(dirs[DirKey.ROOT], mode=0o755)
    os.mkdir(dirs[DirKey.LOOP_FILES], mode=0o755)
    os.mkdir(dirs[DirKey.MOUNTS], mode=0o755)
    return dirs


def scrap_dirs(dirs: dict):
    os.rmdir(dirs[DirKey.MOUNTS])
    os.rmdir(dirs[DirKey.LOOP_FILES])
    os.rmdir(dirs[DirKey.ROOT])


class DirKey(Enum):
    ROOT = 0  # root directory of the entire test tree
    LOOP_FILES = 1  # contains all loop files
    MOUNTS = 2  # contains all mount points


class File:
    '''Represents a temporary file to be used as a loop device'''
    _path = None

    def __init__(self, path: Path, size: int):
        if size < 1:
            raise ValueError('size must be greater than or equal to 1')
        self._path = path.resolve()
        create_file(self._path, size * 1024 * 1024)

    def unlink(self):
        if self._path.exists():
            os.unlink(self._path)
            self._path = None

    def path(self) -> Path:
        return self._path

    def scrap(self):
        self.unlink()


class Loop:
    """Manages a loop device linked to a File"""
    _f: File = None
    dev: Path = None  # block device

    def __init__(self, f: File):
        self._f = f

    def _acquire_loop_device(self) -> Path:
        """Returns free loop device"""
        dev = None
        with open('/dev/loop-control', 'rb') as ctrl:
            num = fcntl.ioctl(ctrl, 0x4C82)  # LOOP_CTL_GET_FREE
            if num < 0:
                raise Exception('Could not acquire loop device')
            else:
                dev = Path(f'/dev/loop{num}')
        return dev

    def activate(self):
        if self.dev is not None:
            return
        loop = self._acquire_loop_device()
        proc = subprocess.run(['losetup', str(loop), self._f.path()])
        proc.check_returncode()
        self.dev = loop

    def deactivate(self):
        if self.dev is None:
            return
        proc = subprocess.run(['losetup', '-d', self.dev])
        proc.check_returncode()
        self.dev = None

    def device(self) -> Path:
        return self.dev

    def scrap(self):
        self.deactivate()
        self._f.scrap()


class Volume:
    '''Manages a volume on top of a loop-device'''
    _loop: Loop = None
    _mount_point: Path = None

    def __init__(self, loop: Loop):
        self._loop = loop

    def mountPoint(self) -> Path:
        return self._mount_point

    def mount(self, mount_point: Path):
        if self._mount_point is not None:
            raise Exception('Volume is already mounted')
        if not mount_point.exists():
            raise Exception('mount point does not exist')
        if self._loop.device() is None:
            raise Exception('loop device not active')
        mount.mount(self._loop.device(), mount_point.resolve())
        self._mount_point = mount_point.resolve()

    def umount(self):
        if self._mount_point is None:
            return
        mount.umount(self.mountPoint())
        self._mount_point = None

    def scrap(self):
        self.umount()
        self._loop.scrap()
