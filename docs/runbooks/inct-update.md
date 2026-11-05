# Runbook — atualização e publicação INCT

## Quando
Instalar, executar manualmente ou diagnosticar coleta/publicação da rotina semanal.
Os caminhos abaixo são o layout padrão; hosts, usuário remoto e inventário real pertencem
à configuração privada da implantação, não ao repositório.
O serviço oneshot fica `inactive` entre execuções; isso é normal se `Result=success`.
O timer deve estar `active/enabled`.

## Componentes
- `scripts/inct_update.py`: coleta sequencial limitada, comparação, geração transacional.
- `scripts/inct_publish.py`: envio por SSH; padrão **stage-only**.
- `scripts/inct_receive.py`: receptor stdlib compatível com Python 3.10+, comando forçado.
- `scripts/inct_migrate.py`: migração administrativa inicial, dry-run por padrão;
  usa troca atômica ou duas renomeações somente com `--allow-maintenance-window` explícito.
  Na segunda modalidade, falha ao instalar o link restaura o diretório original.
- `deploy/inct/`: Dockerfile, launcher, unit e timer (domingo 04:00 America/Sao_Paulo).
- `--offline`: usa cache/seed; não consulta CNPq. `--check-only`: compara sem promover.
- IDs de entrada: exatamente 16 dígitos, sem duplicatas. Caminhos da configuração são
  relativos à raiz do projeto, como no script original; produção usa caminhos absolutos.

## Validação local

```bash
docker build --target test -f deploy/inct/Dockerfile -t scriptlattes-inct:test .
docker run --rm --network none --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=128m,mode=1777 scriptlattes-inct:test
# Alternativa local: pip install -r requirements-dev.txt && python -m pytest tests -q
venv/bin/python scripts/inct_update.py --config /CAMINHO/inct.config \
  --state-dir /CAMINHO/estado-isolado --seed-cache "$PWD/cache" --offline
```

Não apontar `--state-dir` para a pasta publicada. A saída configurada no arquivo
original é sobrescrita **apenas na cópia de configuração da release**, nunca no original.
A primeira geração usa o seed explicitamente informado. Consultas seguintes usam
`current/cache` como referência, mas baixam novamente para staging nas execuções online.
Sem alteração, `last-check.json` é atualizado e `current` permanece igual.

## Preparar uma nova instalação

No executor Linux, como administrador, a partir de um checkout revisado em `/opt/scriptlattes`:

```bash
useradd --system --create-home --home-dir /var/lib/scriptlattes \
  --shell /usr/sbin/nologin scriptlattes  # somente se a conta ainda não existir
install -d -o scriptlattes -g scriptlattes -m 0750 /srv/scriptlattes /srv/scriptlattes/seed-cache
install -d -o root -g scriptlattes -m 0750 /etc/scriptlattes
install -o root -g scriptlattes -m 0640 deploy/inct/inct.config.example /etc/scriptlattes/inct.config
install -o root -g scriptlattes -m 0640 deploy/inct/inct.list.example /etc/scriptlattes/inct.list
```

Substituir os IDs fictícios e ajustar o grupo/intervalo **antes de consultar a rede**.
Se houver cache autorizado, copiá-lo para `seed-cache`, pertencente ao usuário dedicado,
sem modificar os originais.

```bash
docker build --target production -f deploy/inct/Dockerfile -t scriptlattes-inct:validated .
docker image inspect --format '{{.Id}}' scriptlattes-inct:validated
```

Criar `/etc/scriptlattes/runner.env` a partir de `runner.env.example`, com o ID imutável
obtido e `INCT_PUBLISH_MODE=none`; arquivo root-only (0600). Instalar as unidades:

```bash
install -m 0644 deploy/inct/scriptlattes-inct.service deploy/inct/scriptlattes-inct.timer /etc/systemd/system/
systemctl daemon-reload
systemd-analyze verify /etc/systemd/system/scriptlattes-inct.service /etc/systemd/system/scriptlattes-inct.timer
```

Não habilitar o timer ainda. Validar coleta e geração sem publicação primeiro.

### Preparar a publicação SSH

- Criar chave Ed25519 exclusiva para o usuário `scriptlattes`; não reutilizar/copiar chave pessoal.
- Manter a chave em `/var/lib/scriptlattes/.ssh/` com diretório 0700 e arquivos privados 0600.
- Configurar alias `inct-vision` no arquivo SSH desse diretório, com `IdentityFile`,
  `IdentitiesOnly yes`, `BatchMode yes`, `ForwardAgent no` e `StrictHostKeyChecking yes`.
