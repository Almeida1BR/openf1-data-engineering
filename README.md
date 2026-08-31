# OpenF1 Data Engineering Project

Projeto de Engenharia de Dados desenvolvido a partir dos dados disponibilizados pela API pública OpenF1.

O objetivo é construir, de forma incremental, um pipeline de dados completo utilizando informações da Fórmula 1, passando pelas etapas de ingestão, armazenamento, transformação, persistência e preparação dos dados para consumo analítico.

O projeto possui finalidade educacional e de portfólio, buscando aplicar conceitos e ferramentas utilizadas em ambientes reais de Engenharia de Dados.

---

## Objetivos

O projeto utiliza dados da OpenF1 para praticar e desenvolver conhecimentos relacionados a:

- Consumo de APIs REST
- Ingestão de dados
- Manipulação de JSON
- Processamento de dados com Python
- Organização em arquitetura de camadas
- Limpeza e transformação de dados
- Conversão de JSON para Parquet
- Persistência de dados
- Padronização de schemas
- Tratamento de tipos
- Remoção de duplicidades
- Data lineage
- Logging
- Testes automatizados
- Banco de dados relacional
- Containerização
- Orquestração de pipelines
- Visualização de dados
- Boas práticas de organização de projetos de Engenharia de Dados

---

## Fonte dos dados

Os dados são obtidos através da API OpenF1:

```text
https://api.openf1.org/v1
```

Atualmente, o projeto utiliza os seguintes endpoints:

- `sessions`
- `drivers`
- `laps`
- `team_radio`
- `car_data`

---

## Dados utilizados

### Sessions

Contém informações relacionadas às sessões de um evento de Fórmula 1, como identificação da sessão e do evento, nome e tipo da sessão, país, circuito, datas de início e término e ano.

### Drivers

Contém informações relacionadas aos pilotos presentes em determinada sessão.

Entre os campos utilizados estão:

- `driver_number`
- `first_name`
- `last_name`
- `full_name`
- `name_acronym`
- `team_name`
- `country_code`
- `session_key`
- `meeting_key`

O endpoint `drivers` também é utilizado pela ingestão para identificar automaticamente os pilotos participantes de uma sessão.

### Laps

Contém informações relacionadas às voltas realizadas pelos pilotos, incluindo número da volta, duração da volta, tempos dos setores, velocidades intermediárias e chaves de identificação.

### Team Radio

Contém informações relacionadas às comunicações de rádio disponibilizadas durante as sessões.

### Car Data

O endpoint `car_data` contém dados de telemetria dos carros.

Entre as principais informações estão:

- `date`
- `session_key`
- `meeting_key`
- `driver_number`
- `speed`
- `n_gear`
- `drs`
- `throttle`
- `brake`
- `rpm`

Por possuir um volume significativamente maior de dados, sua ingestão é realizada separadamente para cada piloto.

A lista de pilotos é obtida automaticamente através do endpoint `drivers`. Para cada piloto, o pipeline utiliza `driver_number` e `session_key` como parâmetros da requisição.

Na camada Bronze, os arquivos de telemetria são armazenados utilizando o sobrenome do piloto:

```text
car_data/
├── verstappen.json
├── norris.json
├── hamilton.json
├── leclerc.json
└── ...
```

Essa abordagem evita a realização de uma única requisição extremamente grande para todos os pilotos.

---

## Arquitetura do pipeline

A arquitetura atual segue o fluxo:

```text
                 OpenF1 API
                     │
                     ▼
              Ingestion Layer
                     │
                     ▼
             ┌───────────────┐
             │    BRONZE     │
             │     JSON      │
             │  Dados brutos │
             └───────┬───────┘
                     │
                     ▼
               transform.py
                     │
                     ▼
             ┌───────────────┐
             │    SILVER     │
             │    Parquet    │
             │ Dados tratados│
             └───────┬───────┘
                     │
                     ▼
             ┌───────────────┐
             │     GOLD      │
             │   Planejada   │
             └───────┬───────┘
                     │
                     ▼
                PostgreSQL
                     │
                     ▼
                  Metabase
```

Posteriormente, o Apache Airflow será utilizado para orquestrar automaticamente as diferentes etapas do pipeline.

---

## Arquitetura em camadas

### Bronze

A camada Bronze contém os dados provenientes diretamente da OpenF1, persistidos em JSON e mantidos o mais próximo possível do formato retornado pela API.

```text
data/
└── bronze/
    ├── sessions/
    ├── drivers/
    ├── laps/
    ├── team_radio/
    └── car_data/
```

A separação por endpoint facilita rastreabilidade, reprocessamento, debug, auditoria e evolução do pipeline.

### Silver

A camada Silver contém os dados provenientes da Bronze após limpeza e padronização.

