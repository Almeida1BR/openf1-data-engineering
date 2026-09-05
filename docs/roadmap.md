# Roadmap e definição de entrega

## Escopo concluído

A versão local integrada cobre uma sessão OpenF1 desde a coleta até o consumo no Metabase, com execução pelo Airflow. O recorte validado é a sessão 9158, treino livre 1 de Singapura em 15/09/2023. Cada amostra de car_data pertence a um piloto e instante dessa sessão.

| Frente | Implementação | Evidência de aceite |
| --- | --- | --- |
| Coleta | HTTP, retry, intervalo 2,1 s, manifestos | nova coleta completa em 05/09/2026 |
| Telemetria | uma chamada por piloto | 20 pilotos, 360.520 amostras |
| Silver | tipos, filtro, chaves, lineage, qualidade | cinco datasets processados |
| Gold | sete tabelas | inclui 474 grupos de telemetria por volta |
| PostgreSQL | DDL, JSONB, transação por sessão | duas recargas, contagens e chaves conferidas |
| Recuperação | exclusão restrita à sessão | teste preserva outra sessão |
| Orquestração | Airflow 3.3.1, executar e verificar | DAG concluída com sucesso |
| BI | Metabase 0.63.16, dois dashboards e 19 análises | consultas executadas e filtros inspecionados |
| Observabilidade | catálogo JSON de execuções | status, duração, linhas, bytes e SHA-256 |
| Contrato | testes de chaves, datas e domínio | suíte automatizada |
| Reprodutibilidade | Dockerfile e requirements.lock | ambiente reproduzível |
| CI | workflow com PostgreSQL 17 | preparado para execução após publicação |
| Documentação | arquitetura, operação e fontes | português e imagens PNG |

## Definição de pronto

A entrega local é aceita quando uma coleta ou Bronze existente gera Silver, Gold e PostgreSQL, o Metabase consulta o banco, a DAG executa e suas contagens batem. Avisos de origem permanecem visíveis. Ausência de rádio não elimina piloto; acelerador acima de 100 continua um aviso explícito.

O ambiente está vinculado ao localhost. Credenciais de banco são de demonstração e as contas administrativas dos aplicativos usam senhas geradas. Publicação em servidor, domínio, orçamento e destinatários de alertas dependem do uso operacional escolhido.

## Publicação no GitHub

As alterações estão preparadas localmente. O workflow passa a rodar após commit e push. Proteção de branch exige configurar o status obrigatório no GitHub. A existência do YAML não equivale a uma execução remota verde.

## Evoluções para operação externa

1. Escolher servidor ou serviço gerenciado, dimensionamento, domínio, TLS e autenticação.
2. Substituir credenciais locais por segredos gerenciados e separar permissões de migração, ingestão e BI.
3. Migrar Airflow standalone para serviços separados e metadados PostgreSQL.
4. Configurar backups de PostgreSQL, Metabase, Airflow e Bronze e testar restauração.
5. Definir retenção, custo máximo, janela de execução e responsáveis por incidentes.
6. Definir destinatários de alertas e limites de duração, cobertura e atualização.
7. Validar concorrência entre máquinas e publicação atômica de partições.

## Evoluções analíticas opcionais

- stints para compostos e estratégia de pneus;
- pit para paradas;
- weather para contexto ambiental;
- location para comparação espacial;
- alinhamento por distância e setores com tolerâncias explícitas;
- comparação entre sessões e temporadas já carregadas;
- associação de rádio com eventos de pista.

Cada endpoint adicional deve possuir contrato, chave, regras de qualidade e pergunta analítica. A quantidade de softwares instalados não é critério de aceite: cada componente deve ter uma função demonstrável.

## Limites conhecidos

A DAG atual tem duas tarefas: execução do pipeline e verificação SQL. Retries reprocessam a sessão inteira de forma idempotente no banco. Decompor por endpoint e mapear dinamicamente pilotos é uma melhoria de eficiência futura. O intervalo HTTP controla um cliente sequencial; múltiplos clientes precisam de coordenação externa.

Bronze é retida integralmente; Silver e Gold são substituídas por sessão. A auditoria guarda hashes da Gold, não cópias históricas de todos os Parquets. O DDL define tabelas versionadas; alterações futuras de colunas exigem migrações SQL explícitas.

Consulte [serviços e entrega](servicos-e-entrega.md) para acesso, credenciais locais, reprodução e validação.
