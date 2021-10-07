#!/usr/bin/env python

#lazysnapshotter - a backup tool using btrfs
#Copyright (C) 2021 Joerg Walter
#
#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, version 3 of the License.
#
#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License
#along with this program.  If not, see https://www.gnu.org/licenses.

import btrfsutil
import os
import unittest
from lazysnapshotter import snapshotkit2
from pathlib import Path
from os.path import basename
from .testlib import dev

def make_subvolumes(path: Path, subvolumes) -> list:
	"""create a subvolumes inside of path for each element in iterable subvolumes"""
	paths = list()
	for s in subvolumes:
		p = path.joinpath(str(s))
		btrfsutil.create_subvolume(p)
		paths.append(p)
	if len(paths) > 0:
		return paths
	return None

def filter_int(p: Path) -> bool:
	'''Returns true if p's basename can be converted to an Integer'''
	try:
		int(basename(p))
	except ValueError:
		return False
	return True

def conv_int(data) -> int:
	return int(str(basename(data)))

class TestSnapshotkit2(unittest.TestCase):
	def test_scandir(self):
		#setup
		dirs = dev.setup_dirs(Path('/tmp/lazytest/test_scandir'))
		mnt_point = dirs[dev.DirKey.MOUNTS].joinpath('test')
		os.mkdir(mnt_point, mode = 0o755)
		vol = dev.make_volume(dirs, 'test', 50)
		vol.mount(mnt_point)
		try:
			self.assertIsNone(snapshotkit2.scan_dir(mnt_point)) #no subvolumes
			os.mkdir(mnt_point.joinpath('notasnapshot'))
			self.assertIsNone(snapshotkit2.scan_dir(mnt_point)) #still no subvolumes
			btrfsutil.create_subvolume(mnt_point.joinpath('0'))
			self.assertTrue(len(snapshotkit2.scan_dir(mnt_point)) == 1) #one subvolume
			make_subvolumes(mnt_point, range(1, 5))
			self.assertTrue(len(snapshotkit2.scan_dir(mnt_point)) == 5) #five subvolumes
			btrfsutil.create_subvolume(mnt_point.joinpath('test'))
			self.assertTrue(len(snapshotkit2.scan_dir(mnt_point)) == 6) #six subvolumes
			self.assertTrue(len(snapshotkit2.scan_dir(mnt_point, filter_func = filter_int)) == 5) #five subvolumes with names that can be converted to integers
		finally:
			#teardown
			vol.scrap()
			os.rmdir(mnt_point)
			dev.scrap_dirs(dirs)
	
	def test_biggest_common_snapshot(self):
		#setup
		dirs = dev.setup_dirs(Path('/tmp/lazytest/test_biggest_common_snapshot'))
		m1 = dirs[dev.DirKey.MOUNTS].joinpath('1')
		m2 = dirs[dev.DirKey.MOUNTS].joinpath('2')
		os.mkdir(m1, mode = 0o755)
		os.mkdir(m2, mode = 0o755)
		v1 = dev.make_volume(dirs, '1', 50)
		v2 = dev.make_volume(dirs, '2', 50)
		v1.mount(m1)
		v2.mount(m2)
		try:
			make_subvolumes(m1, [8,5,2,6,0,'test',3,'blah'])
			make_subvolumes(m2, [7,0,2,9,5,'test',6,'blah'])
			a = snapshotkit2.snapshot_dict(snapshotkit2.scan_dir(m1, filter_func = filter_int), conv_int)
			b = snapshotkit2.snapshot_dict(snapshotkit2.scan_dir(m2, filter_func = filter_int), conv_int)
			common = snapshotkit2.biggest_common_snapshot(a, b)
			self.assertTrue(basename(common[0]) == basename(common[1]))
			self.assertTrue(int(str(basename(common[0]))) == 6)
		finally:
			#teardown
			v2.scrap()
			v1.scrap()
			os.rmdir(m2)
			os.rmdir(m1)
			dev.scrap_dirs(dirs)
