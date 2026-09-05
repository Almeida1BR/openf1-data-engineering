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

As imagens raster foram geradas para este projeto com tema visual de Fórmula 1 e são usadas como material editorial:

- [`imagens/openf1-capa.png`](imagens/openf1-capa.png): capa do README;
- [`imagens/openf1-arquitetura.png`](imagens/openf1-arquitetura.png): fluxo visual das camadas;
- [`imagens/openf1-telemetria.png`](imagens/openf1-telemetria.png): telemetria individual por piloto;
- [`imagens/metabase-dashboard.png`](imagens/metabase-dashboard.png): captura real do painel.
- [`imagens/metabase-telemetria.png`](imagens/metabase-telemetria.png): captura real do painel de telemetria e voltas.

As imagens não são evidência de dados capturados. Os números e regras devem ser conferidos nos Parquets, manifestos, testes e documentação do pipeline.
