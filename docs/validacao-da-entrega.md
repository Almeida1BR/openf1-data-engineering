# Evidências da entrega de 05/09/2026

A validação foi realizada no repositório local, sobre a sessão 9158. Os resultados abaixo descrevem verificações executadas, não apenas configurações adicionadas.

## Pipeline e dados

- Nova ingestão na API: `20260905T170557Z_ebe1cd19`, status success.
- Volume: 1 sessão, 20 pilotos, 475 voltas, 29 rádios e 360.520 amostras.
- Telemetria: 20 arquivos por driver_number, 18.026 amostras por piloto.
- Qualidade: aviso de acelerador acima de 100 preservado; sem duplicidades de chave no snapshot.
- Gold: sete tabelas, incluindo 474 grupos de telemetria por volta.
- Execução direta por Python: aprovada.
- Build e execução pelo container com requirements.lock: aprovados.

## PostgreSQL

As contagens das sete tabelas foram comparadas com o manifesto: 474, 1, 20, 475, 20, 15 e 103 linhas para telemetria por volta, sessão, desempenho por piloto, voltas, telemetria, rádio e DRS, respectivamente.

Duas recargas consecutivas preservaram contagens e chaves primárias. Os segmentos foram conferidos como arrays JSONB. As duas consultas SQL versionadas retornaram 20 pilotos cada.

O teste transacional alterou temporariamente nomes de pilotos na primeira tabela e introduziu uma chave duplicada na última. A carga falhou e o nome anterior permaneceu no banco, comprovando rollback das alterações anteriores à falha. O teste usou cópias temporárias da Gold; os arquivos originais foram preservados.

O papel openf1_leitura possui SELECT e não possui INSERT na tabela de desempenho.

## Airflow

A DAG foi importada sem erros e concluiu duas execuções:

- `manual__2026-09-05T17:07:24.640988+00:00`: success;
- `manual__2026-09-05T17:17:20.388930+00:00`: success.

As tarefas executar e verificar completaram o processamento e a comparação SQL. O serviço foi recriado com a imagem atualizada e o histórico permaneceu no volume.

## Metabase

As 19 consultas retornaram dados: indicadores, análises por piloto e 474 linhas na análise por volta. O bootstrap foi repetido e reutilizou seus IDs. Os dashboards instalados estão em http://localhost:3000/dashboard/2 e http://localhost:3000/dashboard/3.

A inspeção visual confirmou gráficos, indicadores e tabelas em português. O filtro foi alterado para 9160: os cartões exibiram Sem resultados. Ao restaurar o padrão 9158, os dados reapareceram. As 15 capturas reais estão em `docs/imagens/prints/`, cobrindo dashboards, consultas, PostgreSQL, catálogo Airflow, grafo, tarefas, código, detalhes e execução bem-sucedida.

## Testes e ferramentas

A suíte registrou 19 testes aprovados. Compileall, pip check, git diff --check e docker compose config também passaram. As dependências do pipeline foram congeladas em requirements.lock. As credenciais geradas do Metabase estão ignoradas pelo Git.

## Limites da verificação

O workflow GitHub foi criado, mas não executado remotamente, pois não houve publicação nesta etapa. O ambiente foi validado localmente; não houve deploy público, configuração de domínio, backup externo ou alertas enviados a terceiros. Airflow standalone é a topologia de demonstração adotada. As opções para operação externa estão no roadmap.
