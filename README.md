# scriptLattes

O CNPq realiza um enérgico trabalho na integração de bases de currículos acadêmicos de instituições públicas e privadas em uma única plataforma denominada Lattes. Os chamados ``Currículos Lattes'' são considerados um padrão nacional de avaliação representando um histórico das atividades científicas / acadêmicas / profissionais de pesquisadores cadastrados. Os currículos Lattes foram projetados para mostrar informação pública, embora, individual de cada usuário cadastrado na plataforma. Muitas vezes, realizar uma compilação ou sumarização de produções bibliográficas para um grupo de usuários cadastrados de médio ou grande porte (e.g. grupo de professores, departamento de pós-graduação) realmente requer um grande esforço mecânico que muitas vezes é suscetível a falhas.

O scriptLattes é um script GNU-GPL desenvolvido para a extração e compilação automática de: (1) produções bibliográficas, (2) produções técnicas, (3) produções artísticas, (4) orientações, (5) projetos de pesquisa, (6) projetos de extensão, **(7) projetos de desenvolvimento**, (8) áreas de atuação com especialidades, (9) prêmios e títulos, e (10) grafo de colaborações de um conjunto de pesquisadores cadastrados na plataforma Lattes. Associações de Qualis para as produções acadêmicas publicadas em Congressos e Revistas também são considerados.

O scriptLattes baixa automaticamente os currículos Lattes em formato HTML (livremente disponíveis na rede) de um grupo de pessoas de interesse, compila as listas de produções, tratando apropriadamente as produções duplicadas e similares. São geradas páginas HTML com listas de produções e orientações separadas por tipo e colocadas em ordem cronológica invertida. **Além dos relatórios HTML tradicionais, o sistema agora gera automaticamente arquivos JSON individuais para cada pesquisador, facilitando a análise de dados e integração com outras ferramentas.** Adicionalmente são criadas automaticamente vários grafos (redes) de co-autoria entre os membros do grupo de interesse e um mapa de geolocalização dos membros e alunos (de pós-doutorado, doutorado e mestrado) com orientação concluída. Os relatórios gerados permitem avaliar, analisar ou documentar a produção de grupos de pesquisa. Este projeto de software livre foi idealizado por Jesús P. Mena-Chalco e Roberto M. Cesar-Jr em 2005 (IME/USP).

O scriptLattes atualmente permite filtrar as produções científicas usando termos de pesquisa (Veja os exemplo teste-03).

## Automação incremental de relatórios

A rotina opcional em `scripts/inct_update.py` consulta currículos, detecta mudanças
e gera versões validadas sem sobrescrever a última geração válida. A publicação por
SSH é separada e usa **staging por padrão**; instalar o código não ativa publicação
nem agendamento automaticamente.

A automação usa Linux e Python 3.11+ (Python 3.13 no container). O receptor remoto
requer apenas a biblioteca padrão do Python 3.10+. Exemplos sem dados pessoais estão
em `deploy/inct/inct.config.example` e `deploy/inct/inct.list.example`.

Veja o [runbook de instalação, testes e recuperação](docs/runbooks/inct-update.md)
e a [documentação](docs/README.md). A execução tradicional continua disponível.

## ✨ Principais Funcionalidades Implementadas

### 🔄 Extração Aprimorada de Projetos
- **Projetos de Pesquisa**: Extração completa com padrão `salvarParte3`
- **Projetos de Extensão**: Suporte completo para múltiplos projetos
- **Projetos de Desenvolvimento**: **Nova funcionalidade** - extração completa de projetos de desenvolvimento/tecnológicos
- **Correção de Bugs**: Resolvido problema de contaminação de dados entre membros

### 🎯 Áreas de Atuação Melhoradas
- **Múltiplas Áreas**: Extração correta de todas as áreas de atuação de cada pesquisador
- **Estrutura Completa**: Grande área, área, subárea e **especialidade** quando disponível
- **Parsing Inteligente**: Regex otimizado para capturar especialidades com espaços e caracteres especiais

### 📄 Exportação JSON Abrangente
- **Arquivos Individuais**: JSON separado para cada pesquisador
- **Estrutura Completa**: Todos os tipos de dados disponibilizados
- **Estatísticas Atualizadas**: Contadores automáticos para todos os tipos de produção

