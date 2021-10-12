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

import os.path
import unittest
from pathlib import Path

import libmount

from lazysnapshotter import mounts, verify


class TestMounts(unittest.TestCase):
    def test_getBlockDeviceFromUUID(self):
        base = Path('/dev/disk/by-uuid')
        if not base.exists():
            raise Exception(
                f'Your dynamic device manager does not provide the directory "{str(base)}"')
        for x in base.iterdir():
            uuid = os.path.basename(x)
            if not verify.uuid(uuid):
                continue
            dev = mounts.getBlockDeviceFromUUID(uuid)
            self.assertIsNotNone(dev)
            self.assertTrue(dev.is_absolute())
        self.assertIsNone(mounts.getBlockDeviceFromUUID(
            '12345678-1234-1234-1234-123456789abc'))

    def test_getMountpoint(self):
        mtab = libmount.Table().parse_mtab()
        rootfs = mtab.find_target('/')
        self.assertEqual(str(mounts.getMountpoint(rootfs.source)), '/')
