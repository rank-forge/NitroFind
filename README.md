# NitroFind

NitroFind e uma ferramenta local de busca automotiva. Ela coleta artigos sobre carros, indexa o conteudo em um Elasticsearch local e entrega uma interface web em `http://127.0.0.1:5000` para pesquisa de texto completo, filtros e leitura dos artigos.

O objetivo do projeto e simples: acesso rapido, offline no momento da busca, sem anuncios e sem ruido de SEO, a uma base local de especificacoes, historia e artigos automotivos.

## Estado do projeto

- Versao funcional atual: v1.1 Web Interface.
- Marco em andamento: v1.2 Search Quality & UX Polish.
- Forma suportada de execucao: `python3 main.py`.
- Interface atual: Flask + HTML/CSS/JavaScript vanilla no navegador.
- Busca: Elasticsearch 8.x local, usando `function_score`.
- Coleta de dados: Wikipedia via MediaWiki API e blogs automotivos via `requests` + BeautifulSoup.
- Escopo: carros. Motocicletas, caminhoes e veiculos nao automotivos estao fora do escopo.

## Principais recursos

- Busca local em texto completo sobre o indice `car_articles`.
- Inicializacao conjunta do Flask e do Elasticsearch por `main.py`.
- Servidor preso a `127.0.0.1`, sem exposicao externa por padrao.
- Tela de carregamento enquanto o Elasticsearch aquece.
- Busca com debounce de 300 ms.
- Resultados com titulo, dominio de origem, trecho destacado e tempo de consulta.
- Visualizacao do artigo completo dentro da propria aplicacao.
- Filtros atuais por `manufacturer`, `era_bucket` e `body_style` na API.
- Scraper com retomada por SQLite para evitar reprocessar paginas ja visitadas.
- Deduplicacao por `_id` deterministico no Elasticsearch.
- Limite de seguranca do scraper perto de 1,8 GB para manter a base abaixo de 2 GB.
- Relevancia deterministica, sem IA, embeddings ou chamadas externas no momento da busca.

## Stack

| Camada | Tecnologia |
| --- | --- |
| Linguagem | Python 3.11+ |
| Servidor local | Flask |
| Busca | Elasticsearch 8.x |
| Cliente ES | `elasticsearch==8.*` |
| Scraper Wikipedia | `mediawikiapi`, `requests` |
| Scraper blogs | `requests`, BeautifulSoup4, lxml |
| Estado do scraper | SQLite |
| Frontend | HTML, CSS e JavaScript vanilla |
| Testes | pytest |

Observacao: o `requirements.txt` atual foi gerado com `pip-compile --generate-hashes` e Python 3.12, mas o alvo do projeto permanece Python 3.11+.

## Requisitos

- Linux ou WSL. O ciclo principal de execucao atual valida o binario POSIX `bin/elasticsearch`.
- Python 3.11 ou superior.
- Elasticsearch 8.x extraido em disco. Os exemplos usam `elasticsearch-8.18.0` porque algumas mensagens internas ainda citam 8.18, mas o cliente Python travado no lockfile pertence a familia 8.x.
- Java compativel com a distribuicao do Elasticsearch usada. A distribuicao oficial do Elasticsearch 8 normalmente ja vem com JDK embutido.
- Acesso a internet apenas para instalar dependencias e para rodar o scraper. A busca depois de indexada e local.

Os comandos abaixo usam `python3`, que e o nome mais comum do binario em Linux/WSL. Se o seu ambiente virtual expuser apenas `python`, use `python` no lugar.

## Instalacao

Crie e ative um ambiente virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Instale as dependencias travadas:

