# Operação local e reprocessamento

## 1. Pré-requisitos

- Python 3.12 ou compatível com as dependências do projeto;
- acesso à internet apenas quando uma nova ingestão for desejada;
- Docker e Docker Compose para PostgreSQL, Metabase e Airflow;
- espaço em disco proporcional ao volume de `car_data`;
- execução dos comandos a partir da raiz do repositório.

Os comandos usam `python -m` porque o projeto organiza `config` e `src` como pacotes importáveis.

## 2. Preparar o ambiente

```bash
cd /home/almeida/workspace/openf1-data-engineering
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
cp .env.example .env
```

Não coloque tokens, credenciais ou URLs privadas no Git. O `.env` já está no `.gitignore`.

## 3. Operação recomendada

### 3.1 Coleta e processamento completos

```bash
python -m src.pipeline --session-key 9158
```

O fluxo executa:

```text
consulta OpenF1
   → escrita Bronze com run_id
   → transformação Silver particionada
   → quality_report.json
   → construção Gold
   → manifest.json e pipeline_manifest.json
```

A saída fica em `data/bronze`, `data/silver/session_key=9158` e `data/gold/session_key=9158`.

### 3.2 Reprocessamento sem rede

```bash
python -m src.pipeline \
  --skip-ingestion \
  --session-key 9158 \
  --bronze-root data/bronze \
  --silver-root data/silver \
  --gold-root data/gold
```

Esse modo é o recomendado para revisar transformações e métricas sem consumir chamadas da API. A transformação seleciona a execução `run_id=*` mais recente; no snapshot atual, utiliza os diretórios legados porque a Bronze versionada está nesse formato.

### 3.3 Reprocessar uma execução específica

```bash
python -m src.pipeline \
  --skip-ingestion \
  --session-key 9158 \
  --bronze-root data/bronze/run_id=20230915T093000Z_a1b2c3d4 \
  --silver-root data/silver \
  --gold-root data/gold
```

Use o valor real do diretório. Não invente uma `run_id`; ela deve existir na Bronze.

### 3.4 Executar etapas isoladas

```bash
python -m src.ingestion.ingestion_openf1 --session-key 9158
python -m src.transformation.transform --session-key 9158 --partitioned
python -m src.gold.build --session-key 9158
python -m src.loading.loader \
  --gold-root data/gold/session_key=9158 \
  --database-url postgresql+psycopg://openf1:openf1@localhost:5432/openf1
```

O carregamento deve receber a pasta que contém diretamente os Parquets Gold, não apenas a raiz `data/gold`.

## 4. Opções de linha de comando

### `src.pipeline`

| Opção | Efeito |
| --- | --- |
| `--session-key` | substitui a sessão do ambiente |
| `--bronze-root` | altera a raiz de entrada/saída Bronze |
| `--silver-root` | altera a raiz Silver |
| `--gold-root` | altera a raiz Gold |
| `--skip-ingestion` | usa Bronze existente |
| `--load-database` | executa também a carga SQL |
| `--database-url` | sobrescreve `POSTGRES_URL` |

### `src.ingestion.ingestion_openf1`

| Opção | Efeito |
| --- | --- |
| `--session-key` | escolhe a sessão |
| `--output-root` | altera a raiz da Bronze |
| `--endpoints` | coleta apenas endpoints selecionados |

### `src.transformation.transform`

| Opção | Efeito |
| --- | --- |
| `--bronze-root` | raiz dos JSONs |
| `--silver-root` | raiz dos Parquets |
| `--session-key` | filtro defensivo |
| `--partitioned` | escreve em `session_key=<valor>` |

### `src.gold.build`

| Opção | Efeito |
| --- | --- |
| `--silver-root` | raiz dos Parquets Silver |
| `--gold-root` | raiz dos Parquets Gold |
| `--session-key` | partição e filtro da sessão |

## 5. Logs

Cada executável configura um arquivo em `logs/`:

```text
logs/
├── ingestion.log
├── transformation.log
├── gold.log
├── loading.log
└── pipeline.log
```

O logger evita handlers duplicados quando a aplicação é importada ou quando mais de uma etapa é executada no mesmo processo. As mensagens registram endpoint, contagem, status, caminhos e identificadores de execução.

## 6. Manifesto de ingestão