Os dados são armazenados em Apache Parquet e transformados através do script:

```text
src/transformation/transform.py
```

Entre os tratamentos realizados estão:

- Normalização dos nomes das colunas
- Padronização de strings
- Conversão de datas
- Conversão de colunas numéricas
- Tratamento de valores vazios
- Remoção de duplicidades
- Consolidação de múltiplos JSONs
- Reset de índices
- Adição de informação da origem dos dados

### Data Lineage

Durante a transformação é adicionada a coluna:

```text
source_file
```

Ela permite identificar de qual arquivo da camada Bronze determinado registro foi originado.

Exemplo:

```text
driver_number: 1
speed: 312
rpm: 11845
source_file: verstappen.json
```

### Consolidação do Car Data

Na camada Bronze, a telemetria é armazenada em múltiplos arquivos por piloto. Durante a transformação, todos os arquivos são lidos automaticamente e concatenados.

Na Silver, são consolidados em:

```text
data/silver/car_data/car_data.parquet
```

Fluxo:

```text
Vários JSONs Bronze
        │
        ▼
     Pandas
        │
        ▼
     concat()
        │
        ▼
car_data.parquet
```

### Gold

A camada Gold será responsável pelos dados preparados especificamente para consumo analítico.

Essa etapa ainda será desenvolvida.

Alguns exemplos de conjuntos de dados que poderão ser construídos:

- Performance por piloto
- Performance por volta
- Velocidade máxima por piloto
- Comparação de tempos de volta
- Uso de DRS
- Análise de aceleração e frenagem
- RPM por trecho
- Comparação entre pilotos
- Análise por sessão
- Métricas de telemetria
- Indicadores de desempenho

---

## Estrutura do projeto

```text
openf1-data-engineering/
│
├── config/
│   ├── __init__.py
│   └── settings.py
│
├── data/
│   ├── raw/
│   ├── bronze/
│   │   ├── sessions/
│   │   ├── drivers/
│   │   ├── laps/
│   │   ├── team_radio/
│   │   └── car_data/
│   │
│   ├── silver/
│   │   ├── sessions/
│   │   ├── drivers/
│   │   ├── laps/
│   │   ├── team_radio/
│   │   └── car_data/
│   │
│   └── gold/
│
├── docs/
├── logs/
├── notebooks/
│
├── src/
│   ├── ingestion/
│   │   ├── __init__.py
│   │   └── ingestion_openf1.py
│   │
│   ├── loading/
│   │   ├── __init__.py
│   │   └── loader.py
│   │
│   ├── transformation/
│   │   ├── __init__.py
│   │   └── transform.py
│   │
│   └── utils/
│       ├── __init__.py
│       └── logger.py
│
├── tests/
│   ├── __init__.py
│   └── test_ingestion.py
│
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

---

## Tecnologias utilizadas

### Atualmente implementadas

- Python
- Requests
- Pandas
- Python-dotenv
- Pytest
- PyArrow
- SQLAlchemy
- Apache Parquet

### Tecnologias planejadas

#### PostgreSQL 17

Será utilizado como banco de dados relacional para persistência dos dados tratados e das futuras tabelas analíticas.

#### Docker

Será utilizado para containerizar os serviços necessários para execução do ambiente do projeto.

#### Docker Compose

Será avaliado para subir e integrar serviços como PostgreSQL, Metabase e Airflow.

#### Metabase

Será utilizado para construção de dashboards e exploração dos dados armazenados no PostgreSQL.

#### Apache Airflow

Será utilizado posteriormente para orquestração do pipeline.

Fluxo planejado:

```text
Ingestão
   ↓
Validação
   ↓
Transformação
   ↓
Carga
   ↓
Gold
```

---

## Configuração do ambiente

Criar o ambiente virtual:

```bash
python3 -m venv .venv
```

Ativar o ambiente:

```bash
source .venv/bin/activate
```

Instalar as dependências:

```bash
pip install -r requirements.txt
```

---

## Principais dependências

O `requirements.txt` contém atualmente bibliotecas como:

```text
requests
pandas
python-dotenv
pytest
pyarrow
sqlalchemy
```

---

## Execução da ingestão

A ingestão dos dados da OpenF1 é realizada através do script:

```text
src/ingestion/ingestion_openf1.py
```

O fluxo de ingestão é responsável por:

1. Realizar requisições à OpenF1
2. Identificar os dados desejados
3. Obter os registros
4. Persistir os JSONs
5. Organizar os arquivos na camada Bronze

### Ingestão automatizada de telemetria

A telemetria exige uma estratégia diferente por possuir um volume muito maior de registros.

```text
OpenF1
   │
   ▼
GET /drivers
   │
   ▼
Obter driver_number
   │
   ▼
