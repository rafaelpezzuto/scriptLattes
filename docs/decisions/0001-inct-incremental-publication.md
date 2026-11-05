# ADR 0001 — Atualização transacional e publicação separada

- Status: aceita e implementada; publicação migrada, serviço validado e agendamento semanal ativo.
- Data: 2026-11-05.

## Contexto
O scriptLattes reutiliza currículos presentes em cache sem consultar mudanças.
Relatórios INCT já estão publicados em uma pasta do servidor institucional.
O executor próprio permite agendamento; não se depende de cron no destino.

## Decisão
Preservar o pipeline existente. Um wrapper consulta os currículos com timeout,
valida identidade e metadados, compara conteúdo normalizado e URLs relevantes.
Mudanças em currículo, configuração/lista ou fonte/assets regeneram o grupo inteiro.
A consulta atual exige baixar HTML: não existe verificação condicional leve validada.

Gerações são imutáveis (`cache`, configuração, entradas, `state.json`, `output`).
Um symlink local é trocado apenas depois da validação de todos os JSONs esperados.
Falha em qualquer membro preserva a geração anterior. `--check-only` não consome
mudanças; `--offline` não afirma ter consultado o CNPq.

A publicação é independente e repetível: tar contendo apenas arquivos regulares,
manifesto SHA-256, comando SSH forçado com chave dedicada restrita ao IP do executor.
O receptor valida nomes, tipos, limites e hashes antes de disponibilizar uma release.
`stage` não altera o destino público; `activate` exige destino já gerenciado.
A migração inicial do diretório real é uma intervenção administrativa separada.
O helper administrativo oferece troca atômica com `renameat2(RENAME_EXCHANGE)`.
No destino real (NFS), essa operação não é suportada (`EINVAL`): o teste abortou
preservando a pasta original. O fallback com duas renomeações demanda janela de
manutenção explicitamente aprovada e a flag `--allow-maintenance-window`.
Após autorização, a migração foi realizada preservando o diretório original como
backup; falha ao instalar o link tem rollback testado. Não existe fallback silencioso.

Docker isola Python/Chromium; o navegador roda sem root, sem capabilities e sem
escrita na imagem. O sandbox interno do Chrome é desativado somente por opt-in no
container, não na execução local. A imagem construída é fixada por ID no executor.

## Consequências
- Nenhuma chave pessoal copiada; chave de publicação não entra no container.
- Relatórios coletivos continuam consistentes com o processamento existente.
- Consulta falha não resulta em publicação parcial; disponibilidade anterior preservada.
- Retenção de releases/cache exige acompanhamento de disco; sem limpeza automática destrutiva.
- Coleta real dos 55 currículos e entrega HTTP por symlink já foram validadas.
  A janela de migração em NFS foi realizada e os 159 arquivos publicados conferidos.
  O teste completo pelo serviço systemd passou; o timer foi habilitado após a validação
  dos 55 membros e dos hashes HTTP de toda a publicação.
- O hash evita mudanças cosméticas comuns; não é um diff semântico completo do parser.
- Fonte e dependências do build precisam ser revisadas nas atualizações de imagem;
  tags de base/apt são resolvidas no build, não travadas por versão no Dockerfile.
