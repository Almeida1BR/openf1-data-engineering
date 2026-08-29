# OpenF1 Data Engineering Project

Projeto de Engenharia de Dados utilizando dados da API pública OpenF1.

O objetivo deste projeto é construir, de forma incremental, um pipeline de dados baseado em informações da Fórmula 1, passando pelas etapas de ingestão, armazenamento, transformação e preparação dos dados para análises futuras.

## Objetivo

Consumir dados disponibilizados pela API OpenF1 e utilizá-los para praticar conceitos de Engenharia de Dados, incluindo:

- Consumo de APIs REST
- Ingestão de dados
- Manipulação de dados em JSON
- Organização em camadas de dados
- Limpeza e transformação
- Persistência de dados
- Logging
- Testes automatizados
- Boas práticas de organização de projetos em Python

## Fonte dos dados

Os dados serão obtidos através da API OpenF1.

A API disponibiliza diferentes informações relacionadas às sessões de Fórmula 1, como:

- Pilotos
- Sessões
- Voltas
- Tempos de volta
- Pit stops
- Posições
- Telemetria
- Clima
- Resultados
- Dados de corrida

## Arquitetura inicial

O fluxo inicial planejado para o projeto será:

```text
OpenF1 API
    ↓
Ingestion
    ↓
Raw
    ↓
Bronze
    ↓
Transformation
    ↓
Silver
    ↓
Gold
```

Cada camada terá uma responsabilidade específica dentro do pipeline.

### Raw

Armazena os dados exatamente como foram recebidos da API, sem alterações.

### Bronze

Representa a primeira camada persistida do pipeline, mantendo os dados próximos do formato original.

### Silver

Contém dados limpos, padronizados e tratados.

Exemplos:

- Correção de tipos
- Tratamento de valores nulos
- Padronização de nomes
- Remoção de registros inválidos
- Tratamento de datas

### Gold

Camada destinada aos dados já preparados para consumo.

Pode futuramente alimentar:

- Dashboards
- Relatórios
- Análises
- Métricas
- Modelos analíticos

## Estrutura do projeto

```text
openf1-data-engineering/
├── config/
│   ├── __init__.py
│   └── settings.py
│
├── data/
│   ├── raw/
│   ├── bronze/
│   ├── silver/
│   └── gold/
│
├── docs/
├── logs/
├── notebooks/
│
├── src/
│   ├── ingestion/
│   │   ├── __init__.py
│   │   └── openf1_client.py
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

## Tecnologias iniciais

O projeto utilizará inicialmente:

- Python
- Requests
- Pandas
- Python-dotenv
- Pytest

Novas tecnologias poderão ser adicionadas conforme a evolução do projeto.

## Configuração do ambiente

Criar um ambiente virtual:

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

## Variáveis de ambiente

Criar um arquivo `.env` baseado no `.env.example`:

```bash
cp .env.example .env
```

Configuração inicial:

```env
OPENF1_BASE_URL=https://api.openf1.org/v1
```

## Status do projeto

Projeto em fase inicial de desenvolvimento.

A primeira etapa será implementar o cliente responsável pela comunicação com a API OpenF1 e realizar a ingestão dos primeiros dados.

## Próximas etapas

1. Implementar comunicação com a OpenF1.
2. Realizar a primeira requisição.
3. Salvar a resposta original na camada `raw`.
4. Implementar logging.
5. Criar tratamento inicial dos dados.
6. Estruturar as camadas Bronze, Silver e Gold.
7. Adicionar testes automatizados.
8. Avaliar posteriormente persistência em banco de dados.
9. Automatizar o pipeline.
10. Evoluir a arquitetura conforme novas necessidades surgirem.

## Finalidade

Este projeto possui finalidade educacional e de portfólio, sendo desenvolvido como prática de conceitos e ferramentas utilizadas em Engenharia de Dados.
