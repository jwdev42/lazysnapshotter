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

import unittest
from lazysnapshotter import bnames


class TestBName(unittest.TestCase):
    def test_lt(self):
        base = bnames.BName(2020, 6, 13, 6)
        smaller = ['2020-05-14.1', '2020-06-13.5', '2020-06-12.5', '2020-06-12.6',
                   '2020-05-13.6', '2019-06-13.6']
        for e in smaller:
            s = bnames.parse(e)
            self.assertLess(s, base)
            self.assertFalse(base < s)

    def test_gt(self):
        base = bnames.BName(2020, 6, 13, 6)
        bigger = ['2020-06-13.7', '2020-06-14.6',
                  '2020-07-13.6', '2021-06-13.6']
        for e in bigger:
            big = bnames.parse(e)
            self.assertGreater(big, base)
            self.assertFalse(base > big)

    def test_parse(self):
        malformed = ['10000-01-01.1', '1956-02-13.0', '42', '666-04-23.1',
                     '2001-01-96.23', '0000-00-00.1', '1999-13-01.2', '1999-12-32.2']
        for x in malformed:
            with self.assertRaises(bnames.ParseError):
                bnames.parse(x)
        # testing all years is too slow
        years = (1, 9, 10, 99, 100, 999, 1000, 9999)
        for y in years:
            months = range(1, 12)
            for m in months:
                days = range(1, 31)
                for d in days:
                    indexes = (1, 9, 10, 99, 100, 999, 1000)
                    for i in indexes:
                        str_repr = '{:04d}-{:02d}-{:02d}.{:d}'.format(
                            y, m, d, i)
                        n = bnames.parse(str_repr)
                        self.assertEqual(str(n), str_repr)