- Instalar `known_hosts` após verificar a chave do host por canal autenticado/independente;
  não confiar em `ssh-keyscan` sem conferir o fingerprint.
- No destino, instalar `inct_receive.py` em diretório privado fora do webroot. Instalar
  `inct_migrate.py` junto dele apenas para o acesso administrativo habitual.
- Autorizar a chave pública com restrição `from="IP-DO-EXECUTOR",restrict` e comando forçado:
  `/usr/bin/python3 /CAMINHO-PRIVADO/inct_receive.py --destination /PASTA-PUBLICA/relatorio`.
- Não permitir shell, encaminhamento de portas ou execução do helper de migração pela chave.
- Confirmar `ssh ... inct-vision status`; um comando arbitrário deve ser recusado.

A configuração SSH e a chave permanecem fora da imagem/container de coleta.
O receptor instalado no destino e o publicador no executor usam somente stdlib;
o código-fonte desses utilitários pode estar na imagem, mas nenhuma credencial está nela.

## Executor: caminhos
- Código: `/opt/scriptlattes` (root-owned).
- Config/lista: `/etc/scriptlattes/inct.config`, `inct.list`.
- Imagem imutável e modo: `/etc/scriptlattes/runner.env` (root-only).
- Estado: `/srv/scriptlattes/current`, `releases/`, `logs/`, `last-check.json`.
- Seed inicial: `/srv/scriptlattes/seed-cache`.
- Chave dedicada: `/var/lib/scriptlattes/.ssh/inct_vision` (não copiar/exibir).
- Host key autenticada e config: mesmo diretório SSH.

## Executar manualmente (no executor, como administrador)

```bash
set -a
. /etc/scriptlattes/runner.env
set +a
bash /opt/scriptlattes/deploy/inct/run.sh --offline
# Consulta real sem gerar/publicar:
bash /opt/scriptlattes/deploy/inct/run.sh --check-only
# Consulta real e geração, sem publicação quando INCT_PUBLISH_MODE=none:
bash /opt/scriptlattes/deploy/inct/run.sh
```

O launcher tem lock global; updater/publicador compartilham um lock de estado.
`--offline` e `--check-only` nunca publicam automaticamente via launcher.
O container não recebe a chave SSH. Memória/CPU/PIDs são limitados. O launcher root
orquestra Docker; aplicação e publicador usam UID dedicado sem grupo Docker.

## Enviar sem alterar o site

```bash
runuser -u scriptlattes -- python3 /opt/scriptlattes/scripts/inct_publish.py \
  --state-dir /srv/scriptlattes --host inct-vision \
  --ssh-config /var/lib/scriptlattes/.ssh/config
```

`last-publication.json` registra confirmação do receptor. Uma falha de envio permite
repetir o publicador **sem recoletar/regerar**. O receptor valida toda nova transferência,
inclusive repetição do mesmo token. Staging fica em diretório irmão oculto do site:
`.NOME-DO-DESTINO-deploy/releases/TOKEN`. Não existe shell remoto pela chave dedicada.
Geração offline pode ser enviada para staging, mas ativá-la exige `--allow-offline`.
A primeira consulta online completa após uma geração offline cria uma release online,
mesmo se os currículos forem iguais. Isso registra a verificação e permite ativação sem
`--allow-offline`. `--force` continua disponível para reprocessamento explícito.
O hash ignora o carimbo `Página gerada pelo Sistema Currículo Lattes em ...`, que muda
em toda consulta. A data de atualização informada pelo pesquisador continua relevante.

## Ativação inicial — gate administrativo

Pré-requisitos: coleta online completa, validação dos JSONs esperados, comparação
com a publicação anterior, teste HTTP de symlink e plano de rollback.

O helper usa `renameat2(RENAME_EXCHANGE)` por padrão; se o filesystem não suportar a
operação, aborta sem alterar o diretório publicado. Em NFS, `EINVAL` já foi observado.
Não repetir a operação esperando outro resultado: **duas renomeações exigem aprovação
explícita de uma breve janela de manutenção** e a flag `--allow-maintenance-window`.

Pelo acesso administrativo habitual, fora da chave restrita de publicação:

```bash
python3 /CAMINHO-PRIVADO/inct_migrate.py --destination /PASTA-PUBLICA/relatorio \
  --release TOKEN                         # somente dry-run
# Executar apenas após a aprovação da janela:
python3 /CAMINHO-PRIVADO/inct_migrate.py --destination /PASTA-PUBLICA/relatorio \
  --release TOKEN --execute --allow-maintenance-window
```

