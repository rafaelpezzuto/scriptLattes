#!/usr/bin/env python3
"""Transactional INCT refresh. Paths in .config are relative to --project-root."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import unicodedata
import uuid

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 1
HASH_SCHEMA = 2


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_json(path: Path, value):
    temp = path.with_name(path.name + '.tmp')
    with temp.open('w', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


@contextmanager
def lock(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'update.lock').open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('Outra atualização está em execução') from exc
        yield


def load_config(path: Path, root: Path):
    values = {}
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        line = line.split('#', 1)[0].strip()
        if not line:
            continue
        if '=' not in line:
            raise ValueError(f'Configuração inválida na linha {number}: falta =')
        key, value = (p.strip() for p in line.split('=', 1))
        values[key] = value
    list_path = Path(values['global-arquivo_de_entrada'])
    if not list_path.is_absolute():
        list_path = root / list_path
    list_path = list_path.resolve(strict=True)
    ids = []
    for line in list_path.read_text(encoding='utf-8').splitlines():
        line = line.split('#', 1)[0].strip()
        if not line:
            continue
        # Match Grupo's delimiter precedence.
        parts = line.split(',')
        if len(parts) < 2 and ';' in line:
            parts = line.split(';')
        if len(parts) < 2 and '\t' in line:
            parts = line.split('\t')
        identifier = parts[0].strip()
        if not re.fullmatch(r'[0-9]{16}', identifier):
            raise ValueError(f'A rotina incremental exige ID Lattes de 16 dígitos: {identifier!r}')
        ids.append(identifier)
    if not ids or len(set(ids)) != len(ids):
        raise ValueError('Lista vazia ou IDs Lattes duplicados')
    values['global-arquivo_de_entrada'] = str(list_path)
    return values, ids


def inspect_cv(path: Path, identifier: str):
    from bs4 import BeautifulSoup

    if path.stat().st_size > 30_000_000:
        raise ValueError(f'Currículo excessivamente grande: {identifier}')
    html = path.read_text(encoding='utf-8')
    if not re.search(r'</body>\s*</html>\s*$', html, re.IGNORECASE):
        raise ValueError(f'Documento HTML incompleto: {identifier}')
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one('.layout-cell-pad-main')
    name = soup.select_one('h2.nome')
    if content is None or name is None or not name.get_text(strip=True):
        raise ValueError(f'HTML não reconhecido como currículo: {identifier}')
    text = content.get_text(' ', strip=True)
    found = re.search(r'ID Lattes:\s*([0-9]{16})', text)
    updated = re.search(r'Última atualização do currículo em\s*(\d{2}/\d{2}/\d{4})', text)
    if not found or found.group(1) != identifier or not updated or 'Identificação' not in text:
        raise ValueError(f'Identidade/metadados inválidos no currículo: {identifier}')
    datetime.strptime(updated.group(1), '%d/%m/%Y')
    # Footer is outside this node. Ignore UI code/presentation, but retain link targets
    # (DOIs, collaborators) since they can affect parser output without changing text.
    for node in content.select('script, style, noscript'):
        node.decompose()
    normalized = unicodedata.normalize('NFC', ' '.join(content.stripped_strings))
    # Lattes places its response-generation timestamp INSIDE the main content.
    # It changes on every request, unlike the researcher's actual update date.
    normalized = re.sub(
        r'Página gerada pelo Sistema Currículo Lattes em \d{2}/\d{2}/\d{4} às \d{2}:\d{2}:\d{2}',
        '', normalized)
    normalized = re.sub(r'\s+([.,;:!?])', r'\1', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    links = sorted({a['href'] for a in content.select('a[href]')
                    if not a['href'].startswith(('#', 'javascript:'))})
    return {'hash': digest(json.dumps([normalized, links], ensure_ascii=False).encode()),
            'updated_at': updated.group(1), 'name': name.get_text(' ', strip=True)}


def fingerprint(root: Path, values: dict):
    hasher = hashlib.sha256()
    # Source AND templates/assets/dependencies. Include dirty source, not just git SHA.
    files = [root / 'scriptLattes.py', root / 'requirements.txt', Path(__file__)]
    for directory in ('scriptLattes', 'css', 'js'):
        files.extend(p for p in (root / directory).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    for path in sorted(set(files)):
        hasher.update(str(path.relative_to(root) if path.is_relative_to(root) else path.name).encode())
        hasher.update(path.read_bytes())
    relevant = {k: v for k, v in values.items()
                if k not in ('global-diretorio_de_saida', 'global-diretorio_de_armazenamento_de_cvs')}
    hasher.update(json.dumps(relevant, sort_keys=True).encode())
    for key, value in values.items():
        if 'arquivo' in key and value:
            p = Path(value)
            if not p.is_absolute():
                p = root / p
            hasher.update(p.read_bytes())
    # "hoje" can occur in researcher membership periods as well as global config.
    hasher.update(str(datetime.now().year).encode())
    hasher.update(f'{SCHEMA}:{sys.version_info[:2]}'.encode())
    return hasher.hexdigest()


def run_process(argv, root: Path, log: Path, timeout: int):
    with log.open('ab') as output:
        process = subprocess.Popen(argv, cwd=root, stdout=output, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
        except BaseException as exc:
            # Reap the entire process group on timeout OR operator cancellation,
            # including ChromeDriver/Chromium children of the downloader.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            if isinstance(exc, subprocess.TimeoutExpired):
                raise RuntimeError(f'Tempo limite excedido ({timeout}s); log: {log}') from exc
            raise
        if code:
            raise RuntimeError(f'Processo retornou {code}; log: {log}')


def fetch_cv(identifier: str, directory: Path, root: Path, log: Path, timeout: int):
    code = ('from scriptLattes.baixaLattes import baixaCVLattes; import sys; '
            'baixaCVLattes(sys.argv[1], sys.argv[2])')
    run_process([sys.executable, '-c', code, identifier, str(directory)], root, log, timeout)


def validate_output(output: Path, ids):
    if not (output / 'index.html').is_file() or (output / 'index.html').stat().st_size == 0:
        raise ValueError('Geração sem index.html válido')
    actual = []
    for p in (output / 'json').glob('*.json'):
        data = json.loads(p.read_text(encoding='utf-8'))
        info = data['informacoes_pessoais']
        if not info.get('nome_completo'):
            raise ValueError(f'JSON sem nome: {p.name}')
        actual.append(info['id_lattes'])
    if sorted(actual) != sorted(ids):
        raise ValueError(f'JSONs incompletos/duplicados: esperados {len(ids)}, encontrados {len(actual)}')
    if any(p.is_symlink() for p in output.rglob('*')):
        raise ValueError('Saída contém link simbólico inesperado')


def generate(root: Path, config: Path, log: Path, timeout: int):
    run_process([sys.executable, str(root / 'scriptLattes.py'), str(config)], root, log, timeout)


def refresh(args):
    root = Path(args.project_root).resolve()
    state = Path(args.state_dir).resolve()
    with lock(state):
        values, ids = load_config(Path(args.config).resolve(), root)
        wanted = fingerprint(root, values)
        current = state / 'current'
        baseline = {}
        if current.is_symlink():
            if not current.resolve(strict=True).is_relative_to(state / 'releases'):
                raise ValueError('current aponta para fora das releases gerenciadas')
            baseline = json.loads((current / 'state.json').read_text())
            if baseline.get('schema') != SCHEMA:
                raise ValueError('Versão de estado incompatível; migração explícita necessária')
        elif current.exists():
            raise ValueError('current precisa ser um link gerenciado pela rotina')
        seed = Path(args.seed_cache).resolve() if args.seed_cache else None
        cache = current / 'cache' if baseline else seed
        now = datetime.now(timezone.utc).isoformat()
        logs = state / 'logs'
        logs.mkdir(exist_ok=True)
        run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
        log = logs / (run_id + '.log')
        records, changed = {}, []
        with tempfile.TemporaryDirectory(prefix='staging-', dir=state) as temporary:
            staging = Path(temporary)
            cvs = staging / 'cache'
            cvs.mkdir()
            for identifier in ids:
                target = cvs / identifier
                old = None
                if cache and (cache / identifier).is_file():
                    old = inspect_cv(cache / identifier, identifier)
                if args.offline:
                    if old is None:
                        raise ValueError(f'Currículo ausente no cache: {identifier}')
                    shutil.copyfile(cache / identifier, target)
                else:
                    fetch_cv(identifier, cvs, root, log, args.fetch_timeout)
                records[identifier] = inspect_cv(target, identifier)
                # Recompute baseline from the preserved HTML when the comparison
                # algorithm changes, rather than treating all legacy hashes as edits.
                previous = (old if baseline.get('hash_schema') != HASH_SCHEMA
                            else baseline.get('curricula', {}).get(identifier, old))
                if previous is None or previous['hash'] != records[identifier]['hash']:
                    changed.append(identifier)
            needs_build = (args.force or not baseline or wanted != baseline.get('fingerprint')
                           or (baseline.get('offline', False) and not args.offline)
                           or bool(changed) or set(ids) != set(baseline.get('curricula', {})))
            if baseline and not needs_build:
                validate_output(current / 'output', ids)
            result = {'checked_at': now, 'offline': args.offline, 'changed_ids': changed,
                      'members': len(ids), 'needs_build': needs_build,
                      'outcome': 'check-only' if args.check_only else 'unchanged',
                      'release': str(current.resolve()) if baseline else None}
            if args.check_only or not needs_build:
                atomic_json(state / 'last-check.json', result)
                return result
            output = staging / 'output'
            # Snapshot input files: release remains reproducible if live config/list changes later.
            for key, value in list(values.items()):
                if 'arquivo' in key and value:
                    source = Path(value)
                    if not source.is_absolute():
                        source = root / source
                    dest = staging / (key + '.txt')
                    shutil.copyfile(source, dest)
                    values[key] = str(dest)
            values['global-diretorio_de_saida'] = str(output)
            values['global-diretorio_de_armazenamento_de_cvs'] = str(cvs)
            config = staging / 'generation.config'
            config.write_text(''.join(f'{k} = {v}\n' for k, v in values.items()), encoding='utf-8')
            generate(root, config, log, args.build_timeout)
            validate_output(output, ids)
            metadata = {'schema': SCHEMA, 'hash_schema': HASH_SCHEMA,
                        'fingerprint': wanted, 'curricula': records,
                        'created_at': now, 'offline': args.offline}
            atomic_json(staging / 'state.json', metadata)
            releases = state / 'releases'
            releases.mkdir(exist_ok=True)
            release = releases / run_id
            os.rename(staging, release)
            # Persist config with final paths, not temporary ones.
            config = release / 'generation.config'
            config.write_text(config.read_text().replace(str(staging), str(release)), encoding='utf-8')
            next_link = state / ('current-' + uuid.uuid4().hex)
            next_link.symlink_to(Path('releases') / run_id, target_is_directory=True)
            os.replace(next_link, current)
            result.update(outcome='generated', release=str(release))
            atomic_json(state / 'last-check.json', result)
            return result


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True)
    p.add_argument('--state-dir', required=True)
    p.add_argument('--project-root', default=str(ROOT))
    p.add_argument('--seed-cache')
    p.add_argument('--check-only', action='store_true')
    p.add_argument('--offline', action='store_true', help='Não consulta Lattes; apenas cache explicitamente disponível')
    p.add_argument('--force', action='store_true')
    p.add_argument('--fetch-timeout', type=int, default=180)
    p.add_argument('--build-timeout', type=int, default=1800)
    return p


def main():
    args = parser().parse_args()
    try:
        if args.fetch_timeout <= 0 or args.build_timeout <= 0:
            raise ValueError('Timeouts devem ser positivos')
        print(json.dumps(refresh(args), ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({'outcome': 'failed', 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