```bash
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

Se voce alterar dependencias, edite `requirements.in` e regenere o lockfile com hashes:

```bash
python3 -m pip install pip-tools
pip-compile --generate-hashes requirements.in
```

## Configuracao do Elasticsearch

Baixe e extraia uma distribuicao Elasticsearch 8.x. Depois aponte `ES_HOME` para o diretorio extraido:

```bash
export ES_HOME=/caminho/para/elasticsearch-8.18.0
```

Instale a configuracao local do NitroFind no Elasticsearch:

```bash
python3 scripts/setup_es.py
```

Esse script copia:

- `config/elasticsearch.yml` para `$ES_HOME/config/elasticsearch.yml`
- `config/jvm.options` para `$ES_HOME/config/jvm.options.d/nitrofind.options`

A configuracao aplicada usa:

- `network.host: 127.0.0.1`
- `http.port: 9200`
- `discovery.type: single-node`
- seguranca/TLS desabilitados para uso local
- heap JVM fixo em 512 MB
- watermarks de disco em valores absolutos (`10gb`, `5gb`, `2gb`) para um indice local com teto de 2 GB

`main.py` tambem injeta essa configuracao no inicio quando `ES_HOME` esta definido, mas rodar `scripts/setup_es.py` deixa o ambiente explicito e mais facil de diagnosticar.

## Execucao da aplicacao

Com `ES_HOME` definido:

```bash
python3 main.py
```

Abra:

```text
http://127.0.0.1:5000
```

Fluxo de inicializacao:

1. `main.py` resolve e valida `ES_HOME`.
2. Copia a configuracao NitroFind para o Elasticsearch.
3. Inicia o processo do Elasticsearch em background.
4. Aguarda o cluster ficar `green` ou `yellow`.
5. Inicia o Flask em `127.0.0.1`.
6. A UI libera a busca quando `/api/status` retorna `status: ok`.

Para usar outra porta:

```bash
PORT=8080 python3 main.py
```

O host continua fixo em `127.0.0.1`.

## Criacao e atualizacao do indice

O indice principal se chama `car_articles`. O scraper cria o indice se ele ainda nao existir.

Antes de rodar o scraper, o Elasticsearch precisa estar ativo em `http://localhost:9200`. Voce pode deixar `python3 main.py` rodando em um terminal e executar o scraper em outro.

Rodar todas as fontes configuradas:

```bash
python3 -m scripts.scraper --all
```

Rodar apenas Wikipedia:

```bash
python3 -m scripts.scraper --wikipedia
```

Rodar apenas blogs:

```bash
python3 -m scripts.scraper --blogs
```

Usar um arquivo de configuracao alternativo:

```bash
python3 -m scripts.scraper --all --config config/scraper.yaml
```

Recriar o indice antes de coletar dados:

```bash
python3 -m scripts.scraper --all --recreate
```

Use `--recreate` quando a estrutura do indice mudar, por exemplo apos adicionar um novo campo ao mapping, ou depois de uma falha de indexacao. Esse modo tambem limpa o estado SQLite de retomada do scraper para que os artigos sejam coletados e indexados novamente.

## Configuracao do scraper

O arquivo principal e `config/scraper.yaml`.

Ele controla:

- categorias raiz da Wikipedia;
- profundidade maxima de varredura;
- intervalo de rate limit;
- User-Agent usado nas chamadas;
- lista de blogs habilitados;
- seletores CSS para listagem e corpo dos artigos;
- limite de tamanho usado para interromper indexacao antes do teto de 2 GB.

Antes de uma coleta real, ajuste o `user_agent` da Wikipedia para incluir um contato proprio. Isso segue a etiqueta da MediaWiki API e facilita contato caso alguma requisicao precise ser investigada.

## API local

### `GET /api/status`

Durante a inicializacao:

```json
{
  "status": "starting"
}
```

com HTTP 503.

Quando pronto:

```json
{
  "status": "ok",
  "es_health": "yellow",
  "doc_count": 1234,
  "index_size_bytes": 4567890
}
```

### `GET /api/search`

Parametros:

| Parametro | Obrigatorio | Descricao |
| --- | --- | --- |
| `q` | sim | Texto da busca. Se vier vazio, retorna `[]` sem consultar o ES. |
| `manufacturer` | nao | Filtro exato no campo `manufacturer`. |
| `era_bucket` | nao | Filtro exato, como `1960s` ou `2000s`. |
| `body_style` | nao | Filtro exato no campo `body_style`. |

Os filtros sao aplicados como `term` filters do Elasticsearch. Portanto, eles sao exatos e sensiveis ao valor indexado.

Exemplo:

```bash
curl "http://127.0.0.1:5000/api/search?q=mustang&manufacturer=Ford&era_bucket=1960s"
```

Resposta:

```json
[
  {
    "article_id": "12345",
    "title": "Ford Mustang",
    "url": "https://en.wikipedia.org/wiki/Ford_Mustang",
    "source_domain": "en.wikipedia.org",
    "excerpt": "Highlighted <b>excerpt</b>...",
    "score": 12.34,
    "took_ms": 8
  }
]
```

`/api/search` omite de proposito os campos completos do artigo, como `body`, `body_html`, `specs` e `hero_image_url`, para que cada busca com debounce continue leve.

### `GET /api/articles/<article_id>`