A segunda modalidade restaura o caminho original caso a instalação do link falhe.
Guardar o receipt e o caminho do backup no inventário privado da implantação.

1. Fazer snapshot/backup da pasta publicada pelo acesso administrativo habitual.
2. Preparar um link temporário apontando à release validada.
3. Somente após aprovação da janela, renomear o diretório original para backup e instalar
   o link na localização original. Existe um pequeno intervalo na migração inicial;
   restaurar imediatamente o nome original se a segunda operação falhar. Não usar `rm -rf`.
4. Conferir URLs públicas, assets, JSONs e permissões. Manter backup e release anterior.
5. Somente após isso usar `--activate`; o receptor recusa substituir diretório real.
6. Configurar `INCT_PUBLISH_MODE=activate`, testar serviço manualmente, depois:

```bash
systemctl enable --now scriptlattes-inct.timer
systemctl list-timers scriptlattes-inct.timer
```

`none` não envia; `stage` envia sem ativar; `activate` exige a migração acima.
Condicionar a ativação do timer a uma execução bem-sucedida do serviço: consulta online →
geração → publicação → confirmação do token → validação HTTP contra a saída local.
As execuções semanais validam a geração e os hashes da transferência pelo receptor;
a verificação HTTP de todos os arquivos é uma validação adicional recomendada na ativação.

## Diagnóstico

```bash
systemctl status scriptlattes-inct.service scriptlattes-inct.timer
journalctl -u scriptlattes-inct.service --since today --no-pager
# Arquivos de diagnóstico detalhado: /srv/scriptlattes/logs/*.log
runuser -u scriptlattes -- ssh -F /var/lib/scriptlattes/.ssh/config inct-vision status
```

- Timeout de coleta padrão: 180 s por currículo; build: 1800 s; serviço: 5 h.
- `last-check.json` representa a última checagem completa (inclusive probes/check-only), não uma execução abortada.
  Consultar também `members`, `offline` e `outcome`: uma amostra não comprova consulta do grupo completo.
  Falhas aparecem no exit code, journal e log correspondente. Não usar a existência
  do arquivo como prova de que a última tentativa passou.
- HTML de erro/captcha/ID errado é recusado. Não contornar bloqueios: suspender coleta
  e obter acesso autorizado ou usar fontes/cache atualizados por meio permitido.
- Contadores externos de citações exibidos pelo Lattes podem variar entre consultas
  e mudar o hash do HTML mesmo sem alterar os JSONs extraídos. Nesse caso pode haver
  regeneração/publicação equivalente; o algoritmo não é um diff completo do parser.
- A indisponibilidade de um membro aborta o lote. Downloads temporários não são
  retomáveis nesta versão: em falha, são removidos e o lote precisa ser refeito.
- Notificações externas ainda não configuradas; monitorar status/journal antes de produção.
- Atualização anual do intervalo de relatório é decisão explícita (config inicial 2025–2026).

## Recuperação e retenção
Desativar timer antes de intervenções. Gerações anteriores não são apagadas.
Para rollback remoto, via acesso administrativo, escolher token anterior validado
no mesmo diretório de releases e trocar o symlink com `os.replace` (NFS suporta a troca
entre links, ao contrário da troca inicial entre diretório e link). Nunca apontar para
staging incompleto. Para restaurar o diretório original pré-migração, preservar/remover
somente o symlink público e renomear o backup original de volta em janela aprovada;
não apagar ou copiar por cima do backup. Consultar `migration-receipt.json` no diretório
de deploy do destino, se gerado pela implantação, ou o resultado JSON do helper,
para encontrar o backup exato.

Acompanhar disco (`du -sh /srv/scriptlattes/releases`). Definir retenção antes de
operações recorrentes prolongadas; não remover `current`, release publicada ou backup
pré-migração. Esta versão não faz garbage collection automática.

## Não fazer
- Não habilitar timer ou ativação antes de validar coleta real e publicação HTTP.
- Não executar navegador como root nem adicionar o usuário dedicado ao grupo Docker.
- Não copiar chave pessoal nem usar `StrictHostKeyChecking=no`.
- Não usar `rsync --delete` no diretório público, apagar cache ou substituir o site em falha.
- Não confundir geração offline com atualização dos dados no CNPq.
- Não enviar arquivos privados, configuração, cache HTML ou chaves dentro do pacote público:
  só `current/output` é transferido.