### 🔧 Melhorias Técnicas
- **Parser Robusto**: Correções na lógica de parsing HTML
- **Estado Isolado**: Cada membro processado independentemente
- **Flags Corrigidas**: Reset apropriado de flags de seção
- **Tratamento de Idiomas**: Suporte para múltiplos idiomas por pesquisador

## Pré-requisitos
- **Python 3**: Certifique-se de ter o Python 3 instalado no seu computador. 
  Se não tiver, você pode baixá-lo em [python.org](https://www.python.org/downloads/).
- **Google Chrome ou Chromium**: Necessário para o funcionamento do ChromeDriver.
- **jq**: Utilitário para processamento JSON (necessário para o Makefile):
  - Ubuntu/Debian: `sudo apt-get install jq`
  - CentOS/RHEL/Fedora: `sudo yum install jq` ou `sudo dnf install jq`
  - macOS: `brew install jq`
- **wget**: Para download do ChromeDriver (geralmente já instalado)

## Instalação Rápida (Recomendada)

Para uma instalação completa automatizada, use o Makefile incluído:

```bash
# Clone o repositório
git clone https://github.com/jpmenachalco/scriptLattes.git
cd scriptLattes

# Instalação completa (ambiente virtual + dependências + ChromeDriver)
make install
```

Este comando irá:
1. Criar um ambiente virtual Python
2. Instalar todas as dependências
3. Detectar automaticamente a versão do seu Chrome/Chromium
4. Baixar e configurar a versão correta do ChromeDriver

### Outros comandos úteis do Makefile:

```bash
make help                    # Mostra todos os comandos disponíveis
make status                  # Verifica o status da instalação
make test                    # Executa o exemplo de teste
make clean                   # Limpa arquivos temporários e cache
make update-chromedriver     # Atualiza o ChromeDriver
```

## Instalação Manual (Alternativa)

### 1. Clone este repositório para o seu computador
```bash
git clone https://github.com/jpmenachalco/scriptLattes.git
```

### 2. Navegue até o diretório do projeto
```bash
cd scriptLattes
```

### 3. Crie um ambiente virtual
```bash
python -m venv venv
```

#### Ative o ambiente virtual no Windows
```cmd
venv\Scripts\activate
```

#### Ative o ambiente virtual no Linux/Mac
```bash
source venv/bin/activate
```

### 4. Instale as dependências
```bash
pip install -r requirements.txt
```

### 5. Configure o ChromeDriver manualmente
Baixe o ChromeDriver correspondente à versão do seu navegador em [Chrome for Testing](https://googlechromelabs.github.io/chrome-for-testing/). É importante que as versões sejam compatíveis.

## Execução do Programa

### Com Makefile (ambiente virtual gerenciado automaticamente):
```bash
make test
```

### Manual (certifique-se de que o ambiente virtual está ativado):
```bash
source venv/bin/activate  # Linux/Mac
python3 scriptLattes.py exemplo/teste-01.config
```

## Estrutura de Saída

O scriptLattes gera vários tipos de saída para análise dos dados extraídos:

### Relatórios HTML
- Páginas HTML interativas com tabelas organizadas por tipo de produção
- Gráficos de colaboração e visualizações em rede
- Mapas de geolocalização dos pesquisadores e orientandos

### **Novidade: Exportação JSON Individual Completa**
A partir da versão atual, o scriptLattes gera automaticamente **arquivos JSON individuais para cada pesquisador** na pasta `json/` do diretório de saída.

**Estrutura Completa do JSON por pesquisador:**
- `informacoes_pessoais`: Dados básicos do pesquisador (Nome, ID Lattes, endereço profissional, etc.)
- `formacao_academica`: Histórico completo de formação acadêmica
- `projetos_pesquisa`: Lista completa de projetos de pesquisa com detalhes
- `projetos_extensao`: **Projetos de extensão universitária** - completo com descrições
- `projetos_desenvolvimento`: **🆕 NOVO - Projetos de desenvolvimento e tecnológicos** - totalmente implementado
- `areas_de_atuacao`: **Melhorado** - Múltiplas áreas com grande área, área, subárea e **especialidade** quando disponível
- `producao_bibliografica`: Artigos, livros, capítulos, trabalhos em congressos
- `producao_tecnica`: Softwares, produtos tecnológicos, trabalhos técnicos
- `patentes_registros`: Patentes, programas de computador, desenhos industriais
- `producao_artistica`: Produções artísticas e culturais
- `orientacoes`: Orientações em andamento e concluídas (todas as modalidades)
- `eventos`: Participações e organizações de eventos
- `premios_titulos`: Prêmios e títulos recebidos
- `idiomas`: **Melhorado** - Múltiplos idiomas com proficiências detalhadas
- `estatisticas`: **Atualizado** - Resumo quantitativo incluindo projetos de desenvolvimento

**Exemplos práticos de uso dos dados JSON:**

```bash
# Listar todos os projetos de desenvolvimento (nova funcionalidade)
jq '.projetos_desenvolvimento[].nome' json/00_Paulo-Sergio-*.json

# Verificar todas as áreas de atuação com especialidades
jq '.areas_de_atuacao[] | {area: .area, subarea: .subarea, especialidade: .especialidade}' json/*.json

# Obter estatísticas completas incluindo projetos de desenvolvimento
jq '.estatisticas' json/00_Paulo-Sergio-*.json

# Extrair projetos de extensão
jq '.projetos_extensao[].nome' json/*.json

# Verificar todos os idiomas conhecidos pelos pesquisadores
jq '.idiomas[] | {nome: .nome, proficiencia_completa: .proficiencia_completa}' json/*.json

# Comparar tipos de projetos por pesquisador
jq '{nome: .informacoes_pessoais.nome_completo, projetos_pesquisa: (.estatisticas.total_projetos_pesquisa), projetos_extensao: (.estatisticas.total_projetos_extensao), projetos_desenvolvimento: (.estatisticas.total_projetos_desenvolvimento)}' json/*.json
```

**Melhorias na Estrutura de Dados:**

1. **Áreas de Atuação Aprimoradas:**
   ```json
   {
     "grande_area": "Ciências Exatas e da Terra",
     "area": "Ciência da Computação", 
     "subarea": "Metodologia e Técnicas da Computação",
     "especialidade": "Engenharia de Software",
     "descricao_completa": "Grande área: Ciências Exatas... / Especialidade: Engenharia de Software."
   }
   ```

2. **Projetos de Desenvolvimento (NOVO):**
   ```json
   {
     "nome": "ES Na Palma da Mão: Uma Plataforma baseado em serviços...",
     "ano_inicio": "2019",
     "ano_conclusao": "2020", 
     "descricao": ["Descrição completa do projeto..."],
     "tipo": "Projeto de desenvolvimento"
   }
   ```

3. **Estatísticas Expandidas:**
   ```json
   {
     "total_projetos_pesquisa": 9,
     "total_projetos_extensao": 2,
     "total_projetos_desenvolvimento": 7,
     "total_artigos_periodicos": 5
   }
   ```

### Arquivos de Dados Estruturados
- **CSV/Excel**: Tabelas exportáveis para análise em planilhas
- **GDF**: Formato para análise de redes em ferramentas como Gephi
- **TXT**: Listas simples de produções

## 🔧 Melhorias Técnicas Implementadas

### Correções Críticas de Parser
1. **Bug de Contaminação de Estado**: Corrigido problema onde dados de um pesquisador eram misturados com outros
2. **Flags de Seção**: Reset adequado de flags (`achouAreaDeAtuacao`, `achouIdioma`, etc.) para permitir múltiplos itens
3. **Padrão salvarParte3**: Projetos de desenvolvimento agora seguem o padrão correto usado por outros tipos de projetos
4. **Condições de Processamento**: Adicionada flag `achouProjetoDeDesenvolvimento` nas condições principais do parser

### Melhorias no Processamento de Dados
1. **Regex Aprimorado**: Especialidades agora capturadas corretamente com textos contendo espaços
2. **Múltiplas Seções**: Suporte completo para múltiplas áreas de atuação e múltiplos idiomas
3. **Parsing Robusto**: Melhor tratamento de caracteres especiais e formatação inconsistente
4. **Estado Isolado**: Cada membro processado independentemente sem vazamento de dados

### Validações e Testes
- ✅ Paulo: 9 projetos pesquisa + 2 projetos extensão + **7 projetos desenvolvimento** + 6 áreas atuação  
- ✅ Daniel: 5 projetos pesquisa + 0 projetos extensão + **5 projetos desenvolvimento** + 4 áreas atuação
- ✅ Especialidades extraídas: "Engenharia de Software", "Processamento de Sinais Biológicos", etc.
- ✅ Múltiplos idiomas por pesquisador funcionando corretamente

## Solução de Problemas Comuns

### Erro de incompatibilidade do ChromeDriver
Se você receber um erro como "This version of ChromeDriver only supports Chrome version X", execute:
```bash
make update-chromedriver
```

### Verificar status da instalação
```bash
make status
```

### Problemas com Extração de Dados Específicos

#### Projetos de desenvolvimento não aparecem
Se você não estiver vendo projetos de desenvolvimento no JSON, verifique:
1. Se o pesquisador realmente possui projetos na seção "Projetos de desenvolvimento" do Lattes
2. Execute novamente o script com `--somente-json` para debugging:
```bash
python scriptLattes.py exemplo/teste-01.config --somente-json
```

#### Áreas de atuação incompletas
Se especialidades não estão sendo extraídas:
1. Verifique se as áreas no Lattes seguem o formato: "Grande área: ... / Especialidade: ..."
2. O sistema agora suporta múltiplas áreas por pesquisador automaticamente

#### Dados misturados entre pesquisadores
Este problema foi corrigido na versão atual. Se ainda ocorrer:
1. Limpe o cache: `make clean`
2. Execute novamente: `make test`

### Verificar dados extraídos
```bash
# Verificar estrutura completa de um pesquisador
jq keys json/00_Paulo-Sergio-*.json

# Verificar se projetos de desenvolvimento foram extraídos
jq '.estatisticas.total_projetos_desenvolvimento' json/*.json

# Verificar quantas áreas de atuação foram encontradas
jq '.areas_de_atuacao | length' json/*.json

# Listar todos os tipos de projetos
jq '{pesquisa: (.estatisticas.total_projetos_pesquisa), extensao: (.estatisticas.total_projetos_extensao), desenvolvimento: (.estatisticas.total_projetos_desenvolvimento)}' json/*.json
```

### Chrome/Chromium não encontrado
Certifique-se de ter o Google Chrome ou Chromium instalado:
- Ubuntu/Debian: `sudo apt-get install google-chrome-stable` ou `sudo apt-get install chromium-browser`
- CentOS/RHEL/Fedora: Baixe do site oficial do Google Chrome
- macOS: Baixe do site oficial do Google Chrome

### Problemas com dependências
Se houver problemas com as dependências Python:
```bash
make clean-all  # Remove tudo
make install    # Reinstala do zero
```

## Comunicação
- Temos uma área no Discord que pode ser útil para compartilhar dúvidas/sugestões [https://discord.gg/Xz8NZ3kBc3]
- Contato direto: [jesus.mena@ufabc.edu.br]

## Como referenciar este software
- J. P. Mena-Chalco e R. M. Cesar-Jr. scriptLattes: An open-source knowledge extraction system from the Lattes platform. Journal of the Brazilian Computer Society, vol. 15, n. 4, páginas 31--39, 2009. [http://dx.doi.org/10.1007/BF03194511]
- J. P. Mena-Chalco e R. M. Cesar-Jr. Prospecção de dados acadêmicos de currículos Lattes através de scriptLattes. Capítulo do livro Bibliometria e Cientometria: reflexões teóricas e interfaces São Carlos: Pedro & João, páginas 109-128, 2013. [http://dx.doi.org/10.13140/RG.2.1.5183.8561]

## Notas:
- O scriptLattes não está vinculado ao CNPq. A ferramenta é o resultado de um esforço (independente) realizado com o único intuito de auxiliar as tarefas mecânicas de compilação de informações cadastradas nos Currículos Lattes (publicamente disponíveis). Portanto, o CNPq não é responsável por nenhuma assessoria técnica sobre esta ferramenta.
- O repositorio antigo, no sourceforge não está sendo atualizado.

## 📋 Changelog - Principais Melhorias

### ✨ Nova Funcionalidade - Projetos de Desenvolvimento
- **Implementado**: Extração completa de projetos de desenvolvimento/tecnológicos
- **Estrutura**: Mesma estrutura dos projetos de pesquisa e extensão
- **JSON**: Campo `projetos_desenvolvimento` adicionado ao JSON
- **Estatísticas**: Contador `total_projetos_desenvolvimento` nas estatísticas

### 🔧 Correções Críticas de Parser
- **Bug Contaminação**: Corrigido vazamento de dados entre pesquisadores diferentes
- **Estado Isolado**: Cada membro agora é processado independentemente
- **Flags Reset**: Correção do reset de flags para permitir múltiplos itens por seção

### 🎯 Áreas de Atuação Melhoradas
- **Múltiplas Áreas**: Suporte para todos as áreas de atuação de um pesquisador
- **Especialidades**: Extração correta de especialidades com regex otimizado
- **Parsing Robusto**: Melhor tratamento de textos com espaços e caracteres especiais
- **Estrutura Completa**: Grande área, área, subárea e especialidade quando disponível

### 🌐 Idiomas Aprimorados
- **Múltiplos Idiomas**: Correção para extrair todos os idiomas de um pesquisador
- **Proficiências**: Extração detalhada das habilidades em cada idioma
- **Reset de Flags**: Corrigido problema que impedia múltiplos idiomas

### 📊 Melhorias na Exportação JSON
- **Campos Padronizados**: Nomenclatura consistente (`areas_de_atuacao` vs `areas_atuacao`)
- **Dados Completos**: Todos os tipos de dados agora incluídos no JSON
- **Estatísticas Expandidas**: Contadores para todos os tipos de produção e projetos

### 🛠️ Melhorias Técnicas
- **Padrão salvarParte3**: Projetos de desenvolvimento agora seguem padrão correto
- **Condições de Processamento**: Flags adicionadas nas condições principais
- **Tratamento de Certificação**: Suporte para "Projeto certificado" em desenvolvimento
- **Parsing HTML**: Melhor tratamento da estrutura HTML do Lattes

### 📈 Resultados Validados
- **Paulo**: 9 pesquisa + 2 extensão + 7 desenvolvimento + 6 áreas
- **Daniel**: 5 pesquisa + 0 extensão + 5 desenvolvimento + 4 áreas  
- **Especialidades**: Corretamente extraídas (ex: "Engenharia de Software")
- **Múltiplos Itens**: Idiomas e áreas de atuação funcionando corretamente

### 🔍 Para Desenvolvedores
As principais melhorias no código incluem:
- `parserLattes.py`: Correção de flags e condições de processamento
- `projetoDeDesenvolvimento.py`: Nova classe seguindo padrão existente
- `membro.py`: Adição de lista de projetos de desenvolvimento
- `grupo.py`: Melhorias no parsing de áreas de atuação e export JSON
- Correção em múltiplos pontos para evitar contaminação de estado entre membros

## 📚 Documentação Adicional

Para histórico completo de mudanças, versões e detalhes técnicos, consulte:
- **[CHANGELOG.md](CHANGELOG.md)** - Histórico detalhado de mudanças e correções
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Guia completo para contribuições e desenvolvimento
- **[exemplo/](exemplo/)** - Arquivos de configuração e exemplos de uso
- **[README.md](README.md)** - Documentação principal (este arquivo)

### Como Contribuir
Se você encontrar problemas ou quiser melhorar o sistema, consulte nosso [Guia de Contribuição](CONTRIBUTING.md) para:
1. **Processo completo** de reportar bugs e sugerir melhorias
2. **Templates padronizados** para issues e pull requests  
3. **Diretrizes de código** e melhores práticas
4. **Processo de testing** e validação
5. **Workflow de desenvolvimento** e deployment

**Quick Start para Contribuições:**
```bash
# Verificação rápida
python scriptLattes.py exemplo/teste-01.config
jq keys json/*.json  # Verificar estrutura JSON

# Teste de regressão  
make clean && make test  # Limpar cache e testar
```


