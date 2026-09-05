# Serviços e entrega integrada

## 1. Arquitetura operacional

PostgreSQL 17 armazena a Gold. Metabase 0.63.16 consulta o banco com usuário de leitura. Airflow 3.3.1 executa a DAG parametrizada e verifica as contagens. O pipeline continua utilizável diretamente por Python ou container. A nova coleta em 05/09/2026 confirmou 20 pilotos e 360.520 amostras da sessão 9158.

| Serviço | Endereço | Persistência |
| --- | --- | --- |
| PostgreSQL analítico | localhost:5432 | volume openf1_postgres_data |
| Metabase | http://localhost:3000 | PostgreSQL separado, volume metabase_data |
| Airflow | http://localhost:8080 | volume airflow_data |
| Pipeline | execução por comando | diretórios data e logs |

Os nomes físicos de volumes recebem o prefixo do projeto Compose. O banco interno do Metabase não publica porta no host. As portas públicas dos serviços locais usam 127.0.0.1.

## 2. Reprodução em máquina limpa

Na raiz do repositório, com Python 3.12 e Docker Compose:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
mkdir -p logs
docker compose up -d postgres metabase
docker compose --profile execucao run --rm --build pipeline
docker compose exec -T postgres psql -U openf1 -d openf1 < sql/ddl/002_leitura_metabase.sql
python -m scripts.configurar_metabase
docker compose --profile orquestracao up -d --build airflow
```

Aguarde `/api/health` do Metabase retornar status `ok` antes do bootstrap. A primeira inicialização realiza migrações internas. O container pipeline usa a Bronze existente. Para nova coleta e processamento, execute `python -m src.pipeline --session-key 9158`.

Preserve o `.env` existente. Para carregar pela CLI, configure `POSTGRES_URL=postgresql+psycopg://openf1:openf1@localhost:5432/openf1`. Dentro dos containers, a conexão utiliza `postgres` como host, configurado no Compose.

## 3. Credenciais

O script cria o administrador do Metabase com e-mail `almeida@openf1.local` e senha aleatória. Credenciais e IDs ficam em `logs/metabase-config.json`, com permissão 0600 e exclusão pelo Git. Preserve esse arquivo para repetir o bootstrap sem criar novos cartões. Não publique seu conteúdo.

O usuário do banco para BI é `openf1_leitura`, com CONNECT, USAGE e SELECT. Não possui INSERT, UPDATE ou DELETE. As senhas dos bancos no Compose são destinadas à demonstração local.

O Airflow utiliza o administrador `almeida`. Sua senha gerada está no volume persistente. Consulte no seu terminal:

```bash
docker compose exec airflow cat /opt/airflow/simple_auth_manager_passwords.json.generated
```

## 4. Dashboard

O bootstrap cria ou atualiza 19 cartões distribuídos em dois dashboards e imprime suas URLs. Nesta instalação os IDs são 2 e 3; uma instalação nova pode produzir outros IDs.

| Cartão | Conteúdo |
| --- | --- |
| Melhor volta por piloto | menor volta completa, excluindo saída de box |
| Velocidade máxima por piloto | maior velocidade de toda a telemetria da sessão |
| DRS ativo por piloto (%) | proporção de amostras nos estados 10, 12 ou 14 |
| Voltas e cobertura de telemetria | equipe, voltas, amostras e rádios |
| Telemetria por volta | amostras e velocidade por janela temporal |

Os filtros Sessão e Piloto alimentam parâmetros SQL numéricos. O padrão da sessão é 9158 e o dashboard de telemetria inicia no piloto 1. Uma sessão ou piloto sem dados carregados deve retornar ausência de resultados. O script verifica as 19 consultas antes de informar conclusão. As interfaces usam português quando disponível; nomes oficiais da API permanecem no contrato.

## 5. Orquestração

A DAG `openf1_sessao` recebe `session_key` inteira positiva e `usar_snapshot` booleano. A tarefa executar chama o pipeline e retorna o caminho do manifesto. A tarefa verificar compara as contagens SQL com a Gold. A telemetria não é transferida pelo XCom.

```bash
docker compose exec airflow airflow dags unpause openf1_sessao
docker compose exec airflow airflow dags trigger openf1_sessao
docker compose exec airflow airflow dags list-runs openf1_sessao
docker compose exec airflow airflow dags list-import-errors
```

