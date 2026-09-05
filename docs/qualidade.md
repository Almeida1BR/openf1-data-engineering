# Qualidade, lineage e critérios de aceitação

## 1. Objetivo

A qualidade neste projeto verifica se os dados podem ser utilizados sem misturar sessões, pilotos ou chaves. Ela não tenta corrigir qualquer anomalia estatística automaticamente. O princípio é separar erro bloqueante de aviso observável:

- erro bloqueante interrompe a transformação;
- aviso permite a saída, registra o problema e preserva o valor original;
- sucesso indica que o contrato foi atendido sem avisos.

## 2. Implementação

As regras estão em `src/quality/quality.py`. O transformador chama `validate_dataframe` antes e depois da deduplicação e usa `assert_quality` para impedir a gravação de um resultado com erro.

O relatório final fica em:

```text
data/silver/session_key=9158/quality_report.json
```

## 3. Conteúdo do relatório

Cada dataset possui:

| Campo do relatório | Finalidade |
| --- | --- |
| `generated_at` | instante UTC da validação |
| `endpoint` | dataset avaliado |
| `rows` | quantidade de linhas avaliadas |
| `columns` | colunas presentes |
| `missing_columns` | obrigatórias ausentes |
| `unexpected_columns` | colunas não previstas |
| `natural_key` | chave usada na avaliação |
| `null_key_rows` | linhas com parte da chave nula |
| `duplicate_key_rows` | linhas participantes de duplicidade |
| `deduplicated_rows` | linhas efetivamente removidas |
| `session_key_mismatch_rows` | linhas fora da sessão esperada |
| `null_counts` | nulos por coluna |
| `errors` | lista de falhas bloqueantes |
| `warnings` | lista de ressalvas |
| `status` | `success`, `warning` ou `failed` |

## 4. Validações estruturais

### Colunas

Cada endpoint tem conjunto de campos obrigatórios e opcionais. A ausência de obrigatório é erro. Uma coluna nova da API é aviso, permitindo que o pipeline continue enquanto o contrato é atualizado conscientemente.

### Chaves

As chaves naturais são definidas por endpoint:

```text
sessions   = session_key
drivers    = session_key + driver_number
laps       = session_key + driver_number + lap_number
team_radio = session_key + driver_number + recording_url
car_data   = session_key + driver_number + date
```

Linhas com chave nula ou duplicada são sinalizadas. A transformação mantém a última ocorrência de uma chave natural duplicada e registra quantas linhas foram realmente removidas.

### Escopo

Se a execução tem uma sessão selecionada, todos os valores não nulos de `session_key` devem ser iguais ao valor esperado. Essa regra existe tanto na ingestão quanto na transformação para proteger contra resposta de API inesperada e contra arquivos históricos misturados.

## 5. Validações de domínio

| Dataset | Regra | Resultado |
| --- | --- | --- |
| `sessions` | `date_end >= date_start` | erro se violada |
| `laps` | `lap_number > 0` | erro se violada |
| `laps` | duração não positiva | aviso |
| `car_data` | `speed >= 0` | erro se violada |
| `car_data` | `rpm >= 0` | erro se violada |
| `car_data` | `n_gear` entre 0 e 8 | erro se violada |
| `car_data` | `throttle > 100` | aviso, preserva origem |
| `car_data` | código de freio fora de 0, 100 e 104 | aviso, preserva origem |

Os domínios são baseados na documentação da OpenF1 e no comportamento do snapshot. Um aviso não autoriza o dashboard a tratar o dado como normal sem investigação.

## 6. Resultado real do snapshot 9158

A transformação local do conteúdo versionado foi executada com o filtro de sessão. O resultado observado foi:

| Dataset | Entrada | Saída | Status |
| --- | ---: | ---: | --- |
| `sessions` | 1 | 1 | `success` |
| `drivers` | 20 | 20 | `success` |
| `laps` | 475 | 475 | `success` |
| `team_radio` | 29 | 29 | `success` |
| `car_data` | 360.520 | 360.520 | `warning` |

O único aviso foi `throttle` acima de 100 em 102.942 registros. Não houve remoção por duplicidade e não houve mistura de sessões. O valor foi preservado na Silver.

## 7. Lineage

O lineage mínimo possui três campos:

```text
source_file       = arquivo JSON de origem
source_path       = caminho relativo na Bronze
ingestion_run_id  = execução que produziu o JSON
```

Exemplo:

```text
source_file      = data.json
source_path      = run_id=.../car_data/driver_number=1/data.json
ingestion_run_id = 20230915T093000Z_a1b2c3d4
```

Em arquivos legados, `ingestion_run_id` recebe `legacy` e o caminho relativo ainda identifica a origem. Os campos de lineage não formam a chave do negócio.

## 8. Testes automatizados

| Arquivo | Cobertura |
| --- | --- |
| `tests/test_client.py` | parâmetros HTTP, timeout, retry e resposta inválida |
| `tests/test_ingestion.py` | run Bronze, chamadas por piloto e rejeição de piloto incorreto |
| `tests/test_transformation.py` | normalização, filtro de sessão, deduplicação e escolha da run mais recente |
| `tests/test_gold.py` | agregação de volta, telemetria, rádio e DRS |
| `tests/test_loading.py` | carga SQLAlchemy em SQLite e serialização de arrays |

Os testes usam dados falsos pequenos e não dependem de rede. A validação sobre o snapshot real é uma etapa operacional separada.

## 9. Critérios de aceite da pipeline atual

Uma execução da sessão 9158 é considerada funcional quando:

- o manifesto Bronze termina com `status=success`;
- todos os endpoints esperados são restringidos à sessão 9158;
- cada `car_data` possui apenas o `driver_number` requisitado;
- a Silver grava Parquet e relatório de qualidade;
- não existem erros de qualidade;
- avisos permanecem visíveis no relatório;
- a Gold grava as sete tabelas e o manifesto;
- `driver_session_performance` possui uma linha para cada piloto de `drivers`;
- a carga SQLite de teste passa;
- a suíte automatizada passa.

Banco persistente, DAG, dashboard e auditoria local foram integrados. O workflow de CI está preparado no repositório; sua execução remota requer publicação no GitHub. Para operação externa, consulte as decisões de infraestrutura no [`roadmap.md`](roadmap.md).
