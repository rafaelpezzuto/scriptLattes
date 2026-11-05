#!/usr/bin/env python3
"""Stage an immutable local release through a restricted SSH receiver.

Default is stage-only. --activate requires prior administrative migration of the
remote public directory to the receiver's managed symlink structure.
"""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

from inct_receive import MANIFEST, MAX_BYTES, MAX_FILES, token_for, tree_manifest
from inct_update import atomic_json, lock, validate_output


def package(output: Path, archive: Path):
    manifest = tree_manifest(output)
    if (output / MANIFEST).exists():
        raise ValueError('Saída contém manifesto reservado')
    if len(manifest) + 1 > MAX_FILES:
        raise ValueError('Publicação excede limite de arquivos')
    size = sum((output / name).stat().st_size for name in manifest)
    data = json.dumps(manifest, sort_keys=True).encode()
    if size + len(data) > MAX_BYTES:
        raise ValueError('Publicação excede limite de tamanho')
    with tarfile.open(archive, 'w') as bundle:
        for name in manifest:
            bundle.add(output / name, arcname=name, recursive=False)
        entry = tarfile.TarInfo(MANIFEST)
        entry.size = len(data)
        entry.mode = 0o644
        bundle.addfile(entry, io.BytesIO(data))
    return token_for(manifest)


def ssh(args, command: str, archive=None):
    if not args.host or args.host.startswith('-') or any(c.isspace() for c in args.host):
        raise ValueError('Host SSH inválido')
    argv = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'ConnectTimeout=15', '-o', 'ServerAliveInterval=15',
            '-o', 'ServerAliveCountMax=3']
    if args.ssh_config:
        argv += ['-F', str(Path(args.ssh_config).resolve())]
    argv += [args.host, command]
    result = subprocess.run(argv, stdin=archive if archive else subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=args.timeout, check=False)
    if result.returncode:
        raise RuntimeError(f'SSH retornou {result.returncode}: {result.stderr.decode(errors="replace")[-2000:]}')
    try:
        return json.loads(result.stdout)
    except (ValueError, UnicodeError) as exc:
        raise RuntimeError('Resposta inválida do receptor') from exc


def publish(args):
    state = Path(args.state_dir).resolve()
    # Same lock as updater: immutable release cannot be switched under publication.
    with lock(state):
        current = state / 'current'
        if not current.is_symlink():
            raise ValueError('Nenhuma geração local disponível')
        release = current.resolve(strict=True)
        if not release.is_relative_to(state / 'releases'):
            raise ValueError('Release fora da área gerenciada')
        metadata = json.loads((release / 'state.json').read_text())
        if metadata.get('offline') and args.activate and not args.allow_offline:
            raise ValueError('Geração offline: ativação exige --allow-offline explícito')
        output = release / 'output'
        validate_output(output, metadata['curricula'])
        with tempfile.TemporaryDirectory(prefix='publish-', dir=state) as temp:
            archive = Path(temp) / 'output.tar'
            token = package(output, archive)
            with archive.open('rb') as stream:
                result = ssh(args, 'stage ' + token, stream)
            if result.get('outcome') != 'staged' or result.get('release') != token:
                raise RuntimeError('Receptor não confirmou a transferência esperada')
        if args.activate:
            result = ssh(args, 'activate ' + token)
            if result.get('outcome') != 'activated' or result.get('release') != token:
                raise RuntimeError('Receptor não confirmou a ativação esperada')
        atomic_json(state / 'last-publication.json', {
            'local_release': str(release), 'remote': args.host, 'result': result})
        return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state-dir', required=True)
    p.add_argument('--host', required=True, help='Alias SSH com chave dedicada e comando forçado')
    p.add_argument('--ssh-config')
    p.add_argument('--activate', action='store_true')
    p.add_argument('--allow-offline', action='store_true')
    p.add_argument('--timeout', type=int, default=300)
    args = p.parse_args()
    try:
        if args.timeout <= 0:
            raise ValueError('Timeout deve ser positivo')
        print(json.dumps(publish(args)))
    except Exception as exc:
        print(json.dumps({'outcome': 'failed', 'error': str(exc)}), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
