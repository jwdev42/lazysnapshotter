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
import os
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def _send_command(src: Path, parent: Path):
    cmd = [shutil.which('btrfs'), 'send']
    if parent is not None:
        cmd.append('-p')
        cmd.append(str(parent))
    cmd.append(str(src))
    return cmd


def _receive_command(dst: Path):
    return [shutil.which('btrfs'), 'receive', '-e', str(dst)]


def snapshot_diff(src: Path, dst: Path, parent: Path):
    """Handles btrfs-send and btrfs-receive, designed to be used as a higher-order function in transact.send()"""
    try:
        procs = None
        # setup pipe
        pipe = os.pipe()
        pread = pipe[0]
        pwrite = pipe[1]
        os.set_inheritable(pread, True)
        os.set_inheritable(pwrite, True)

        # initialize subprocesses
        procs = [subprocess.Popen(_send_command(src, parent), stdout=pwrite, close_fds=False),
                 subprocess.Popen(_receive_command(dst), stdin=pread, close_fds=False)]

        # wait for subprocesses to finish
        for p in procs:
            p.wait()

        # evaluate return values
        for p in procs:
            if p.returncode != 0:
                raise SubprocessError(
                    'Subprocess returned code {}: {}'.format(p.returncode, str(p)))

    except Exception as e:
        for p in procs:
            logger.critical('Killing subprocess: {}'.format(str(p)))
            p.kill()
        raise e
    finally:
        os.close(pipe[0])
        os.close(pipe[1])


class SubprocessError(Exception):
    pass
