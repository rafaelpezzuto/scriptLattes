# Automação INCT — implementação e validação

## Escopo entregue
- Consulta sequencial com timeout, validação de identidade e comparação de conteúdo.
- Cache, entradas, metadados e saída isolados em releases; promoção somente após validação.
- Reprocessamento do grupo completo se currículo, lista/configuração ou código mudar.
- Modo offline explícito e check-only sem consumo das alterações detectadas.
- Transferência verificada por manifesto SHA-256; staging separado de ativação.
- Receptor com comandos restritos e migração administrativa com backup e rollback.
- Container sem root, limites de recursos e timer semanal do systemd.

## Validação operacional realizada
- Processamento dos 55 currículos do cache, sem alterar os arquivos originais.
- Segunda execução offline sem mudanças: nenhuma nova geração.
- 55 JSONs gerados do cache equivalentes aos da publicação anterior.
- Coleta real dos 55 currículos; 11 JSONs atualizados em relação à base inicial.
- Repetição de consulta sem falso positivo pelo carimbo de geração do HTML.
- Transferência de 159 arquivos com integridade conferida.
- Entrega HTTP por link simbólico testada antes da migração.
- Diretório original preservado integralmente no backup da migração.
- Execução completa pelo systemd: coleta, geração, ativação e 159 hashes HTTP conferidos.
- Timer habilitado somente após o teste completo passar.

## Limites da entrega
O código não inclui credenciais, lista de pesquisadores ou inventário operacional.
Notificações externas e retenção automática permanecem melhorias opcionais.
A revisão de higiene posterior não altera a implantação existente automaticamente.
