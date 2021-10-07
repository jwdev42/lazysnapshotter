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

"""Manage btrfs snapshots"""

from pathlib import Path
import btrfsutil

def scan_dir(p: Path, filter_func = None):
	"""Scans Path p for btrfs snapshots, returns the paths of all found snapshots as a list or None if no snapshots were found.
	Snapshots can be filtered by passing a function as filter_func that takes a path and returns a boolean expression.
	If such a function is present, only those snapshots where the filter function returns true will be returned in the snapshot list."""
	snapshots = list()
	for f in p.iterdir():
		if btrfsutil.is_subvolume(f):
			if filter_func is not None:
				if filter_func(f):
					snapshots.append(f)
			else:
				snapshots.append(f)
	if len(snapshots) < 1:
		return None
	return snapshots

def snapshot_dict(snapshots, key_func):
	"""Takes a list of snapshots (likely generated by scan_dir) and puts every element into a dictionary.
	The function key_func takes the snapshot as a parameter and returns its dictionary key."""
	if snapshots is None:
		return None
	d = dict()
	for s in snapshots:
		d[key_func(s)] = s
	return d

def biggest_common_snapshot(a, b):
	"""Returns the biggest common snapshot of snapshot dicts a and b. It is determined by reverse sorting the dictionary keys.
	If such a snapshot is found, a tuple with 2 elements (snapshot a and snapshot b) will be returned.
	If no common snapshot is found, None will be returned."""
	if a is None or b is None:
		return None
	keys = list(a.keys())
	keys.sort(reverse = True)
	for key in keys:
		if key in b:
			return (a[key], b[key])
	return None
