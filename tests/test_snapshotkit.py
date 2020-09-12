#!/usr/bin/env python

#lazysnapshotter - a backup tool using btrfs
#Copyright (C) 2020 Joerg Walter
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

import datetime
import unittest
import tempfile
import os
from pathlib import Path
from lazysnapshotter import snapshotkit

class TestToIso(unittest.TestCase):
	
	def test_ytoiso(self):
		for x in range(0, 10000):
			s = snapshotkit.ytoiso(x)
			self.assertEqual(len(s), 4)
			self.assertEqual(int(s), x)
		self.assertRaises(ValueError, snapshotkit.ytoiso, -1)
		self.assertRaises(ValueError, snapshotkit.ytoiso, 10000)

	def test_mtoiso(self):
		for x in range(1, 13):
			s = snapshotkit.mtoiso(x)
			self.assertEqual(len(s), 2)
			self.assertEqual(int(s), x)
		self.assertRaises(ValueError, snapshotkit.mtoiso, -1)
		self.assertRaises(ValueError, snapshotkit.mtoiso, 0)
		self.assertRaises(ValueError, snapshotkit.mtoiso, 13)

	def test_dtoiso(self):
		for x in range(1, 32):
			s = snapshotkit.dtoiso(x)
			self.assertEqual(len(s), 2)
			self.assertEqual(int(s), x)
		self.assertRaises(ValueError, snapshotkit.mtoiso, -1)
		self.assertRaises(ValueError, snapshotkit.dtoiso, 0)
		self.assertRaises(ValueError, snapshotkit.dtoiso, 32)

class TestSnapshot(unittest.TestCase):
	
	def setUp(self):
		self._tempdir = tempfile.TemporaryDirectory()
	
	def tearDown(self):
		self._tempdir.cleanup()
	
	def test_create_snapshot(self):
		with tempfile.TemporaryDirectory() as source:
			sd = snapshotkit.SnapshotDir(Path(self._tempdir.name), test = True)
			ss = sd.createSnapshot(Path(source))
			expected_name = '{}.1'.format(datetime.date.today().isoformat())
			self.assertEqual(str(ss), expected_name)
	
	def test_snapshot_ordering(self):
		#samples 3,5,6,9,10 are malformed and ignored
		samples = ('2020-03-25.1', '1996-05-01.2', '1996-05-01.1', '1996-05-01.0', '2020-03-24.5', '12666-01-01.1', '983-06-23.3', '0974-04-30.23', '0001-01-01.6', '0000-02-15.3', '1970-01-32.8')
		expected = (samples[8], samples[7], samples[2], samples[1], samples[4], samples[0])
		for folder in samples:
			p = Path(self._tempdir.name, folder)
			os.mkdir(p)
		sd = snapshotkit.SnapshotDir(Path(self._tempdir.name), test = True)
		sd.scan()
		self.assertEqual(len(sd._snapshots), len(expected))
		i = 0
		while i < len(expected):
			self.assertEqual(str(sd._snapshots[i]), expected[i])
			i += 1
