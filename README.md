# OpenF1 Data Engineering

![Capa do projeto](assets/openf1-capa.png)

Projeto de Engenharia de Dados construído a partir da API pública [OpenF1](https://openf1.org/). O objetivo é transformar registros de uma sessão de Fórmula 1 em um conjunto de dados reproduzível, rastreável e pronto para análise, preservando a separação entre ingestão, armazenamento bruto, tratamento, agregação analítica e consumo relacional.

O recorte de referência deste repositório é a sessão `session_key=9158`: o primeiro treino livre do Grande Prêmio de Singapura de 2023, em Marina Bay. O ponto central do projeto é `car_data`: não se trata de uma telemetria genérica do evento, mas da telemetria gerada pelo carro de cada piloto participante daquela sessão. A ingestão consulta a lista de pilotos e faz uma requisição de `car_data` para cada combinação de `session_key` e `driver_number`.

## Situação atual

O projeto deixou de ser apenas uma prova de ingestão e agora possui um fluxo funcional de ponta a ponta para uma sessão:

```text
OpenF1
   ↓
Cliente HTTP com limite, timeout e retry
   ↓
Bronze: JSON bruto por execução e por piloto
   ↓
Validação, normalização, tipos, deduplicação e lineage
   ↓
Silver: Parquet particionado por session_key
   ↓
Gold: tabelas analíticas de sessão, piloto, volta, telemetria, rádio e DRS
   ↓
PostgreSQL com substituição transacional por sessão → Metabase
```

Foram implementados nesta evolução:

- configuração por ambiente com `.env` e compatibilidade com `API_OPENF1` legado;
- cliente HTTP reutilizável com timeout, espera mínima entre chamadas e retry para falhas transitórias;
- ingestão parametrizada por `session_key`;
- isolamento de cada ingestão por `run_id`;
- requisição de `car_data` individual para cada piloto;
- escrita atômica de arquivos JSON;
- manifestos de ingestão, qualidade, Gold e pipeline;
- transformação Bronze → Silver com tipagem, limpeza e deduplicação por chave natural;
- filtro explícito para manter apenas a sessão solicitada;
- validações de schema, nulos de chave, duplicidade, domínio e escopo de sessão;
- camada Gold com sete conjuntos de dados analíticos, incluindo telemetria por volta;
- carregador para PostgreSQL e SQLite de teste;
- DDL PostgreSQL e consultas SQL de exemplo;
- suíte automatizada de regressão, contrato e recuperação;
- Airflow 3.3.1 com execução parametrizada e conferência do banco;
- Metabase 0.63.16 com dois dashboards, 19 análises e filtros de sessão e piloto;
- catálogo local de execuções, duração, volumes e checksums SHA-256;
- dependências congeladas e workflow de validação no GitHub;
- documentação técnica em português e imagens raster reais com tema de Fórmula 1.

## Snapshot de referência da sessão 9158

Os números abaixo foram medidos nos arquivos atualmente versionados em `data/bronze`, após filtrar `session_key=9158`. Eles documentam o estado do dado disponível no repositório, não uma garantia de que a API continuará retornando exatamente a mesma quantidade em uma nova coleta.

| Endpoint | Registros no recorte | Granularidade | Tratamento principal |
| --- | ---: | --- | --- |
| `sessions` | 1 | uma sessão | contexto do treino |
| `drivers` | 20 | um piloto na sessão | dimensão de piloto |
| `laps` | 475 | uma volta por piloto | tempos, setores e velocidades |
| `team_radio` | 29 | uma mensagem de rádio | comunicação disponível |
| `car_data` | 360.520 | uma amostra por piloto e instante | telemetria do carro |

Neste snapshot, os 360.520 registros de `car_data` estão distribuídos em 20 arquivos e correspondem a 18.026 amostras por piloto. A camada Gold resultante possui 1 linha de resumo de sessão, 20 linhas de desempenho por piloto, 475 linhas de desempenho por volta, 20 linhas de resumo de telemetria, 15 linhas de resumo de rádio e 103 combinações de estados de DRS observados.

A sétima tabela, `telemetry_lap_summary`, acrescenta 474 grupos de telemetria por volta. A volta sem início válido não recebe associação temporal. A coleta real repetida em 05/09/2026 confirmou os volumes do snapshot.

O endpoint `team_radio` possui cobertura diferente de `car_data`: somente os pilotos com mensagens disponíveis aparecem no resumo de rádio. A ausência de uma linha não significa que o piloto não tenha participado da sessão.

## Escopo da telemetria

![Telemetria individual por piloto](assets/openf1-telemetria.png)

Cada arquivo de telemetria é identificado por:

```text
session_key=9158
driver_number=N
date=instante_da_amostra
```

Os sinais preservados em `car_data` são `speed`, `n_gear`, `drs`, `throttle`, `brake` e `rpm`, além das chaves de sessão, evento, piloto e instante. A ordem temporal é mantida na Bronze e a Silver converte `date` para timestamp UTC e os sinais para tipos numéricos.

A decisão de particionar a ingestão por piloto atende simultaneamente ao volume do endpoint e à regra de negócio do projeto:

```text
GET /drivers?session_key=9158
       ↓
driver_number = 1, 2, 4, ...
       ↓
GET /car_data?session_key=9158&driver_number=1
GET /car_data?session_key=9158&driver_number=2
GET /car_data?session_key=9158&driver_number=4
       ↓
car_data/driver_number=N/data.json
```

O pipeline não mistura telemetria de outras sessões. A ingestão rejeita respostas com sessão ou piloto divergentes. A transformação filtra os catálogos históricos pela sessão solicitada e valida o resultado. Runs com manifesto de falha ou de outra sessão são ignoradas na descoberta automática; entradas parciais são rejeitadas pelo pipeline completo.

## Fonte e limites da OpenF1

A fonte é a [API OpenF1](https://api.openf1.org/v1), cuja [documentação oficial](https://openf1.org/docs/) descreve os endpoints, os filtros e os campos. Para dados históricos, a documentação informa acesso sem autenticação; dados em tempo real podem depender de plano e disponibilidade. A OpenF1 é uma fonte não oficial, portanto o projeto preserva a origem e não a trata como substituta de um feed oficial da Fórmula 1.

Pontos relevantes para interpretar o dado:

- `car_data` possui frequência aproximada de 3,7 Hz e representa sinais do carro, não uma leitura contínua de cada milissegundo;
- `speed` é velocidade em km/h;
- `n_gear` representa a marcha, com valores documentados de 0 a 8;
- os códigos de `drs` possuem estados intermediários; a Gold considera `10`, `12` e `14` como DRS ativo, conforme a tabela documentada;
- `brake` é preservado como código da origem, normalmente 0 ou 100, sem converter a coluna para booleano na Silver;
- a documentação permite filtrar os endpoints por `session_key` e, quando aplicável, por `driver_number`;
- a disponibilidade de `team_radio` é mais limitada que a de sessões, pilotos, voltas e telemetria;
- `country_code` é mantido como dado descritivo, mas não participa das chaves do modelo.

## Arquitetura

![Arquitetura do pipeline](assets/openf1-arquitetura.png)

### Bronze

A Bronze mantém a resposta da API próxima do formato original. Cada execução nova recebe um diretório próprio e um manifesto:

```text
data/bronze/
└── run_id=20230915T093000Z_a1b2c3d4/
    ├── manifest.json
    ├── sessions/
    │   └── sessions.json
    ├── drivers/
    │   └── drivers.json
    ├── laps/
    │   └── laps.json
    ├── team_radio/
    │   └── team_radio.json
    └── car_data/
        ├── driver_number=1/
        │   └── data.json
        ├── driver_number=4/
        │   └── data.json
        └── driver_number=...
            └── data.json
```

O snapshot histórico original do repositório também é aceito no formato legado, com `data/bronze/<endpoint>/*.json`. A transformação procura primeiro a execução mais recente em `run_id=*` e, quando não há execução nesse formato, utiliza os diretórios legados.

O manifesto de ingestão registra `run_id`, horário de início e término, `session_key`, URL base, endpoints solicitados, contagem por endpoint, contagem de telemetria por piloto e status final. Uma falha não apaga a execução parcial: o manifesto é atualizado para `failed` com a mensagem do erro.

### Silver

A Silver é a camada confiável para processamento analítico. O formato é Parquet, com partição por sessão quando o pipeline é executado pelo comando principal:

```text
data/silver/
└── session_key=9158/
    ├── quality_report.json
    ├── sessions/sessions.parquet
    ├── drivers/drivers.parquet
    ├── laps/laps.parquet
    ├── team_radio/team_radio.parquet
    └── car_data/car_data.parquet
```

Os dados da telemetria são consolidados em um único Parquet por sessão, mas continuam identificados por `driver_number`. A Silver adiciona as colunas de rastreabilidade `source_file`, `source_path` e `ingestion_run_id` quando elas estão disponíveis.

### Gold

A Gold não é uma cópia do endpoint. Ela contém tabelas derivadas que reduzem o custo de consultas e tornam explícita a pergunta analítica:

```text
data/gold/
└── session_key=9158/
    ├── session_summary.parquet
    ├── driver_session_performance.parquet
    ├── lap_performance.parquet
    ├── telemetry_summary.parquet
    ├── radio_summary.parquet
    ├── drs_state_summary.parquet
    ├── manifest.json
    └── pipeline_manifest.json
```

Os nomes, colunas, quantidade de linhas e caminhos de cada conjunto são registrados no manifesto Gold.

### PostgreSQL e consumo

O Compose fornece PostgreSQL 17, Metabase e Airflow opcional. O loader aplica o DDL, adquire um bloqueio transacional e substitui somente a sessão carregada com `DELETE + INSERT`. As sete tabelas são carregadas na mesma transação: qualquer falha provoca rollback. As chaves e tipos JSONB são preservados; outras sessões permanecem no banco. A política assume um snapshot completo da sessão, e não eventos incrementais isolados.

## Estrutura do repositório

```text
openf1-data-engineering/
├── assets/
│   ├── openf1-arquitetura.png
│   ├── openf1-capa.png
│   └── openf1-telemetria.png
├── config/
│   ├── __init__.py
│   └── settings.py
├── data/
│   ├── raw/
│   ├── bronze/
│   ├── silver/
│   └── gold/
├── docs/
│   ├── arquitetura.md
│   ├── contrato-de-dados.md
│   ├── fontes-e-limitacoes.md
│   ├── operacao.md
│   ├── qualidade.md
│   ├── roadmap.md
│   └── modelo-analitico.md
├── sql/
│   ├── ddl/001_create_analytics.sql
│   └── queries/
│       ├── 001_driver_session_performance.sql
│       └── 002_telemetry_by_driver.sql
├── src/
│   ├── gold/build.py
│   ├── ingestion/ingestion_openf1.py
│   ├── ingestion/openf1_client.py
│   ├── loading/loader.py
│   ├── pipeline.py
│   ├── quality/quality.py
│   ├── transformation/transform.py
│   └── utils/logger.py
├── tests/
│   ├── test_client.py
│   ├── test_gold.py
│   ├── test_ingestion.py
│   ├── test_loading.py
│   └── test_transformation.py
├── .env.example
├── .gitignore
├── docker-compose.yml
├── README.md
└── requirements.txt
```

## Configuração local

O projeto foi estruturado para ser executado a partir da raiz do repositório. O uso de módulos (`python -m`) mantém os imports de `config` e `src` consistentes.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
cp .env.example .env
```

O arquivo `.env` é ignorado pelo Git. Os parâmetros disponíveis são:

| Variável | Padrão | Finalidade |
| --- | --- | --- |
| `OPENF1_BASE_URL` | `https://api.openf1.org/v1` | URL base da API |
| `OPENF1_SESSION_KEY` | `9158` | sessão usada por padrão |
| `OPENF1_DATA_ROOT` | `data` | raiz das camadas de dados |
| `OPENF1_REQUEST_TIMEOUT` | `30` | timeout por requisição, em segundos |
| `OPENF1_MAX_RETRIES` | `3` | novas tentativas após falhas transitórias |
| `OPENF1_MIN_REQUEST_INTERVAL` | `2.1` | intervalo mínimo em segundos, considerando também 30 chamadas/minuto |
| `POSTGRES_URL` | vazio no ambiente real | conexão SQLAlchemy para carga |

`API_OPENF1` ainda é aceita como nome legado de URL para não quebrar ambientes antigos. Em caso de conflito, `OPENF1_BASE_URL` tem precedência.

## Execução

### Pipeline completo com nova ingestão

O comando abaixo consulta a API, grava a Bronze, transforma para a Silver e produz a Gold da sessão 9158:

```bash
python -m src.pipeline --session-key 9158
```

Para alterar a sessão sem editar o `.env`:

```bash
python -m src.pipeline --session-key 9160
```

A execução cria uma nova `run_id`; os dados de execuções anteriores não são sobrescritos.

### Reprocessamento offline do snapshot local

Para testar o pipeline sem consultar a API, usando o conteúdo já presente em `data/bronze`:

```bash
python -m src.pipeline \
  --skip-ingestion \
  --session-key 9158 \
  --bronze-root data/bronze \
  --silver-root data/silver \
  --gold-root data/gold
```

O transformador encontra automaticamente a execução mais recente em `run_id=*`; se não houver uma, utiliza a estrutura legada do snapshot.

### Executar cada etapa separadamente

```bash
python -m src.ingestion.ingestion_openf1 --session-key 9158
python -m src.transformation.transform --session-key 9158 --partitioned
python -m src.gold.build --session-key 9158
```

A ingestão também aceita uma seleção de endpoints para coleta parcial:

```bash
python -m src.ingestion.ingestion_openf1 \
  --session-key 9158 \
  --endpoints sessions drivers car_data
```

Uma coleta parcial não deve ser enviada diretamente à construção completa da Gold se os cinco datasets necessários não estiverem disponíveis.

### PostgreSQL local

O Compose sobe somente o banco, sem executar a pipeline automaticamente:

```bash
docker compose up -d postgres
python -m src.pipeline \
  --session-key 9158 \
  --load-database \
  --database-url postgresql+psycopg://openf1:openf1@localhost:5432/openf1
```

O carregador cria o schema `analytics` e preserva suas tabelas. O DDL também pode ser aplicado manualmente:

```bash
psql postgresql://openf1:openf1@localhost:5432/openf1 \
  -f sql/ddl/001_create_analytics.sql
```

A carga usa `append` após excluir apenas a sessão escolhida dentro da mesma transação. O manifesto identifica a sessão inclusive para tabelas vazias. Arrays com valores ausentes são convertidos para JSON válido, usando `null`.

### Testes e verificações

```bash
python -m pytest -q
python -m compileall -q config src tests
python -m pip check
git diff --check
```

Os testes não fazem chamadas à API: o cliente e a ingestão utilizam respostas falsas controladas. A execução sobre dados reais da sessão 9158 foi feita separadamente com `--skip-ingestion`.

## Responsabilidade dos módulos

| Módulo | Responsabilidade |
| --- | --- |
| `config/settings.py` | resolve ambiente, caminhos, sessão e conexão |
| `src/ingestion/openf1_client.py` | centraliza HTTP, timeout, limite e retry |
| `src/ingestion/ingestion_openf1.py` | consulta endpoints, particiona telemetria e grava manifestos |
| `src/transformation/transform.py` | lê JSON, normaliza, tipa, deduplica, valida e grava Parquet |
| `src/quality/quality.py` | contratos por endpoint, chaves e regras de domínio |
| `src/gold/build.py` | cria métricas analíticas por sessão, piloto, volta, rádio e DRS |
| `src/loading/loader.py` | carrega Parquet Gold em um banco SQL |
| `src/pipeline.py` | coordena ingestão, transformação, Gold e carga opcional |
| `src/utils/logger.py` | configura console e arquivo de log sem handlers duplicados |

## O que a Gold responde

### `session_summary`

Uma linha por sessão, com contexto do circuito, horário, ano e contagens de registros, pilotos, voltas, telemetria e rádio.

### `driver_session_performance`

Uma linha por piloto participante. Combina identidade, contexto da sessão, métricas de volta, velocidades de referência, resumo de telemetria, freio, DRS e rádio.

### `lap_performance`

Uma linha por volta e piloto. Mantém os campos de volta, setores e arrays de segmentos, e acrescenta `is_complete_lap`, melhor volta do piloto e delta para a melhor volta daquele piloto.

### `telemetry_summary`

Uma linha por piloto com quantidade, janela temporal, velocidade máxima e média, RPM máximo e médio, acelerador médio, amostras com freio e percentual de amostras com DRS ativo.

### `radio_summary`

Uma linha por piloto que tem rádio disponível, com contagem e janela temporal das mensagens.

### `telemetry_lap_summary`

Uma linha por piloto e volta com amostras associadas pela janela temporal. Inclui quantidade de amostras, velocidade máxima e média, RPM médio e início/fim observado. Não interpola gaps e não associa amostras fora da janela.

### `drs_state_summary`

Uma linha por combinação observada de piloto e código de DRS, com número de amostras. É útil para separar estados fechado, disponível, acionado e transições sem destruir o código original.

## Regras de qualidade

O relatório de qualidade é salvo junto da Silver como `quality_report.json`. Cada dataset registra:

- colunas presentes, ausentes e não documentadas;
- chave natural adotada;
- linhas com chave nula;
- linhas duplicadas antes da deduplicação;
- linhas removidas pela deduplicação;
- divergências de `session_key`;
- nulos por coluna;
- erros bloqueantes e avisos preservados;
- status `success`, `warning` ou `failed`.

Erros bloqueantes interrompem a transformação, por exemplo, chave ausente, sessão misturada, data inválida na chave, velocidade negativa ou marcha fora do domínio documentado. Avisos não alteram o valor de origem, como os 102.942 registros em que o snapshot apresenta `throttle` acima de 100.

As chaves naturais são:

| Dataset | Chave natural |
| --- | --- |
| `sessions` | `session_key` |
| `drivers` | `session_key`, `driver_number` |
| `laps` | `session_key`, `driver_number`, `lap_number` |
| `team_radio` | `session_key`, `driver_number`, `recording_url` |
| `car_data` | `session_key`, `driver_number`, `date` |

O campo `date` de `team_radio` é opcional porque a própria disponibilidade do endpoint pode trazer mensagens sem timestamp. `recording_url` participa da identidade do registro.

## Roadmap

O roadmap completo, com prioridade, dependências e critérios de aceite, está em [`docs/roadmap.md`](docs/roadmap.md). Em resumo:

### Concluído nesta etapa

- pipeline parametrizado por sessão;
- telemetria isolada por piloto;
- Bronze, Silver e Gold funcionais;
- qualidade e lineage;
- carga SQL local;
- testes automatizados;
- DDL, consultas, imagens e documentação técnica.

### Ambiente integrado entregue

O roteiro completo está em [serviços e entrega](docs/servicos-e-entrega.md). PostgreSQL foi validado com duas recargas, chaves primárias, JSONB e consultas SQL. A nova coleta de 05/09/2026 confirmou os mesmos volumes da sessão 9158. Airflow executou o pipeline e conferiu o banco com sucesso. Metabase possui dois dashboards, 19 análises e filtros de sessão e piloto. A suíte e o CI incluem verificações de contrato, fronteiras temporais e recuperação.

```bash
mkdir -p logs
docker compose up -d postgres metabase
docker compose --profile execucao run --rm --build pipeline
docker compose exec -T postgres psql -U openf1 -d openf1 < sql/ddl/002_leitura_metabase.sql
python -m scripts.configurar_metabase
docker compose --profile orquestracao up -d --build airflow
```

O Metabase está em `http://localhost:3000` e o Airflow em `http://localhost:8080`. A senha local do Metabase é gerada e guardada em `logs/metabase-config.json`, ignorado pelo Git. Os serviços são publicados apenas em loopback. Consulte o guia de serviços para obter a senha gerada pelo Airflow.

### Evoluções opcionais

Implantação em servidor, TLS, backups externos, alertas remotos, armazenamento de objetos e novos endpoints dependem do ambiente operacional escolhido. O roadmap distingue esses trabalhos da versão local concluída.

## Documentação detalhada

- [`docs/arquitetura.md`](docs/arquitetura.md): desenho de camadas, fluxo, responsabilidades e recuperação;
- [`docs/contrato-de-dados.md`](docs/contrato-de-dados.md): schemas, tipos, chaves e semântica dos campos;
- [`docs/modelo-analitico.md`](docs/modelo-analitico.md): Gold, métricas, fórmulas e consultas;
- [`docs/qualidade.md`](docs/qualidade.md): validações, lineage, avisos e critérios de aceite;
- [`docs/operacao.md`](docs/operacao.md): comandos, manifestos, logs, reprocessamento e troubleshooting;
- [`docs/fontes-e-limitacoes.md`](docs/fontes-e-limitacoes.md): documentação OpenF1, cobertura e limites de interpretação;
- [`docs/roadmap.md`](docs/roadmap.md): itens concluídos, pendentes, dependências e definição de pronto.

## Licença e uso dos dados

Este repositório é educacional e de portfólio. A utilização dos dados deve respeitar os termos, limites e disponibilidade publicados pela [OpenF1](https://openf1.org/). O projeto não reivindica propriedade sobre os dados da Fórmula 1 e mantém os identificadores oficiais dos endpoints para facilitar auditoria.
