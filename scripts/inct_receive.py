#!/usr/bin/env python3
"""Restricted SSH receiver: stage TOKEN | activate TOKEN | status.

Install outside the public web root. Configure destination via the forced command,
never via SSH_ORIGINAL_COMMAND. Initial directory migration is an explicit admin task.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tarfile
import tempfile
import uuid

MAX_BYTES = 512 * 1024 * 1024
MAX_FILES = 10000
MANIFEST = '_inct_manifest.json'


def tree_manifest(directory: Path):
    files = {}
    for p in sorted(directory.rglob('*')):
        if p.is_symlink():
            raise ValueError('Links não permitidos na publicação')
        if p.is_file() and p != directory / MANIFEST:
            files[p.relative_to(directory).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return files


def token_for(manifest):
    return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()


def verify(directory: Path, token: str):
    manifest = json.loads((directory / MANIFEST).read_text())
    if not isinstance(manifest, dict) or token_for(manifest) != token or tree_manifest(directory) != manifest:
        raise ValueError('Manifesto/hash da transferência inválido')
    if not (directory / 'index.html').is_file() or not list((directory / 'json').glob('*.json')):
        raise ValueError('Publicação incompleta')
    for p in (directory / 'json').glob('*.json'):
        data = json.loads(p.read_text())
        if not data['informacoes_pessoais']['id_lattes']:
            raise ValueError('JSON inválido')
    return manifest


def unpack(stream, directory: Path):
    total, count, names = 0, 0, set()
    with tarfile.open(fileobj=stream, mode='r|') as archive:
        for entry in archive:
            name = PurePosixPath(entry.name)
            if (not entry.isfile() or name.is_absolute() or '..' in name.parts
                    or not name.parts or str(name) in names or '\\' in entry.name
                    or any(ord(c) < 32 for c in entry.name)):
                raise ValueError('Entrada insegura/duplicada no arquivo de publicação')
            count += 1
            total += entry.size
            if count > MAX_FILES or total > MAX_BYTES or entry.size < 0:
                raise ValueError('Limite da transferência excedido')
            names.add(str(name))
            p = directory / name
            p.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(entry) as source, p.open('xb') as dest:
                shutil.copyfileobj(source, dest)
            p.chmod(0o644)


@contextmanager
def receiver_lock(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    with (root / 'publish.lock').open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def receive(destination: Path, command: str, stream):
    destination = destination.absolute()
    # Sibling releases keep filesystem atomicity, web root and SSH restrictions simple.
    root = destination.parent / ('.' + destination.name + '-deploy')
    match = re.fullmatch(r'(stage|activate) ([a-f0-9]{64})', command)
    if command != 'status' and not match:
        raise ValueError('Comando não autorizado')
    with receiver_lock(root):
        releases = root / 'releases'
        releases.mkdir(exist_ok=True)
        if command == 'status':
            return {'destination': str(destination), 'exists': destination.exists(),
                    'managed': destination.is_symlink(),
                    'current': os.readlink(destination) if destination.is_symlink() else None}
        operation, token = match.groups()
        release = releases / token
        if release.is_symlink():
            raise ValueError('Release não pode ser link simbólico')
        if operation == 'stage':
            # Always drain/validate input; an interrupted retry must be harmless.
            with tempfile.TemporaryDirectory(prefix='incoming-', dir=root) as temp:
                temporary = Path(temp)
                unpack(stream, temporary)
                manifest = verify(temporary, token)
                for directory in temporary.rglob('*'):
                    if directory.is_dir():
                        directory.chmod(0o755)
                temporary.chmod(0o755)
                if release.exists():
                    verify(release, token)
                else:
                    os.rename(temporary, release)
            return {'outcome': 'staged', 'release': token, 'files': len(manifest)}
        verify(release, token)
        # Never migrate/replace an existing real directory over the automated channel.
        if destination.exists() and not destination.is_symlink():
            raise ValueError('Destino é diretório original: migração administrativa necessária antes de ativar')
        if destination.is_symlink():
            old = destination.resolve()
            if not old.is_relative_to(releases.resolve()):
                raise ValueError('Destino aponta para fora das releases gerenciadas')
        link = destination.parent / ('.inct-next-' + uuid.uuid4().hex)
        try:
            link.symlink_to(os.path.relpath(release, destination.parent), target_is_directory=True)
            os.replace(link, destination)
        finally:
            link.unlink(missing_ok=True)
        return {'outcome': 'activated', 'release': token}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--destination', required=True)
    args = p.parse_args()
    try:
        result = receive(Path(args.destination), os.environ.get('SSH_ORIGINAL_COMMAND', ''), sys.stdin.buffer)
        print(json.dumps(result))
    except Exception as exc:
        print(json.dumps({'outcome': 'failed', 'error': str(exc)}), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
