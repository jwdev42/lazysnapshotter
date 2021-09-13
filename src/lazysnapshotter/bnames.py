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

from dataclasses import dataclass

from . import verify

@dataclass
class BName:
	"""Representation of a snapshot's name"""
	year: int
	month: int
	day: int
	index: int
	
	def __str__(self):
		if not (0 < self.year < 10000 and 0 < self.month < 13 and 0 < self.day < 32 and 0 < self.index):
			raise ValueError('Date or index out of range')
		return '{:04d}-{:02d}-{:02d}.{:d}'.format(self.year, self.month, self.day, self.index)
	
	def __eq__(self, other):
		if not isinstance(other, BName):
			raise TypeError('Cannot compare type "{}" to type "{}"'.format(type(self), type(other)))
		if self.year == other.year and self.month == other.month\
		and self.day == other.day and self.index == other.index:
			return True
		return False
	
	def __lt__(self, other):
		if not isinstance(other, BName):
			raise TypeError('Cannot compare type "{}" to type "{}"'.format(type(self), type(other)))
		if self.year < other.year:
			return True
		elif self.year == other.year:
			if self.month < other.month:
				return True
			elif self.month == other.month:
				if self.day < other.day:
					return True
				elif self.day == other.day:
					if self.index < other.index:
						return True
		return False
		
		def __gt__(self, other):
			return other < self

def parse(name: str) -> BName:
	if len(name) < 12:
		raise ParseError('Input string too short')
	date = name[:10]
	if not verify.isodate(date):
		raise ParseError('Malformed date string')
	if name[10:11] != '.':
		raise ParseError('Expected "." at pos 10')
	index = name[11:]
	if not verify.snapshot_revision(index):
		raise ParseError('Malformed Index')
	return BName(int(name[:4]), int(name[5:7]), int(name[8:10]), int(name[11:]))
			
class ParseError(Exception):
	pass
