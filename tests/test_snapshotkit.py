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

import unittest
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