O padrão é execução manual. Para agenda, configure `OPENF1_SCHEDULE` no ambiente do serviço Airflow com expressão cron e recrie o serviço. `max_active_runs=1` impede duas execuções simultâneas da DAG. Há duas novas tentativas por tarefa, separadas por dois minutos. `usar_snapshot=false` consulta a API novamente.

O modo standalone concentra os componentes e usa metadados locais. Uma implantação compartilhada requer topologia operacional própria, conforme a documentação do Airflow.

## 6. Carga e recuperação

O DDL 001 cria sete tabelas. O loader adquire advisory lock e carrega todas na mesma transação. Cada tabela tem apenas a sessão do manifesto excluída antes de inserir seu snapshot atual. Uma tabela de rádio vazia também remove mensagens antigas dessa sessão quando o manifesto está presente.

Falhas de tipos ou chaves causam rollback. O loader não utiliza DROP nem replace. Tabelas PostgreSQL desconhecidas são rejeitadas. A segunda carga mantém as contagens e constraints. Os arrays de segmentos são JSONB; valores ausentes viram null JSON. Timestamps são convertidos para UTC.

A estratégia exige um snapshot completo da sessão. Não envie um fragmento de dados esperando atualização por evento. Para múltiplas sessões, processe e carregue cada partição separadamente.

## 7. Associação temporal

`telemetry_lap_summary` usa a última volta iniciada antes da amostra, dentro do mesmo piloto e sessão. A janela tem início inclusivo e fim exclusivo. Seu limite final é o menor valor disponível entre início mais duração e início da próxima volta. Sem início ou sem limite final não há associação. Gaps não são interpolados.

O snapshot possui 475 voltas e gerou 474 grupos de telemetria; uma volta não possui início válido. Um grupo não implica volta competitiva válida: voltas de box continuam identificadas em lap_performance. Melhor volta e média usam duração e setores disponíveis, excluindo saídas de box.

## 8. Auditoria e retenção

Cada chamada ao pipeline cria `logs/executions/<id>.json`, inclusive em falha. O registro possui início, fim, duração, sessão, status e tipo de erro. Em sucesso registra linhas, bytes e SHA-256 de cada Parquet Gold. A escrita do registro é atômica.

A Bronze é retida integralmente. Silver e Gold representam o último processamento da partição. Reconstitua uma versão anterior indicando sua Bronze com `--bronze-root`. Execute uma sessão por vez sobre os mesmos diretórios; o bloqueio SQL não bloqueia escritas Parquet. Use raízes distintas para processamento paralelo independente.

## 9. Verificações

```bash
python -m pytest -q
python -m compileall -q config src tests dags scripts
python -m pip check
POSTGRES_URL=postgresql+psycopg://openf1:openf1@localhost:5432/openf1 python -m scripts.validar_banco
docker compose config --quiet
```

O script de banco recarrega duas vezes, verifica contagens, chaves, JSONB e consultas SQL. O workflow do GitHub utiliza PostgreSQL 17 e requirements.lock. A execução remota ocorre após publicação; não é validada apenas pela existência do arquivo YAML.

## 10. Encerramento

`docker compose --profile orquestracao stop` interrompe os serviços preservando volumes. Não remova volumes para encerrar o ambiente. Um backup completo inclui os bancos analíticos e de metadados, o volume Airflow, Bronze e credenciais locais protegidas. Teste a restauração antes de depender da instalação para operação contínua.

## 11. Fontes

- [OpenF1](https://openf1.org/docs/)
- [Metabase em Docker](https://www.metabase.com/docs/latest/installation-and-operation/running-metabase-on-docker)
- [API do Metabase](https://www.metabase.com/learn/metabase-basics/administration/administration-and-operation/metabase-api)
- [Airflow em Docker](https://airflow.apache.org/docs/apache-airflow/stable/howto/docker-compose/index.html)

As imagens PNG temáticas são ilustrações editoriais de apoio. As capturas de Metabase e Airflow demonstram páginas reais da execução local, incluindo PostgreSQL conectado, consulta Gold, dashboards, catálogo da DAG, grafo de tarefas e execução concluída. Elas não substituem os resultados calculados pelo pipeline; servem como evidência visual complementar.

![Conexão PostgreSQL no Metabase](imagens/prints/06-metabase-postgresql-conexao.png)

![Consulta analítica da camada Gold](imagens/prints/05-metabase-consulta-telemetria-volta.png)

![Catálogo real de DAGs do Airflow](imagens/prints/10-airflow-catalogo-dags.png)

![Grafo real da DAG openf1_sessao](imagens/prints/11-airflow-grafo-dag.png)