Retorna o payload completo de um resultado clicado. Essa rota so e chamada depois que o usuario seleciona um resultado, entao o HTML do artigo e os metadados da imagem nao afetam a latencia de digitacao da busca.

Exemplo:

```json
{
  "article_id": "12345",
  "title": "Ford Mustang",
  "url": "https://en.wikipedia.org/wiki/Ford_Mustang",
  "source_domain": "en.wikipedia.org",
  "excerpt": "The Ford Mustang is a pony car.",
  "body": "Full plain-text article body...",
  "body_html": "<div>Rendered article HTML...</div>",
  "hero_image_url": "https://upload.wikimedia.org/example.jpg",
  "manufacturer": "Ford",
  "production_start": 1964,
  "production_end": 2023,
  "era_bucket": "1960s",
  "body_style": "Coupe",
  "country_of_origin": "United States",
  "specs": {
    "engine": "V8"
  }
}
```

`hero_image_url` e opcional. A UI renderiza o dossie imediatamente e faz o fade-in da imagem quando ela termina de carregar.

## Modelo de relevancia

A busca usa `function_score` em cima do BM25 do Elasticsearch.

Sinais principais:

- `multi_match` em `title^3` e `body`;
- decaimento gaussiano em `published_at`, com escala de 730 dias;
- fallback para artigos sem data de publicacao;
- `field_value_factor` em `word_count` com `log1p`;
- boost para artigos com `has_infobox=true`;
- `score_mode: sum`;
- `boost_mode: multiply`.

Esse modelo e propositalmente explicito e reproduzivel. O projeto nao usa IA, embeddings, modelos externos ou APIs de ranking.

## Arquitetura

```text
main.py
  -> nitrofind.es_manager
       resolve ES_HOME, injeta config e valida binario
  -> nitrofind.server
       inicia ES em background, expoe Flask, /api/status e /api/search
  -> nitrofind.search.query_builder
       monta function_score, filtros, highlight e _source
  -> templates/index.html + static/js/app.js + static/css/style.css
       SPA local no navegador

scripts/scraper.py
  -> config/scraper.yaml
  -> nitrofind.scraper.wikipedia
       coleta paginas via MediaWiki API
  -> nitrofind.scraper.blogs
       coleta blogs via requests + BeautifulSoup
  -> nitrofind.scraper.cleaner
       normaliza texto, anos, era_bucket e excerpts
  -> nitrofind.scraper.indexer
       bulk indexing no Elasticsearch
  -> nitrofind.scraper.state
       SQLite para retomada e deduplicacao de visitas
```

## Estrutura do repositorio

```text
.
├── main.py                         # ponto de entrada da aplicacao web local
├── nitrofind/
│   ├── es_manager.py               # ciclo de vida/configuracao do Elasticsearch
│   ├── es_schema.py                # mapping do indice car_articles
│   ├── server.py                   # app Flask e rotas da API
│   ├── search/
│   │   ├── query_builder.py        # montagem das queries Elasticsearch
│   │   ├── models.py               # ArticleResult
│   │   └── engine.py               # mecanismo legado baseado em PyQt/QThreadPool
│   └── scraper/
│       ├── wikipedia.py            # scraper Wikipedia
│       ├── blogs.py                # scraper de blogs
│       ├── cleaner.py              # limpeza e derivacao de campos
│       ├── indexer.py              # bulk indexer e guarda de tamanho
│       └── state.py                # estado SQLite
├── scripts/
│   ├── setup_es.py                 # instala config no ES_HOME
│   ├── scraper.py                  # CLI do pipeline de coleta/indexacao
│   └── build_dist.py               # empacotamento legado v1.0
├── config/
│   ├── elasticsearch.yml           # configuracao single-node local
│   ├── jvm.options                 # heap JVM NitroFind
│   └── scraper.yaml                # fontes e parametros do scraper
├── templates/index.html            # UI HTML
├── static/css/style.css            # tema e layout
├── static/js/app.js                # controlador SPA
├── tests/                          # testes unitarios e integracao
├── requirements.in                 # dependencias diretas
├── requirements.txt                # lockfile com hashes
└── pytest.ini                      # marcadores pytest
```

## Testes

Rodar a suite sem testes de integracao:

```bash
python3 -m pytest -m "not integration"
```

Rodar todos os testes:

```bash
python3 -m pytest
```

Os testes marcados como `integration` podem exigir:

- `ES_HOME` definido;
- Elasticsearch funcional;
- acesso a internet em cenarios de Wikipedia ao vivo.

