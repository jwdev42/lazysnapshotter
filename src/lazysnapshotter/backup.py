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


import logging
from dataclasses import dataclass
from datetime import datetime
from os import stat
from os.path import isdir
from pathlib import Path

import btrfsutil

from . import bnames, globalstuff, logkit, mounts, sessionkit, snapshotkit2, verify
from .transact import Transact
from .diff import snapshot_diff

logger = logging.getLogger(__name__)


@dataclass
class Entry:
    name: str  # name of the backup entry
    # true if backup drive should be unmounted after the backup has finished
    flag_unmount: bool = True
    keyfile: Path = None  # optional keyfile for luks
    snapshots: int = globalstuff.default_snapshots  # amount of snapshots to keep
    source: Path = None  # absolute path to the subvolume to backup.
    snapshot_dir: Path = None  # absolute path to the source's snapshot directory
    # relative path to the backup drive's snapshot directory starting at the drive's root directory
    backup_dir_relative: Path = None
    backup_volume = None  # block device or UUID of the backup partition

    def verify(self):
        verify.requireRightAmountOfSnapshots(self.snapshots)
        verify.requireAbsolutePath(self.source)
        verify.requireExistingPath(self.source)
        verify.requireAbsolutePath(self.snapshot_dir)
        verify.requireExistingPath(self.snapshot_dir)
        if self.backup_dir_relative is not None:
            verify.requireRelativePath(self.backup_dir_relative)
        if self.keyfile is not None:
            verify.requireAbsolutePath(self.keyfile)
            verify.requireExistingPath(self.keyfile)
        if not verify.uuid(self.backup_volume):
            verify.requireAbsolutePath(self.backup_volume)
            verify.requireExistingPath(self.backup_volume)


class NoAccess(Exception):
    pass


def send_and_receive(source: Path, snapshot_dir: Path, backup_dir: Path):
    """Backup subvolume source to a new snapshot inside backup_dir.
    The directory snapshot_dir must be on the source's drive, the directory
    backup_dir must be on the backup_drive. All specified paths must be accessible.
    If snapshot_dir and backup_dir have a common snapshot,
    the new snapshot in backup_dir will be a differential backup."""

    def check_access(p: Path, mask):
        """Check if the path exists and if the accessing user has the specified rights"""
        if not isdir(p):
            raise NoAccess('Directory "{}" does not exist'.format(str(p)))
        s = stat(p)
        if mask != s.st_mode & mask:
            raise NoAccess('Insufficient access to directory "{}"')

    check_access(source, 0o500)
    check_access(snapshot_dir, 0o700)
    check_access(backup_dir, 0o700)

    src = snapshotkit2.snapshot_dict(snapshotkit2.scan_dir(
        snapshot_dir, bnames.filter), bnames.parse_path)
    dst = snapshotkit2.snapshot_dict(snapshotkit2.scan_dir(
        backup_dir, bnames.filter), bnames.parse_path)
    common = snapshotkit2.biggest_common_snapshot(src, dst)
    try:
        trans = Transact(id=sessionkit.session.session_id, source=source,
                         snapshot_dir=snapshot_dir, backup_dir=backup_dir)
        trans.prepare(False)
        trans.create_prelim_snapshot()
        if common is None:
            trans.send(None, snapshot_diff)
        else:
            trans.send(common[0], snapshot_diff)
        trans.rename(_create_name(snapshot_dir, backup_dir))
    except Exception as e:
        trans.rollback()
        raise e


def purge_old_snapshots(directory: Path, keep: int):
    if keep < 1:
        raise globalstuff.Bug('Argument "keep" must be an integer >= 1')
    snapshots = snapshotkit2.snapshot_dict(
        snapshotkit2.scan_dir(directory, bnames.filter), bnames.parse_path)
    keys = list(snapshots)
    if len(keys) > keep:
        keys.sort(reverse=True)
        for r in range(keep):
            logger.debug(f'Keeping subvolume "{str(snapshots[keys[r]])}"')
            del snapshots[keys[r]]
        for v in snapshots.values():
            logger.debug(f'Deleting subvolume "{str(v)}"')
            btrfsutil.delete_subvolume(v)


def _create_name(snapshot_dir: Path, backup_dir: Path) -> str:
    """Returns the next file name available to store a backup by analyzing the existing backup file names"""
    snapshot = None
    src = snapshotkit2.snapshot_dict(snapshotkit2.scan_dir(
        snapshot_dir, bnames.filter_date(datetime.today())), bnames.parse_path)
    dst = snapshotkit2.snapshot_dict(snapshotkit2.scan_dir(
        backup_dir, bnames.filter_date(datetime.today())), bnames.parse_path)
    if src is not None and dst is not None:
        snapshot = bnames.newest(list(src) + list(dst))
    elif src is not None and dst is None:
        snapshot = bnames.newest(list(src))
    elif src is None and dst is not None:
        snapshot = bnames.newest(list(dst))
    if snapshot is not None:
        snapshot.index += 1
        return str(snapshot)
    ts = datetime.today()
    return str(bnames.BName(year=ts.year, month=ts.month, day=ts.day, index=1))


def run(entry: Entry):
    entry.verify()
    sessionkit.session.registerBackup(entry.name, globalstuff.config_backups)
    try:
        logkit.log.fmtAppend('backup_name', 'jobname: {}'.format(entry.name))
        logkit.log.fmtAppend('backup_id', 'jobid: {}'.format(
            str(sessionkit.session.session_id)))
        dev = mounts.device_by_state(entry.backup_volume)
        try:
            logger.info('Arming backup drive')
            dev.arm(sessionkit.session.getMountDir(create_parent=True, mkdir=True),
                    luks_name=str(sessionkit.session.session_id), keyfile=entry.keyfile)
            backup_dir = None
            if entry.backup_dir_relative is not None:
                backup_dir = dev.mountPoint().joinpath(entry.backup_dir_relative)
            else:
                backup_dir = dev.mountPoint()
            logger.info('Starting backup')
            send_and_receive(entry.source, entry.snapshot_dir, backup_dir)
            logger.info('Removing old snapshots')
            purge_old_snapshots(entry.snapshot_dir, entry.snapshots)
            purge_old_snapshots(backup_dir, entry.snapshots)
            logger.info('Syncing backup drive')
            trans_id = btrfsutil.start_sync(dev.mountPoint())
            btrfsutil.wait_sync(dev.mountPoint(), trans_id)
        finally:
            if entry.flag_unmount:
                logger.info('Disarming backup drive')
                dev.disarm()
            else:
                logger.info('Backup drive stays online through user request')
    finally:
        sessionkit.session.releaseBackup()
