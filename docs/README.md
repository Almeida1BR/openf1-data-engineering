# Documentação do projeto

## Entrada rápida

- [`../README.md`](../README.md): visão geral, instalação e comandos;
- [`arquitetura.md`](arquitetura.md): camadas, fluxo, armazenamento e recuperação;
- [`contrato-de-dados.md`](contrato-de-dados.md): endpoints, tipos, chaves e semântica;
- [`modelo-analitico.md`](modelo-analitico.md): tabelas Gold, métricas e perguntas;
- [`qualidade.md`](qualidade.md): regras, relatórios, lineage e testes;
- [`operacao.md`](operacao.md): execução, logs, manifestos e troubleshooting;
- [`fontes-e-limitacoes.md`](fontes-e-limitacoes.md): pesquisa OpenF1, cobertura e limites;
- [`roadmap.md`](roadmap.md): critérios concluídos e evoluções para operação externa;
- [`servicos-e-entrega.md`](servicos-e-entrega.md): PostgreSQL, Airflow, Metabase, credenciais e reprodução.

## Imagens

O conjunto visual combina imagens editoriais em tema de Fórmula 1 com prints reais das páginas locais do Metabase e do Airflow. Os prints estão separados em `imagens/prints/`:

- [`imagens/openf1-capa.png`](imagens/openf1-capa.png): capa editorial do projeto;
- [`imagens/openf1-arquitetura.png`](imagens/openf1-arquitetura.png): arquitetura visual do pipeline;
- [`imagens/openf1-telemetria.png`](imagens/openf1-telemetria.png): escopo da telemetria individual;
- [`imagens/prints/01-metabase-dashboard-sessao.png`](imagens/prints/01-metabase-dashboard-sessao.png): dashboard real de desempenho;
- [`imagens/prints/02-metabase-dashboard-telemetria.png`](imagens/prints/02-metabase-dashboard-telemetria.png): dashboard real de telemetria;
- [`imagens/prints/03-metabase-consulta-melhor-volta.png`](imagens/prints/03-metabase-consulta-melhor-volta.png): análise de melhor volta;
- [`imagens/prints/04-metabase-consulta-velocidade.png`](imagens/prints/04-metabase-consulta-velocidade.png): análise de velocidade;
- [`imagens/prints/05-metabase-consulta-telemetria-volta.png`](imagens/prints/05-metabase-consulta-telemetria-volta.png): telemetria por volta;
- [`imagens/prints/06-metabase-postgresql-conexao.png`](imagens/prints/06-metabase-postgresql-conexao.png): conexão PostgreSQL real;
- [`imagens/prints/07-metabase-postgresql-tabelas.png`](imagens/prints/07-metabase-postgresql-tabelas.png): tabelas analíticas disponíveis;
- [`imagens/prints/08-metabase-colecao-analises.png`](imagens/prints/08-metabase-colecao-analises.png): coleção de análises;
- [`imagens/prints/09-airflow-inicio.png`](imagens/prints/09-airflow-inicio.png): página inicial do Airflow;
- [`imagens/prints/10-airflow-catalogo-dags.png`](imagens/prints/10-airflow-catalogo-dags.png): catálogo de DAGs;
- [`imagens/prints/11-airflow-grafo-dag.png`](imagens/prints/11-airflow-grafo-dag.png): grafo da DAG;
- [`imagens/prints/12-airflow-execucao-sucesso.png`](imagens/prints/12-airflow-execucao-sucesso.png): execução bem-sucedida;
- [`imagens/prints/13-airflow-tarefas.png`](imagens/prints/13-airflow-tarefas.png): tarefas da DAG;
- [`imagens/prints/14-airflow-codigo-dag.png`](imagens/prints/14-airflow-codigo-dag.png): código carregado da DAG;
- [`imagens/prints/15-airflow-detalhes-dag.png`](imagens/prints/15-airflow-detalhes-dag.png): detalhes operacionais da DAG.

As imagens não são evidência de dados capturados. Os números e regras devem ser conferidos nos Parquets, manifestos, testes e documentação do pipeline.