Loop pelos pilotos
   │
   ├── GET /car_data?driver_number=...
   ├── GET /car_data?driver_number=...
   ├── GET /car_data?driver_number=...
   └── ...
   │
   ▼
JSON individual por piloto
```

Essa abordagem evita requisições excessivamente grandes e torna a ingestão mais controlável.

---

## Execução da transformação

O processo Bronze → Silver é realizado através de:

```text
src/transformation/transform.py
```

Executar:

```bash
python3 src/transformation/transform.py
```

O script identifica automaticamente os diretórios existentes dentro de:

```text
data/bronze/
```

e executa a transformação para cada endpoint.

---

## Fluxo da transformação

```text
JSON Bronze
    │
    ▼
Leitura
    │
    ▼
pd.json_normalize()
    │
    ▼
DataFrame
    │
    ▼
Normalização das colunas
    │
    ▼
Limpeza de strings
    │
    ▼
Conversão de datas
    │
    ▼
Conversão numérica
    │
    ▼
Remoção de duplicatas
    │
    ▼
Parquet Silver
```

---

## Formato dos dados

### Bronze

Formato: JSON

Características:

- Próximo da resposta original
- Fácil inspeção
- Permite reprocessamento
- Mantém histórico da ingestão

### Silver

Formato: Parquet

Características:

- Formato colunar
- Tipado
- Comprimido
- Eficiente para leitura analítica
- Compatível com diferentes ferramentas de dados

---

## Estado atual do projeto

Atualmente o pipeline já possui:

- Estrutura inicial do projeto
- Ambiente virtual configurado
- Dependências Python configuradas
- Integração com OpenF1
- Ingestão de `sessions`
- Ingestão de `drivers`
- Ingestão de `laps`
- Ingestão de `team_radio`
- Ingestão de `car_data`
- Automação da ingestão de telemetria por piloto
- Persistência da camada Bronze
- Organização dos dados por endpoint
- Transformação Bronze → Silver
- Normalização dos dados
- Conversão de tipos
- Remoção de duplicidades
- Data lineage através de `source_file`
- Conversão para Apache Parquet
- Consolidação dos arquivos de telemetria
- Persistência da camada Silver
- Versionamento do projeto com Git

O pipeline atualmente alcança:

```text
OpenF1
   ↓
Ingestion
   ↓
Bronze
   ↓
Transformation
   ↓
Silver
```

---

## Próximas etapas

A evolução planejada do projeto é:

1. Validar os schemas individuais da camada Silver
2. Implementar regras de transformação específicas por endpoint
3. Criar validações de qualidade de dados
4. Implementar logging estruturado
5. Expandir os testes automatizados
6. Criar a camada Gold
7. Definir o modelo de dados analítico
8. Configurar PostgreSQL 17
9. Implementar carga dos dados no PostgreSQL
10. Criar infraestrutura com Docker
11. Integrar PostgreSQL e Metabase
12. Construir dashboards
13. Adicionar Apache Airflow
14. Criar DAGs para orquestração
15. Automatizar o pipeline completo

Arquitetura futura:

```text
OpenF1 API
    │
    ▼
Ingestion
    │
    ▼
Bronze
    │
    ▼
Silver
    │
    ▼
Gold
    │
    ▼
PostgreSQL
    │
    ▼
Metabase

       ▲
       │
Apache Airflow
Orquestração
```

---

## Possíveis análises futuras

A arquitetura construída permitirá desenvolver análises como:

- Comparação de pilotos
- Comparação de voltas
- Evolução da velocidade ao longo da volta
- Pontos de frenagem
- Uso do acelerador
- Uso do DRS
- RPM
- Marchas utilizadas
- Velocidades máximas
- Tempos por setor
- Desempenho por sessão
- Comparações de telemetria
- Relação entre sessão, piloto e desempenho

---

## Boas práticas aplicadas

Durante o desenvolvimento estão sendo aplicados conceitos como:

- Separação de responsabilidades
- Organização modular
- Arquitetura em camadas
- Versionamento com Git
- Commits incrementais
- Uso de ambiente virtual
- Dependências isoladas
- Configuração através de variáveis
- Separação entre dados brutos e tratados
- Utilização de Parquet para processamento analítico
- Rastreabilidade da origem dos registros
- Automação de tarefas repetitivas
- Desenvolvimento incremental

---

## Finalidade

Este projeto possui finalidade educacional e de portfólio.

Seu desenvolvimento busca simular a construção incremental de um pipeline de Engenharia de Dados, começando pela coleta dos dados e evoluindo gradualmente para transformação, armazenamento, modelagem, orquestração e visualização.

Além da exploração dos dados da Fórmula 1, o principal objetivo é desenvolver experiência prática com arquiteturas, ferramentas e boas práticas utilizadas em Engenharia de Dados.