Alguns testes legados de `nitrofind/search/engine.py` sao ignorados automaticamente quando PyQt6 nao esta instalado. O caminho principal atual da aplicacao e Flask/browser.

## Dados gerados

O repositorio ignora artefatos locais em `.gitignore`, incluindo:

- `data/`
- `.venv/`
- `.pytest_cache/`
- `build/`
- `dist/`

O estado do scraper fica em:

```text
data/scraper_state.db
```

Os dados persistidos do Elasticsearch ficam no diretorio de dados da propria instalacao apontada por `ES_HOME`.

## Empacotamento

O repositorio ainda contem `nitrofind.spec` e `scripts/build_dist.py`, criados para o fluxo PyInstaller da v1.0.

Na v1.1+, a distribuicao suportada pelo planejamento do projeto passou a ser:

```bash
python3 main.py
```

Como as dependencias Qt foram removidas do lockfile atual, trate o fluxo PyInstaller como legado ate que ele seja revisado.

## Troubleshooting

### `ES_HOME is not set`

Defina a variavel apontando para a raiz da instalacao do Elasticsearch:

```bash
export ES_HOME=/caminho/para/elasticsearch-8.18.0
```

### `Elasticsearch binary not found`

Confira se existe:

```text
$ES_HOME/bin/elasticsearch
```

No estado atual, `main.py` espera o binario POSIX. Use Linux ou WSL.

### A UI fica em `Starting up...`

Verifique:

- se `ES_HOME` aponta para uma instalacao valida;
- se a porta `9200` esta livre;
- se a configuracao em `$ES_HOME/config/elasticsearch.yml` usa `discovery.type: single-node`;
- se a maquina tem memoria suficiente para iniciar o Elasticsearch com heap de 512 MB.

### `car_articles` fica `red` com `unassigned_primary_shards: 1`

Isso normalmente indica bloqueio de alocacao no Elasticsearch. No modo local do NitroFind, a configuracao copiada por `scripts/setup_es.py` usa watermarks absolutos de disco para evitar que uma particao grande, mas acima de 90% de uso, bloqueie um indice pequeno.

Reinicie a aplicacao para reinjetar a configuracao:

```bash
python3 main.py
```

Se o problema continuar, consulte:

```bash
curl -s "http://localhost:9200/_cluster/allocation/explain?pretty" -H "Content-Type: application/json" -d '{"index":"car_articles","shard":0,"primary":true}'
```

### A porta `5000` ja esta em uso

Use outra porta:

```bash
PORT=8080 python3 main.py
```

### Busca retorna poucos ou nenhum resultado

Confirme se o indice tem documentos:

```bash
curl http://127.0.0.1:5000/api/status
```

Se `doc_count` for `0`, rode o scraper.

### Scraper recebe HTTP 403 ou poucos artigos de blog

Os seletores e politicas dos sites podem mudar. Revise `config/scraper.yaml`, especialmente:

- `article_list_url`;
- `listing_selector`;
- `article_selector`;
- `headers`;
- `user_agent`.

### Mudou o mapping e documentos antigos nao exibem HTML

Rode o scraper com `--recreate` para reconstruir `car_articles` com o schema atual.

## Seguranca e limites

- A aplicacao escuta em `127.0.0.1`, nao em `0.0.0.0`.
- O Elasticsearch e iniciado sem `shell=True`.
- `ES_HOME` e validado antes de executar o binario.
- O mapping usa `dynamic: "false"` para evitar campos inesperados.
- A API usa indice fixo `car_articles`, nao informado pelo usuario.
- O tamanho de resposta e limitado no `query_builder`.
- O scraper usa `yaml.safe_load`.
- O estado SQLite usa parametros SQL, sem interpolacao de query.
- O projeto e local e single-user. Nao ha autenticacao, multiusuario ou modo cloud.

## Roadmap resumido

v1.2 esta em andamento e cobre:

- melhorar renderizacao de artigos e tabelas;
- reduzir ruido no corpo extraido dos artigos;
- adicionar busca fuzzy;
- adicionar busca por frase entre aspas;
- adicionar ordenacao por relevancia, data e tamanho;
- adicionar filtros por ano e pais de origem;
- adicionar paginacao;
- salvar historico local das ultimas buscas;
- adicionar alternancia de tema claro/escuro.

## Licenca

Nenhum arquivo de licenca foi encontrado no repositorio. Defina uma licenca antes de distribuir o projeto publicamente.
