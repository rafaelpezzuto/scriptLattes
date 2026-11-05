# Estado do projeto — automação INCT

## Onde estamos
- Branch de implementação: `feat/inct-atualizacao-incremental`.
- Base: `main` sincronizada com upstream; correção anterior de prêmios já integrada.
- Updater transacional, publicador, receptor SSH restrito e migração inicial implementados.
- Implantação existente foi validada com 55 currículos e 159 arquivos publicados.
- Intervalo usado na validação: 2025–2026. O código permite configurar outro intervalo.
- Agendamento semanal validado; o serviço oneshot termina e fica inativo entre execuções.

## Validação da revisão
- 47 testes passaram no container, sem rede e com filesystem read-only.
- Ruff, ShellCheck e sintaxe shell passaram; nove SyntaxWarnings de regex do legado
  continuam como avisos não bloqueantes, fora do escopo desta mudança.
- Imagem de produção confirmada sem root, pytest, Ruff, testes ou dados privados.
- CI executa a mesma imagem de testes em pull requests e na main.
- Corrigidas a promoção de baseline offline após consulta online completa e a limpeza
  dos grupos de processos quando o operador cancela uma execução.
- Dados originais e relatórios locais conferidos por hash, sem alterações.

## Entrega para revisão
- PR aberto no fork pessoal: [#1 — atualização incremental e publicação segura](https://github.com/rafaelpezzuto/scriptLattes/pull/1).
- Base: `rafaelpezzuto/scriptLattes:main`; head: `feat/inct-atualizacao-incremental`.
- Commit funcional: `520144a`; a sincronização da base foi fast-forward, sem force.
- CI remoto acompanha o PR; consultar os checks atuais antes de merge.
- Nenhum PR foi aberto no upstream e nenhum merge foi executado.
- Alterações desta revisão não foram implantadas: a instância existente continua usando
  sua imagem imutável anteriormente validada, sem redeploy automático.

## Próximo passo
1. Revisar o PR e os checks remotos antes de decidir pelo merge.
2. Fazer um novo build/validação antes de qualquer atualização futura da implantação.

## Armadilhas conhecidas
- Não incluir binário ChromeDriver, currículos HTML, listas reais, configuração pessoal,
  relatórios, credenciais ou inventário dos servidores em commits/imagens/PRs.
- Notas locais de implantação e baseline dos arquivos originais ficam em `.local/`, ignorado
  pelo Git. Não dependem do conteúdo versionado para serem preservados.
- O hash ignora o carimbo de geração do HTML Lattes, mas mantém a data real de atualização.
- Contadores externos de citações podem variar mesmo sem mudança dos JSONs; a normalização
  não é um diff completo do parser e pode provocar regeneração equivalente.
- A coleta atual baixa o HTML para detectar mudanças; não há consulta condicional leve validada.
- Uma falha de coleta aborta o lote sem promover o cache/geração; staging não é retomável.
- Em NFS, a migração inicial entre diretório e link pode exigir duas renomeações com janela
  aprovada e rollback. Publicações seguintes trocam somente o link.
- `last-check.json` pode representar amostra ou check-only: conferir `members`, `offline`
  e `outcome`, além do journal e do receipt de publicação.
- Notificação externa e limpeza automática de releases não estão configuradas.

## Referências
- [Runbook](../runbooks/inct-update.md)
- [Implementação e validação concluídas](../archive/inct-automation.md)
- [ADR](../decisions/0001-inct-incremental-publication.md)
