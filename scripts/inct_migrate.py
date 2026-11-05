#!/usr/bin/env python3
"""One-time administrative migration of a real public directory to a release link.

Dry-run by default. --execute uses Linux renameat2(RENAME_EXCHANGE) unless the
operator explicitly authorizes --allow-maintenance-window for two renames on
NFS. The entire original directory becomes the backup; the two-rename method
restores the original path if installing the new link fails.
Never authorize this script through the publisher's forced SSH command.
"""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import uuid

from inct_receive import receiver_lock, verify


def exchange(left: Path, right: Path):
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        rename = libc.renameat2
    except AttributeError as exc:
        raise RuntimeError('renameat2 indisponível; nenhuma migração realizada') from exc
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(left), -100, os.fsencode(right), 2) != 0:
        code = ctypes.get_errno()
        raise OSError(code, 'Troca atômica não suportada/concluída: ' + os.strerror(code))


def two_renames(destination, backup, release):
    link = destination.parent / ('.inct-migration-' + uuid.uuid4().hex)
    link.symlink_to(os.path.relpath(release, destination.parent), target_is_directory=True)
    try:
        os.rename(destination, backup)
        try:
            os.replace(link, destination)
        except BaseException:
            try:
                os.rename(backup, destination)
            except OSError as exc:
                raise RuntimeError(f'Rollback falhou: diretório original preservado em {backup}') from exc
            raise
    finally:
        if link.is_symlink():
            link.unlink()


def migrate(destination: Path, token: str, execute=False, maintenance_window=False):
    destination = destination.absolute()
    if not re.fullmatch('[a-f0-9]{64}', token):
        raise ValueError('Token inválido')
    root = destination.parent / ('.' + destination.name + '-deploy')
    with receiver_lock(root):
        if destination.is_symlink() or not destination.is_dir():
            raise ValueError('Migração inicial exige um diretório real existente')
        release = root / 'releases' / token
        if release.is_symlink():
            raise ValueError('Release não pode ser symlink')
        result = {'outcome': 'migration-plan', 'destination': str(destination),
                  'release': token, 'files': len(verify(release, token)),
                  'method': 'two-renames' if maintenance_window else 'atomic-exchange'}
        if not execute:
            return result
        backups = root / 'backups'
        backups.mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup = backups / ('original-' + stamp + '-' + uuid.uuid4().hex[:8])
        if maintenance_window:
            two_renames(destination, backup, release)
        else:
            # Target is relative to its FINAL location, not this temporary location.
            backup.symlink_to(os.path.relpath(release, destination.parent), target_is_directory=True)
            try:
                exchange(destination, backup)
            finally:
                # On success `backup` is the original real directory: never remove it.
                if backup.is_symlink():
                    backup.unlink()
        result.update(outcome='migrated', backup=str(backup))
        return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--destination', required=True)
    p.add_argument('--release', required=True)
    p.add_argument('--execute', action='store_true')
    p.add_argument('--allow-maintenance-window', action='store_true',
                   help='Autoriza breve intervalo entre duas renomeações (NFS)')
    args = p.parse_args()
    try:
        print(json.dumps(migrate(Path(args.destination), args.release, args.execute,
                                 args.allow_maintenance_window)))
    except Exception as exc:
        print(json.dumps({'outcome': 'failed', 'error': str(exc)}), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
