# Contrato de dados

## 1. Princípio do contrato

O contrato deste projeto diferencia o que é identificador técnico da OpenF1, o que é metadado do pipeline e o que é métrica derivada. Os nomes dos endpoints e dos campos de origem permanecem em inglês quando são nomes oficiais da API; explicações, comandos e regras estão em português.

O contrato é aplicado por `src/quality/quality.py` durante a transformação. Colunas obrigatórias ausentes e chaves inconsistentes reprovam o dataset. Colunas adicionais não documentadas geram aviso para permitir evolução da API sem perda silenciosa.

## 2. Escopo de referência

```text
session_key = 9158
meeting_key = 1219
year = 2023
circuit_short_name = Singapore
session_type = Practice
session_name = Practice 1
```

O contrato não assume que esses valores serão fixos para outras sessões. Eles servem como exemplo e como validação do snapshot atual.

## 3. Tipos na Silver

| Família | Conversão | Observação |
| --- | --- | --- |
| Chaves | numérico | `session_key`, `meeting_key`, `driver_number` e similares |
| Medidas | numérico | velocidade, RPM, acelerador, freio e duração |
| Datas | timestamp UTC | `date`, `date_start` e `date_end` |
| Texto | string limpa | espaços laterais removidos |
| Booleano | booleano da origem | `is_pit_out_lap` e `is_cancelled` |
| Array | lista preservada | segmentos de setor em `laps` |
| Lineage | texto | `source_file`, `source_path`, `ingestion_run_id` |

Strings vazias, `none` e `null` textuais são convertidas para nulo. Valores numéricos que não podem ser convertidos viram nulo e são avaliados pelas regras de qualidade.

## 4. Chaves naturais

| Endpoint | Chave natural | Motivo |
| --- | --- | --- |
| `sessions` | `session_key` | uma linha de contexto por sessão |
| `drivers` | `session_key`, `driver_number` | um piloto em uma sessão |
| `laps` | `session_key`, `driver_number`, `lap_number` | uma volta numerada de um piloto |
| `team_radio` | `session_key`, `driver_number`, `recording_url` | mensagem identificada pelo áudio disponibilizado |
| `car_data` | `session_key`, `driver_number`, `date` | amostra do carro em um instante |

O campo `date` de `team_radio` é opcional porque pode estar ausente na origem. Ele não participa da chave natural. O projeto não usa o nome do arquivo como chave.

## 5. Endpoint `sessions`

### Granularidade

Uma linha descreve uma sessão de um evento. A API também pode retornar catálogo de calendário; o filtro aplicado pelo pipeline reduz a resposta à sessão solicitada.

### Campos

| Campo | Tipo esperado | Obrigatório | Descrição |
| --- | --- | --- | --- |
| `session_key` | inteiro | sim | identificador da sessão |
| `session_type` | texto | sim | tipo, como `Practice`, `Qualifying` ou `Race` |
| `session_name` | texto | sim | nome da sessão |
| `date_start` | timestamp | sim | início da sessão |
| `date_end` | timestamp | sim | fim da sessão |
| `meeting_key` | inteiro | sim | identificador do evento |
| `circuit_key` | inteiro | sim | identificador do circuito |
| `circuit_short_name` | texto | sim | nome curto do circuito |
| `country_key` | inteiro | sim | identificador do país |
| `country_code` | texto | sim | código do país |
| `country_name` | texto | sim | nome do país |
| `location` | texto | sim | local do circuito |
| `gmt_offset` | texto | sim | deslocamento GMT informado pela origem |
| `year` | inteiro | sim | ano do evento |
| `is_cancelled` | booleano | sim | indicação de cancelamento |

`date_end` anterior a `date_start` reprova a qualidade.

## 6. Endpoint `drivers`

### Granularidade

Uma linha representa a participação de um piloto na sessão. A resposta deste endpoint é a dimensão usada para descobrir os pilotos que receberão chamadas individuais de `car_data`.

| Campo | Tipo esperado | Obrigatório | Descrição |
| --- | --- | --- | --- |
| `meeting_key` | inteiro | sim | evento |
| `session_key` | inteiro | sim | sessão |
| `driver_number` | inteiro | sim | número oficial do piloto na sessão |
| `full_name` | texto | sim | nome de exibição |
| `name_acronym` | texto | sim | abreviação de três letras |
| `team_name` | texto | sim | equipe na sessão |
| `last_name` | texto | sim | sobrenome usado no nome legado do arquivo |
| `broadcast_name` | texto | não | nome para transmissão |
| `team_colour` | texto | não | cor de exibição da equipe |
| `first_name` | texto | não | primeiro nome |
| `headshot_url` | texto | não | URL de imagem |
| `country_code` | texto | não | código de país |

O pipeline usa `driver_number` como identidade técnica. O sobrenome é apenas um atributo descritivo.

## 7. Endpoint `laps`

### Granularidade

Uma linha é uma volta de um piloto. O endpoint pode conter voltas incompletas, voltas de saída de box e setores nulos.

