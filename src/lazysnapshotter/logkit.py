#!/usr/bin/python

#lazysnapshotter - a backup tool using btrfs
#Copyright (C) 2019  Joerg Walter
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

import logging
import sys
from . import verify
from pathlib import Path

class LogKit:
	
	frmttr = logging.Formatter(fmt = '%(asctime)s: %(levelname)s - %(message)s', style = '%')
	rootlogger = logging.getLogger()
	
	def __init__(self, loglevel):
		self.loglevel_priority = 0
		self.messagehandler = logging.StreamHandler(sys.stderr)
		self.messagehandler.setFormatter(LogKit.frmttr)
		LogKit.rootlogger = logging.getLogger()
		LogKit.rootlogger.setLevel(loglevel)
		LogKit.rootlogger.addHandler(self.messagehandler)
	
	def addLogFile(self, path: Path):
		verify.requireAbsolutePath(path)
		fh = logging.FileHandler(path)
		fh.setFormatter(LogKit.frmttr)
		LogKit.rootlogger.addHandler(fh)
	
	def setLevel(self, loglevel, priority):
		if priority >= self.loglevel_priority:
			self.loglevel_priority = priority
			LogKit.rootlogger.setLevel(loglevel)