Uma execução completa produz uma estrutura equivalente a:

```json
{
    "run_id": "20230915T093000Z_a1b2c3d4",
    "session_key": "9158",
    "endpoints": ["sessions", "drivers", "laps", "team_radio", "car_data"],
    "records": {
        "sessions": 1,
        "drivers": 20,
        "laps": 475,
        "team_radio": 29,
        "car_data": {
            "drivers": 20,
            "total": 360520,
            "by_driver": {
                "1": 18026
            }
        }
    },
    "status": "success"
}
```

Os números são ilustrativos do snapshot 9158. A execução real acrescenta todos os pilotos e horários.

## 7. Verificações de uma execução

```bash
test -f data/silver/session_key=9158/quality_report.json
test -f data/gold/session_key=9158/manifest.json
test -f data/gold/session_key=9158/pipeline_manifest.json
python -m pytest -q
python -m compileall -q config src tests
python -m pip check
git diff --check
```

Para inspecionar contagens sem carregar tudo na memória:

```bash
python -c 'import pandas as pd; print(pd.read_parquet("data/gold/session_key=9158/driver_session_performance.parquet").shape)'
```

## 8. PostgreSQL local

### Subir o serviço

```bash
docker compose up -d postgres
docker compose ps
```

O Compose não inicia a pipeline e não baixa dados por conta própria. Ele fornece apenas o banco local `openf1` na porta `5432`.

### Aplicar o DDL

```bash
psql postgresql://openf1:openf1@localhost:5432/openf1 \
  -f sql/ddl/001_create_analytics.sql
```

### Carregar a Gold

```bash
python -m src.loading.loader \
  --gold-root data/gold/session_key=9158 \
  --database-url postgresql+psycopg://openf1:openf1@localhost:5432/openf1
```

O carregador usa `append` com exclusão prévia restrita à sessão e executada na mesma transação. O DDL é aplicado automaticamente e as chaves permanecem após a carga. Execute `python -m scripts.validar_banco` com `POSTGRES_URL` configurada para verificar recarga idempotente, JSONB, chaves e consultas.

### Parar o serviço

```bash
docker compose down
```

O volume `openf1_postgres_data` permanece. A remoção do volume é uma operação destrutiva e não faz parte do fluxo normal de desenvolvimento.

## 9. Troubleshooting

### `ModuleNotFoundError: No module named config`

Execute os módulos a partir da raiz:

```bash
cd /home/almeida/workspace/openf1-data-engineering
python -m src.pipeline --session-key 9158
```

### `Bronze não encontrada`

Verifique se `data/bronze` existe, se `OPENF1_DATA_ROOT` aponta para o diretório correto e se há endpoints diretos ou um `run_id=*` válido.

### `Colunas obrigatórias ausentes`

Inspecione o JSON original e o `quality_report.json`. Uma mudança de contrato da API deve ser tratada em `src/quality/quality.py` e nos testes, não contornada removendo a validação.

### `Linhas fora da sessão`

O arquivo ou resposta contém dados de outra sessão. Preserve a Bronze para auditoria, corrija o recorte da coleta e reexecute. Não misture sessões manualmente para “fazer passar”.

### `Resposta não JSON`

Confira URL base, disponibilidade da API, timeout e limite de requisições. O cliente já repete erros transitórios; aumente o timeout ou o intervalo apenas após verificar a situação da fonte.

### Gold sem rádio para um piloto

Isso é esperado quando não existe mensagem disponível. Consulte `drivers` ou `driver_session_performance`; não interprete ausência em `radio_summary` como ausência de participação.

## 10. Retenção e reprodutibilidade

Cada run de ingestão é preservado para facilitar comparação e auditoria. Em um ambiente de produção, será necessário definir:

- retenção de runs brutos;
- política de compactação e arquivamento;
- identificador imutável da resposta da API;
- checksum dos arquivos;
- política de reprocessamento de uma sessão;
- limpeza segura de artefatos temporários;
- histórico de versão do contrato.

Não há exclusão automática: Bronze e logs de execução são retidos integralmente por padrão. `logs/executions/` mantém identificador, duração, status, linhas, bytes e SHA-256 da Gold. A Silver e a Gold representam a última versão processada da partição; para reconstruir uma versão anterior, indique sua Bronze com `--bronze-root`.