| Campo | Tipo esperado | Obrigatório | Descrição |
| --- | --- | --- | --- |
| `meeting_key` | inteiro | sim | evento |
| `session_key` | inteiro | sim | sessão |
| `driver_number` | inteiro | sim | piloto |
| `lap_number` | inteiro | sim | número da volta |
| `date_start` | timestamp | sim | início da volta quando disponível |
| `lap_duration` | decimal | sim | duração total em segundos quando disponível |
| `is_pit_out_lap` | booleano | sim | volta de saída de box |
| `duration_sector_1` | decimal | não | duração do setor 1 |
| `duration_sector_2` | decimal | não | duração do setor 2 |
| `duration_sector_3` | decimal | não | duração do setor 3 |
| `i1_speed` | decimal | não | velocidade no primeiro intermediário |
| `i2_speed` | decimal | não | velocidade no segundo intermediário |
| `st_speed` | decimal | não | velocidade na linha de chegada |
| `segments_sector_1` | lista de inteiros | não | segmentos do setor 1 |
| `segments_sector_2` | lista de inteiros | não | segmentos do setor 2 |
| `segments_sector_3` | lista de inteiros | não | segmentos do setor 3 |

Os arrays de segmentos são preservados como listas no Parquet. No PostgreSQL são inseridos como `JSONB`; valores ausentes em arrays são normalizados para `null`, pois `NaN` não pertence ao padrão JSON. O teste em SQLite utiliza JSON textual.

## 8. Endpoint `team_radio`

### Granularidade

Uma linha representa uma gravação de rádio disponibilizada para um piloto em uma sessão. A cobertura não é necessariamente completa para todos os pilotos.

| Campo | Tipo esperado | Obrigatório | Descrição |
| --- | --- | --- | --- |
| `meeting_key` | inteiro | sim | evento |
| `session_key` | inteiro | sim | sessão |
| `driver_number` | inteiro | sim | piloto |
| `recording_url` | texto | sim | endereço da gravação |
| `date` | timestamp | não | instante da mensagem |

`radio_summary` agrega apenas as mensagens disponíveis. A ausência de registro não deve ser convertida em uma afirmação de ausência de comunicação.

## 9. Endpoint `car_data`

### Granularidade

Uma linha é uma amostra de telemetria do carro de um piloto em um instante. O contrato central do projeto é:

```text
uma amostra = session_key + driver_number + date
```

Para a sessão 9158, o snapshot possui 20 pilotos e 360.520 amostras. A distribuição observada é de 18.026 amostras por piloto.

### Campos

| Campo | Tipo esperado | Obrigatório | Descrição |
| --- | --- | --- | --- |
| `date` | timestamp UTC | sim | instante da amostra |
| `meeting_key` | inteiro | sim | evento |
| `session_key` | inteiro | sim | sessão |
| `driver_number` | inteiro | sim | piloto que gerou a amostra |
| `speed` | decimal | sim | velocidade em km/h |
| `n_gear` | inteiro | sim | marcha observada |
| `drs` | inteiro | sim | código do estado do DRS |
| `throttle` | decimal | sim | percentual/código de acelerador da origem |
| `brake` | decimal | sim | valor/código de freio da origem |
| `rpm` | decimal | sim | rotações por minuto |

### Regras específicas

- `speed` não pode ser negativa;
- `rpm` não pode ser negativo;
- `n_gear` deve estar entre 0 e 8;
- códigos de freio diferentes de `0`, `100` e `104` geram aviso, mas são preservados;
- `throttle` acima de 100 gera aviso, mas não é truncado;
- a Gold considera os estados `10`, `12` e `14` de `drs` como ativos;
- o `driver_number` da resposta deve ser o mesmo usado na requisição.

O aviso de acelerador acima de 100 existe porque o snapshot real apresenta 102.942 ocorrências. Essa anomalia é observada e documentada, não apagada por uma regra de limpeza destrutiva.

## 10. Colunas de lineage

| Campo | Origem | Uso |
| --- | --- | --- |
| `source_file` | nome do JSON | localizar o arquivo de origem |
| `source_path` | caminho relativo à Bronze | distinguir arquivos com mesmo nome |
| `ingestion_run_id` | diretório `run_id=*` | ligar o registro à execução |

Essas colunas não participam das chaves naturais e não são obrigatórias na resposta original.

## 11. Política de nulos

Nulos podem existir em medidas que a OpenF1 não conseguiu disponibilizar. O pipeline não preenche medidas com zero automaticamente. Na Gold:

- contagens são preenchidas com zero quando o piloto não tem registros naquele dataset;
- médias, máximos e timestamps permanecem nulos quando não existe observação;
- arrays de setor permanecem nulos quando a volta não possui o detalhamento;
- um piloto sem rádio não aparece em `radio_summary`, mas permanece em `driver_session_performance` com `radio_message_count=0`.

Essa distinção evita confundir “não observado” com “observado e igual a zero”.
