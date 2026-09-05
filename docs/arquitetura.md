# Arquitetura do OpenF1 Data Engineering

![Arquitetura visual do projeto](imagens/openf1-arquitetura.png)

## 1. Objetivo arquitetural

O projeto converte dados da [OpenF1](https://openf1.org/) em artefatos analíticos reproduzíveis para uma sessão de Fórmula 1. A unidade de isolamento é `session_key`. O recorte utilizado para desenvolvimento e validação é `session_key=9158`, o primeiro treino livre de Singapura em 2023.

A arquitetura foi desenhada para preservar quatro propriedades:

- o dado bruto deve continuar disponível para auditoria e reprocessamento;
- uma nova execução não deve destruir uma execução anterior;
- `car_data` deve ser coletado individualmente por `driver_number`;
- uma análise Gold não pode misturar sessões ou pilotos de respostas diferentes.

O fluxo é executável por linha de comando, container ou DAG Airflow. O Metabase consome o PostgreSQL com um usuário de leitura. A implantação integrada é local; infraestrutura remota permanece uma decisão operacional.

## 2. Visão de camadas

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ OpenF1 API                                                              │
│ sessions · drivers · laps · team_radio · car_data                       │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Ingestão                                                                │
│ filtro por session_key · car_data por driver_number · retry · manifesto │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Bronze                                                                  │
│ JSON próximo da origem · run_id · partição física por piloto            │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Qualidade e transformação                                               │
│ schema · chaves naturais · tipos · sessão · lineage · deduplicação       │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Silver                                                                  │
│ Parquet tipado · partição por session_key · quality_report.json          │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Gold                                                                    │
│ resumo de sessão · piloto · volta · telemetria · rádio · DRS             │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Consumo                                                                 │
│ Parquet · SQLAlchemy · PostgreSQL · Metabase                            │
└─────────────────────────────────────────────────────────────────────────┘
```

## 3. Fluxo de execução

### 3.1 Configuração

`config/settings.py` centraliza caminhos, URL, sessão padrão, timeout, retry, intervalo mínimo entre requisições e URL do banco. A leitura usa `python-dotenv`, mas variáveis já presentes no processo têm precedência sobre o `.env`.

O valor padrão de `OPENF1_SESSION_KEY` é `9158` porque essa é a sessão de referência do projeto. Qualquer execução pode receber outra sessão pela opção `--session-key`.

### 3.2 Cliente HTTP

`src/ingestion/openf1_client.py` é a única camada autorizada a realizar chamadas HTTP. Isso evita que cada endpoint implemente uma política diferente. O cliente:

- normaliza a URL base e o caminho do endpoint;
- envia `Accept: application/json`;
- aplica timeout por requisição;
- aguarda o intervalo mínimo configurado;
- repete falhas de rede e respostas `429`, `500`, `502`, `503` e `504`;
- respeita `Retry-After` quando a API o informa;
- valida que a resposta possui JSON em formato de lista ou objeto;
- converte falhas da biblioteca HTTP em `OpenF1ClientError`.

### 3.3 Ingestão

`src/ingestion/ingestion_openf1.py` recebe a sessão e a lista de endpoints. No fluxo completo:

1. consulta `sessions` com `session_key`;
2. consulta `drivers` com `session_key`;
3. consulta `laps` com `session_key`;
4. consulta `team_radio` com `session_key`;
5. percorre os `driver_number` obtidos em `drivers`;
6. consulta `car_data` com `session_key` e `driver_number`;
7. valida a identidade da sessão e do piloto na resposta;
8. grava os JSONs e atualiza o manifesto.

O `driver_number` vem da resposta de `drivers`; ele não é inferido do nome do arquivo. O nome do diretório de telemetria funciona como organização física, enquanto o campo da API continua sendo a fonte de verdade.

### 3.4 Escrita Bronze

Cada chamada completa cria um diretório `run_id=...`. A escrita é feita em um arquivo temporário no mesmo diretório e concluída com substituição atômica. Se o processo cair durante a serialização, o arquivo final não fica parcialmente escrito.

```text
data/bronze/run_id=<id>/
├── manifest.json
├── sessions/sessions.json
├── drivers/drivers.json
├── laps/laps.json
├── team_radio/team_radio.json
└── car_data/
    ├── driver_number=1/data.json
    ├── driver_number=4/data.json
    └── driver_number=...
```

O projeto também aceita a estrutura histórica plana já presente no repositório:

```text
data/bronze/
├── sessions/sessions.json
├── drivers/drivers.json
├── laps/laps.json
├── team_radio/team_radio.json
└── car_data/<sobrenome>.json
```

Quando a raiz contém mais de uma execução, `discover_endpoint_paths` seleciona a execução `run_id=*` mais recente. Se nenhuma existir, os diretórios planos são utilizados.

### 3.5 Transformação Silver

`src/transformation/transform.py` lê todos os JSONs de um endpoint recursivamente. Isso é importante para `car_data`, pois a Bronze possui uma pasta por piloto. A etapa executa:

1. normalização dos nomes das colunas;
2. remoção de espaços e conversão de strings vazias em nulos;
3. conversão das colunas temporais para UTC;
4. conversão dos sinais numéricos;
5. filtragem defensiva por `session_key`;
6. validação do DataFrame de entrada;
7. deduplicação por chave natural;
8. validação do DataFrame final;
9. gravação em Parquet;
10. registro do relatório de qualidade.

Quando `--partitioned` é usado, os datasets ficam em `data/silver/session_key=9158/<endpoint>/`. O relatório fica na raiz da partição.

### 3.6 Construção Gold

`src/gold/build.py` lê os cinco datasets Silver e gera sete tabelas. A Silver continua sendo a camada detalhada; a Gold responde perguntas de negócio com uma linha por sessão, piloto, volta, estado ou resumo.

As junções usam `session_key` e `driver_number`. A tabela `telemetry_lap_summary` associa amostras a janelas de volta com início inclusivo e fim exclusivo, limitado pela duração e pelo início da próxima volta. As demais tabelas mantêm seus agregados por piloto.

### 3.7 Carga SQL

`src/loading/loader.py` localiza os Parquets Gold, normaliza valores aninhados e carrega tabelas do schema `analytics`. PostgreSQL preserva JSONB e timestamps UTC. SQLite é utilizado nos testes rápidos.

A política atual substitui a sessão com `DELETE + INSERT` transacional, preservando tabelas, constraints e outras sessões. Um bloqueio PostgreSQL serializa cargas concorrentes. O DDL versionado define a estrutura; alterações futuras de colunas exigem uma migração SQL explícita.

## 4. Manifestos e rastreabilidade

Há quatro pontos de rastreabilidade:

| Artefato | Local | O que registra |
| --- | --- | --- |
| Manifesto de ingestão | Bronze `run_id=*/manifest.json` | sessão, endpoints, contagens, piloto e status |
| Relatório de qualidade | Silver `session_key=*/quality_report.json` | schema, nulos, duplicidades, avisos e erros |
| Manifesto Gold | Gold `session_key=*/manifest.json` | datasets, caminhos, linhas e colunas |
| Manifesto do pipeline | Gold `session_key=*/pipeline_manifest.json` | encadeamento das etapas e raízes usadas |

Além dos manifestos, a Silver preserva `source_file`, `source_path` e `ingestion_run_id` quando o registro veio de uma Bronze que possui essa informação.

## 5. Falhas e recuperação

### Falha HTTP

O cliente repete falhas transitórias. Depois do limite, a exceção sobe para a ingestão, o manifesto recebe `status=failed` e a execução parcial fica disponível para inspeção.

### Resposta de sessão incorreta

Se a API retornar registros com sessão diferente da solicitada, a ingestão interrompe a execução. A transformação possui a mesma defesa para o caso de arquivos históricos ou edição manual da Bronze.

### Resposta de piloto incorreta

Cada chamada de `car_data` é conferida contra o `driver_number` da iteração. Uma resposta que contenha outro piloto é rejeitada antes da gravação.

### Reprocessamento

O reprocessamento offline usa `--skip-ingestion` e mantém a Bronze como fonte. Para reconstruir uma Gold, basta apontar para a Bronze e informar a sessão. Para reproduzir uma coleta específica, informe explicitamente a pasta `run_id` como `--bronze-root`.

## 6. Decisões e não objetivos atuais

### Decisões

- `session_key` é o limite de isolamento de todos os datasets;
- `car_data` é coletado por piloto devido ao volume e ao requisito analítico;
- a origem bruta não é normalizada na Bronze;
- o timestamp é convertido para UTC apenas na Silver;
- códigos originais de `brake` e `drs` são preservados;
- avisos de domínio não alteram silenciosamente o dado de origem;
- Parquet é usado para leitura analítica local e interoperabilidade.

### Evoluções externas

- implantação Airflow com componentes separados e metadados gerenciados;
- ingestão incremental de eventos com watermark, além do snapshot por sessão;
- migrações de alteração de colunas para futuras versões;
- publicação do workflow e proteção de branch no GitHub;
- observabilidade externa e destinatários de alertas;
- associação espacial por distância e setores;
- testes de contrato periódicos contra a API real.

Esses itens estão detalhados em [`roadmap.md`](roadmap.md).
