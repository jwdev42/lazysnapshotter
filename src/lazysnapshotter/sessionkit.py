#!/usr/bin/env python

# lazysnapshotter - a backup tool using btrfs
# Copyright (C) 2020 Joerg Walter
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

import csv
import fcntl
import logging
import os
import os.path
import uuid
from pathlib import Path

from . import globalstuff, verify


logger = logging.getLogger(__name__)
session = None


class DuplicateJobException(Exception):
    pass


class MalformedCsvEntryException(Exception):
    pass


class JobDialect(csv.Dialect):
    delimiter = ':'
    escapechar = '\\'
    quoting = csv.QUOTE_NONE
    lineterminator = '\n'


class JobFile:

    columns = ('name', 'configfile', 'pid', 'jobid')

    def __init__(self, jobfile: Path):
        self.jobfile = jobfile

    def read(self) -> list:
        ret = list()
        with open(self.jobfile, 'r') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            reader = csv.reader(f, dialect=JobDialect)
            for l in reader:
                ret.append(l)
        return ret

    def createFile(self):
        if not self.jobfile.exists():
            with open(self.jobfile, 'w'):
                pass

    def query(self, query: dict) -> list:
        ret = list()
        with open(self.jobfile, 'r') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            reader = csv.reader(f, dialect=JobDialect)
            for l in reader:
                match = True
                for k, v in query.items():
                    try:
                        index = JobFile.columns.index(k)
                    except ValueError:
                        raise globalstuff.Bug('Malformed query: Key \'{}\' is not part of the allowed query keys {}!'.format(
                            k, str(JobFile.columns)))
                    if index >= len(l):
                        match = False
                        break
                    if l[index] != v:
                        match = False
                        break
                if match:
                    ret.append(l)
        return ret

    def register(self, job_name, configfile, job_id):
        verify.requireAbsolutePath(configfile)
        l = self.query(
            {JobFile.columns[0]: job_name, JobFile.columns[1]: str(configfile)})
        if len(l) == 0:
            with open(self.jobfile, 'r') as filelock:
                fcntl.flock(filelock.fileno(), fcntl.LOCK_EX)
                with open(self.jobfile, 'a') as f:
                    writer = csv.writer(f, dialect=JobDialect)
                    writer.writerow(
                        [job_name, str(configfile), str(os.getpid()), str(job_id)])
                    logger.debug('Backup job recorded in JobFile.')
        else:
            raise DuplicateJobException(
                'The same backup job is already running!')

    def release(self, job_id):
        filebuffer = list()
        with open(self.jobfile, 'r') as f_read:
            fcntl.flock(f_read.fileno(), fcntl.LOCK_EX)
            reader = csv.reader(f_read, dialect=JobDialect)
            for l in reader:
                if len(l) != 4:
                    raise MalformedCsvEntryException(
                        'JobFile records must have 4 columns.')
                if l[3] == str(job_id):
                    logger.debug('Found backup job in JobFile for release!')
                else:
                    filebuffer.append(l)
            with open(self.jobfile, 'w') as f_write:
                writer = csv.writer(f_write, dialect=JobDialect)
                for wl in filebuffer:
                    writer.writerow(wl)


class RuntimePathManager:

    dir_keys = ('mounts', 'pid')
    file_keys = ('jobs', 'pidfile')

    def __init__(self, rundir: Path):
        verify.requireAbsolutePath(rundir)
        self.rootdir = rundir

    def getDirectory(self, key, create=False) -> Path:
        directory = None
        if key == 'mounts':
            directory = self.rootdir / Path('mounts')
        elif key == 'pid':
            directory = self.rootdir / Path('pid')
        else:
            raise globalstuff.Bug('"{}" is an invalid key.'.format(key))
        if create == True and not directory.exists():
            directory.mkdir(parents=True)
        return directory

    def getFile(self, key, create_dir=False) -> Path:
        fp = None
        if key == 'jobs':
            fp = self.rootdir / Path('jobs')
        elif key == 'pidfile':
            d = self.getDirectory('pid', create_dir)
            fp = d / Path('{}.pid'.format(str(os.getpid())))
        else:
            raise globalstuff.Bug('"{}" is an invalid key.'.format(key))
        return fp


class Session:

    def __init__(self, rundir: Path):
        self.rpm = RuntimePathManager(rundir)
        self.custom_mountdir = None
        self.session_id = uuid.uuid4()
        self.jobs = None

    def setup(self):
        self.pidfile = self.rpm.getFile('pidfile', create_dir=True)
        logger.debug('Creating pidfile "%s"', str(self.pidfile))
        fp = open(self.pidfile, 'w')
        fp.close()
        jobfile = self.rpm.getFile('jobs', create_dir=True)
        self.jobs = JobFile(jobfile)
        self.jobs.createFile()

    def cleanup(self):
        if hasattr(self, 'pidfile'):
            logger.debug('Deleting pidfile "%s"', str(self.pidfile))
            if self.pidfile.exists():
                self.pidfile.unlink()

    def registerBackup(self, job_name, configfile):
        self.jobs.register(job_name, configfile, self.session_id)

    def releaseBackup(self):
        self.jobs.release(self.session_id)

    def customizeMountDir(self, mountdir: Path):
        verify.requireAbsolutePath(mountdir)
        verify.requireExistingPath(mountdir)
        self.custom_mountdir = mountdir

    def getMountDir(self, create_parent=False, mkdir=False):
        mountdir = None
        if self.custom_mountdir is None:
            mounts = self.rpm.getDirectory('mounts', create_parent)
            mountdir = mounts / Path(str(self.session_id))
        else:
            mountdir = self.custom_mountdir / Path(str(self.session_id))
        if mkdir:
            os.mkdir(mountdir, mode=0o755)
        return mountdir
