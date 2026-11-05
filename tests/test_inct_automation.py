"""Offline regression tests. No credentials, network or real user artifacts."""
import argparse
import io
import json
from pathlib import Path
import sys
import tarfile

import pytest

import inct_update as update
import inct_receive as receive
import inct_publish as publish
import inct_migrate as migration

ID = '1234567890123456'
OTHER = '9999999999999999'


def cv(identifier=ID, title='Prêmio A', extra=''):
    return f'''<html><body><div class="layout-cell-pad-main">
    <h2 class="nome">Pessoa Teste</h2><ul><li>ID Lattes: {identifier}</li>
    <li>Última atualização do currículo em 01/01/2026</li></ul>
    <h1>Identificação</h1><p>{title}</p>{extra}</div><footer>Rodapé</footer></body></html>'''


def fake_output(directory, ids=(ID,)):
    directory.mkdir(parents=True)
    (directory / 'index.html').write_text('<html>Relatório</html>')
    (directory / 'json').mkdir()
    for identifier in ids:
        (directory / 'json' / (identifier + '.json')).write_text(json.dumps({
            'informacoes_pessoais': {'id_lattes': identifier, 'nome_completo': 'Pessoa Teste'}}))


@pytest.fixture
def environment(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    root.mkdir()
    (root / 'members.list').write_text(f'{ID},Pessoa Teste\n')
    config = root / 'inct.config'
    config.write_text('global-arquivo_de_entrada = members.list\nglobal-nome_do_grupo = INCT\n')
    seed = tmp_path / 'seed'
    seed.mkdir()
    (seed / ID).write_text(cv())
    args = argparse.Namespace(project_root=str(root), state_dir=str(tmp_path / 'state'),
                              config=str(config), seed_cache=str(seed), offline=True,
                              force=False, check_only=False, fetch_timeout=5, build_timeout=5)
    # Use real fingerprint while supplying minimal project source files.
    (root / 'scriptLattes.py').write_text('# test generator')
    (root / 'requirements.txt').write_text('')
    calls = []

    def generate(root, config, log, timeout):
        values, ids = update.load_config(config, root)
        calls.append(values)
        fake_output(Path(values['global-diretorio_de_saida']), ids)

    monkeypatch.setattr(update, 'generate', generate)
    monkeypatch.setattr(update, 'fetch_cv', lambda identifier, directory, *rest:
                        (directory / identifier).write_text(cv(identifier)))
    return args, calls


def test_first_generation_then_no_change(environment):
    args, calls = environment
    first = update.refresh(args)
    assert first['outcome'] == 'generated'
    current = Path(args.state_dir) / 'current'
    assert current.is_symlink()
    assert (current / 'cache' / ID).read_text() == cv()
    assert update.refresh(args)['outcome'] == 'unchanged'
    assert len(calls) == 1
    # Updating config or generator code rebuilds even if CV did not change.
    with open(args.config, 'a') as f:
        f.write('global-itens_ate_o_ano = 2026\n')
    assert update.refresh(args)['outcome'] == 'generated'
    (Path(args.project_root) / 'scriptLattes.py').write_text('# changed')
    assert update.refresh(args)['outcome'] == 'generated'
    assert len(calls) == 3


def test_online_validation_promotes_offline_baseline_even_without_cv_changes(environment):
    args, calls = environment
    first = update.refresh(args)
    assert json.loads((Path(first['release']) / 'state.json').read_text())['offline']
    args.offline = False
    result = update.refresh(args)
    assert result['outcome'] == 'generated'
    assert result['changed_ids'] == []
    assert not json.loads((Path(result['release']) / 'state.json').read_text())['offline']
    assert update.refresh(args)['outcome'] == 'unchanged'
    assert len(calls) == 2


def test_changed_cv_and_check_only_does_not_consume_change(environment, monkeypatch):
    args, calls = environment
    old = update.refresh(args)['release']
    args.offline = False
    args.check_only = True
    monkeypatch.setattr(update, 'fetch_cv', lambda identifier, directory, *rest:
                        (directory / identifier).write_text(cv(title='Prêmio B')))
    result = update.refresh(args)
    assert result['needs_build']
    assert result['changed_ids'] == [ID]
    assert str((Path(args.state_dir) / 'current').resolve()) == old
    args.check_only = False
    assert update.refresh(args)['outcome'] == 'generated'
    assert len(calls) == 2
    assert (Path(old) / 'cache' / ID).read_text() == cv()


@pytest.mark.parametrize('failure', ['fetch', 'identity', 'build', 'incomplete'])
def test_failure_preserves_current_and_seed(environment, monkeypatch, failure):
    args, calls = environment
    old = update.refresh(args)['release']
    args.offline = False
    args.force = True

    def fail(*args):
        raise RuntimeError('simulated failure')

    if failure == 'fetch':
        monkeypatch.setattr(update, 'fetch_cv', fail)
    elif failure == 'identity':
        monkeypatch.setattr(update, 'fetch_cv', lambda identifier, directory, *rest:
                            (directory / identifier).write_text(cv(OTHER)))
    elif failure == 'build':
        monkeypatch.setattr(update, 'generate', fail)
    else:
        monkeypatch.setattr(update, 'generate', lambda *args: None)
    with pytest.raises((RuntimeError, ValueError)):
        update.refresh(args)
    assert str((Path(args.state_dir) / 'current').resolve()) == old
    assert (Path(args.seed_cache) / ID).read_text() == cv()


def test_list_changes_and_duplicates(environment):
    args, calls = environment
    update.refresh(args)
    with (Path(args.project_root) / 'members.list').open('a') as f:
        f.write(f'{OTHER},Outra Pessoa\n')
    args.offline = False
    result = update.refresh(args)
    assert result['changed_ids'] == [OTHER]
    assert result['members'] == 2
    with (Path(args.project_root) / 'members.list').open('a') as f:
        f.write(f'{ID},Duplicado\n')
    with pytest.raises(ValueError, match='duplicados'):
        update.refresh(args)


def test_lock_prevents_overlap(environment):
    args, _ = environment
    with update.lock(Path(args.state_dir)):
        with pytest.raises(RuntimeError, match='execução'):
            update.refresh(args)


def test_cv_hash_ignores_presentation_but_tracks_links(tmp_path):
    p = tmp_path / ID
    p.write_text(cv())
    before = update.inspect_cv(p, ID)
    p.write_text(cv(extra='<script>nonce=123</script><style>.x{color:red}</style>').replace('Rodapé', 'Outro'))
    assert update.inspect_cv(p, ID) == before
    p.write_text(cv(extra='<a href="https://doi.org/123">DOI</a>'))
    first = update.inspect_cv(p, ID)
    p.write_text(cv(extra='<a href="https://doi.org/456">DOI</a>'))
    assert update.inspect_cv(p, ID)['hash'] != first['hash']


@pytest.mark.parametrize('html', ['<html>Captcha</html>', cv(OTHER), cv().replace('01/01/2026', '99/99/2026'),
                                  cv().replace('</body></html>', '')])
def test_invalid_curriculum(tmp_path, html):
    p = tmp_path / ID
    p.write_text(html)
    with pytest.raises(ValueError):
        update.inspect_cv(p, ID)


def test_generation_timestamp_and_markup_spacing_are_not_content_changes(tmp_path):
    p = tmp_path / ID
    p.write_text(cv(title='Graduação em Design.', extra=(
        '<div>Página gerada pelo Sistema Currículo Lattes em 14/10/2026 às 15:21:56</div>')))
    before = update.inspect_cv(p, ID)
    p.write_text(cv(title='Graduação em <b>Design</b>.', extra=(
        '<div>Página gerada pelo Sistema Currículo Lattes em 05/11/2026 às 01:22:33</div>')))
    assert update.inspect_cv(p, ID) == before
    p.write_text(cv(title='Graduação em <b>Medicina</b>.', extra=(
        '<div>Página gerada pelo Sistema Currículo Lattes em 05/11/2026 às 01:22:33</div>')))
    assert update.inspect_cv(p, ID)['hash'] != before['hash']


def test_legacy_hashes_recomputed_from_preserved_cv(environment):
    args, _ = environment
    update.refresh(args)
    path = Path(args.state_dir) / 'current/state.json'
    data = json.loads(path.read_text())
    data.pop('hash_schema')
    data['curricula'][ID]['hash'] = 'old-comparison-algorithm'
    path.write_text(json.dumps(data))
    result = update.refresh(args)
    assert result['changed_ids'] == []


def test_strict_config_and_path_id(environment):
    args, _ = environment
    with open(args.config, 'a') as f:
        f.write('broken-line\n')
    with pytest.raises(ValueError, match='falta ='):
        update.refresh(args)
    (Path(args.project_root) / 'members.list').write_text('../../file,Nome')
    Path(args.config).write_text('global-arquivo_de_entrada = members.list\n')
    with pytest.raises(ValueError, match='16 dígitos'):
        update.refresh(args)


def test_generation_timeout_kills_process_group(tmp_path):
    with pytest.raises(RuntimeError, match='Tempo limite'):
        update.run_process([sys.executable, '-c', 'import time; time.sleep(30)'],
                           tmp_path, tmp_path / 'log', 1)


def test_operator_cancellation_kills_and_reaps_the_process_group(tmp_path, monkeypatch):
    events = []

    class InterruptedProcess:
        pid = 12345

        def wait(self, timeout=None):
            if timeout is not None:
                raise KeyboardInterrupt
            events.append('reaped')
            return -9

    monkeypatch.setattr(update.subprocess, 'Popen', lambda *args, **kwargs: InterruptedProcess())
    monkeypatch.setattr(update.os, 'killpg', lambda pid, sig: events.append((pid, sig)))
    with pytest.raises(KeyboardInterrupt):
        update.run_process(['test'], tmp_path, tmp_path / 'log', 1)
    assert events == [(12345, update.signal.SIGKILL), 'reaped']


def test_missing_output_is_not_reported_unchanged(environment):
    args, _ = environment
    update.refresh(args)
    (Path(args.state_dir) / 'current/output/index.html').unlink()
    with pytest.raises(ValueError, match='index.html'):
        update.refresh(args)


def test_receiver_stage_keeps_existing_site_and_refuses_activation(tmp_path):
    output = tmp_path / 'output'
    fake_output(output)
    archive = tmp_path / 'output.tar'
    token = publish.package(output, archive)
    destination = tmp_path / 'www' / 'inct'
    destination.mkdir(parents=True)
    (destination / 'original').write_text('keep')
    with archive.open('rb') as stream:
        result = receive.receive(destination, 'stage ' + token, stream)
    assert result['outcome'] == 'staged'
    with pytest.raises(ValueError, match='migração'):
        receive.receive(destination, 'activate ' + token, None)
    assert (destination / 'original').read_text() == 'keep'


def test_receiver_atomic_activation_and_idempotent_stage(tmp_path):
    output = tmp_path / 'output'
    fake_output(output)
    archive = tmp_path / 'output.tar'
    token = publish.package(output, archive)
    destination = tmp_path / 'inct'
    for _ in range(2):
        with archive.open('rb') as stream:
            assert receive.receive(destination, 'stage ' + token, stream)['outcome'] == 'staged'
    receive.receive(destination, 'activate ' + token, None)
    assert destination.is_symlink()
    old = destination.resolve()
    (output / 'index.html').write_text('New generation')
    new_token = publish.package(output, archive)
    with archive.open('rb') as stream:
        receive.receive(destination, 'stage ' + new_token, stream)
    assert destination.resolve() == old
    receive.receive(destination, 'activate ' + new_token, None)
    assert (old / 'index.html').read_text() == '<html>Relatório</html>'
    assert (destination / 'index.html').read_text() == 'New generation'


@pytest.mark.parametrize('name,kind', [('../evil', 'file'), ('/tmp/evil', 'file'),
                                       ('link', 'symlink'), ('link', 'hardlink')])
def test_archive_rejects_unsafe_members(tmp_path, name, kind):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w') as bundle:
        item = tarfile.TarInfo(name)
        if kind == 'symlink':
            item.type = tarfile.SYMTYPE
            item.linkname = '/etc/passwd'
        elif kind == 'hardlink':
            item.type = tarfile.LNKTYPE
            item.linkname = '/etc/passwd'
        bundle.addfile(item)
    buffer.seek(0)
    with pytest.raises(ValueError, match='insegura'):
        receive.unpack(buffer, tmp_path)


def test_migration_is_dry_run_then_atomically_keeps_original_as_backup(tmp_path):
    output = tmp_path / 'output'
    fake_output(output)
    archive = tmp_path / 'output.tar'
    token = publish.package(output, archive)
    destination = tmp_path / 'site'
    destination.mkdir()
    (destination / 'original').write_text('preserve exactly')
    with archive.open('rb') as stream:
        receive.receive(destination, 'stage ' + token, stream)
    assert migration.migrate(destination, token)['outcome'] == 'migration-plan'
    assert not destination.is_symlink()
    result = migration.migrate(destination, token, execute=True)
    assert result['outcome'] == 'migrated'
    assert destination.is_symlink()
    assert (Path(result['backup']) / 'original').read_text() == 'preserve exactly'
    assert (destination / 'index.html').read_text() == '<html>Relatório</html>'
    with pytest.raises(ValueError, match='diretório real'):
        migration.migrate(destination, token, execute=True)


def test_unsupported_atomic_exchange_keeps_site_and_cleans_temporary_link(tmp_path, monkeypatch):
    output = tmp_path / 'output'
    fake_output(output)
    archive = tmp_path / 'output.tar'
    token = publish.package(output, archive)
    destination = tmp_path / 'site'
    destination.mkdir()
    (destination / 'original').write_text('preserve')
    with archive.open('rb') as stream:
        receive.receive(destination, 'stage ' + token, stream)

    def fail(*args):
        raise OSError('not supported')

    monkeypatch.setattr(migration, 'exchange', fail)
    with pytest.raises(OSError, match='not supported'):
        migration.migrate(destination, token, execute=True)
    assert not destination.is_symlink()
    assert (destination / 'original').read_text() == 'preserve'
    assert not list((tmp_path / '.site-deploy/backups').iterdir())


@pytest.mark.parametrize('fail_install', [False, True])
def test_explicit_maintenance_migration_preserves_backup_or_rolls_back(tmp_path, monkeypatch, fail_install):
    output = tmp_path / 'output'
    fake_output(output)
    archive = tmp_path / 'output.tar'
    token = publish.package(output, archive)
    destination = tmp_path / 'site'
    destination.mkdir()
    (destination / 'original').write_text('original site')
    with archive.open('rb') as stream:
        receive.receive(destination, 'stage ' + token, stream)

    def forbidden_exchange(*args):
        pytest.fail('NFS maintenance migration must not attempt renameat2')

    monkeypatch.setattr(migration, 'exchange', forbidden_exchange)
    assert migration.migrate(destination, token, maintenance_window=True)['method'] == 'two-renames'
    assert destination.is_dir() and not destination.is_symlink()
    if fail_install:
        def fail(*args):
            raise OSError('simulated link installation failure')
        monkeypatch.setattr(migration.os, 'replace', fail)
        with pytest.raises(OSError, match='simulated link'):
            migration.migrate(destination, token, execute=True, maintenance_window=True)
        assert not destination.is_symlink()
        assert (destination / 'original').read_text() == 'original site'
        assert not list((tmp_path / '.site-deploy/backups').iterdir())
    else:
        result = migration.migrate(destination, token, execute=True, maintenance_window=True)
        assert destination.is_symlink()
        assert (destination / 'index.html').read_text() == '<html>Relatório</html>'
        assert (Path(result['backup']) / 'original').read_text() == 'original site'
    assert not list(tmp_path.glob('.inct-migration-*'))


def test_receiver_refuses_arbitrary_commands(tmp_path):
    with pytest.raises(ValueError, match='não autorizado'):
        receive.receive(tmp_path / 'site', 'sh -c id', None)


def test_archive_tampering_detected(tmp_path):
    output = tmp_path / 'output'
    fake_output(output)
    archive = tmp_path / 'a.tar'
    token = publish.package(output, archive)
    extracted = tmp_path / 'extracted'
    extracted.mkdir()
    with archive.open('rb') as stream:
        receive.unpack(stream, extracted)
    (extracted / 'index.html').write_text('tampered')
    with pytest.raises(ValueError, match='hash'):
        receive.verify(extracted, token)


def test_publisher_defaults_stage_only_and_blocks_offline_activation(environment, monkeypatch):
    args, _ = environment
    update.refresh(args)
    commands = []

    def ssh(args, command, archive=None):
        commands.append(command)
        op, token = command.split()
        return {'outcome': {'stage': 'staged', 'activate': 'activated'}[op], 'release': token}

    monkeypatch.setattr(publish, 'ssh', ssh)
    publication = argparse.Namespace(state_dir=args.state_dir, host='vision', ssh_config=None,
                                     activate=False, allow_offline=False, timeout=5)
    assert publish.publish(publication)['outcome'] == 'staged'
    assert len(commands) == 1
    publication.activate = True
    with pytest.raises(ValueError, match='offline'):
        publish.publish(publication)
    publication.allow_offline = True
    assert publish.publish(publication)['outcome'] == 'activated'


def test_external_current_link_is_rejected(environment, tmp_path):
    args, _ = environment
    state = Path(args.state_dir)
    state.mkdir()
    external = tmp_path / 'external'
    external.mkdir()
    (state / 'current').symlink_to(external)
    with pytest.raises(ValueError, match='fora das releases'):
        update.refresh(args)


def test_unknown_state_schema_is_rejected(environment):
    args, _ = environment
    update.refresh(args)
    path = Path(args.state_dir) / 'current/state.json'
    data = json.loads(path.read_text())
    data['schema'] = 999
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='Versão de estado'):
        update.refresh(args)


def test_publisher_failure_does_not_record_success(environment, monkeypatch):
    args, _ = environment
    update.refresh(args)

    def fail(*args):
        raise RuntimeError('connection refused')

    monkeypatch.setattr(publish, 'ssh', fail)
    publication = argparse.Namespace(state_dir=args.state_dir, host='vision', ssh_config=None,
                                     activate=False, allow_offline=False, timeout=5)
    with pytest.raises(RuntimeError):
        publish.publish(publication)
    assert not (Path(args.state_dir) / 'last-publication.json').exists()
