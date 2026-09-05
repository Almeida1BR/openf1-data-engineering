# Modelo analítico da camada Gold

![Consulta real de telemetria por volta](imagens/prints/05-metabase-consulta-telemetria-volta.png)

## 1. Objetivo da Gold

A camada Gold transforma os endpoints detalhados em tabelas com granularidade explícita. O leitor deve conseguir responder perguntas de sessão sem repetir a leitura de 360.520 amostras de telemetria sempre que desejar comparar pilotos.

O modelo atual é orientado a uma sessão por execução. Todas as tabelas carregam `session_key`; as tabelas de piloto carregam também `driver_number`. A combinação dos dois campos é o eixo de relacionamento entre dimensão de piloto, voltas, telemetria, rádio e estados de DRS.

## 2. Mapa de granularidades

| Tabela Gold | Uma linha representa | Chave lógica |
| --- | --- | --- |
| `session_summary` | uma sessão | `session_key` |
| `driver_session_performance` | um piloto em uma sessão | `session_key`, `driver_number` |
| `lap_performance` | uma volta de um piloto | `session_key`, `driver_number`, `lap_number` |
| `telemetry_summary` | o resumo de telemetria de um piloto | `session_key`, `driver_number` |
| `radio_summary` | o resumo de rádio de um piloto com mensagens | `session_key`, `driver_number` |
| `drs_state_summary` | um código de DRS observado para um piloto | `session_key`, `driver_number`, `drs` |

## 3. Tabelas

### 3.1 `session_summary`

É o contexto e o controle de volume da execução. Contém os campos da sessão e:

| Campo | Regra |
| --- | --- |
| `driver_count` | quantidade distinta de pilotos no dataset `drivers` |
| `lap_record_count` | quantidade de linhas de `laps` |
| `car_data_record_count` | quantidade de linhas de `car_data` |
| `team_radio_record_count` | quantidade de linhas de `team_radio` |
| `telemetry_driver_count` | quantidade distinta de pilotos com telemetria |
| `generated_at` | instante UTC da construção da Gold |

No snapshot da sessão 9158, a linha de resumo registra 20 pilotos, 475 linhas de volta, 360.520 amostras de telemetria e 29 mensagens de rádio.

### 3.2 `driver_session_performance`

É a tabela principal para uma primeira visão de comparação entre pilotos. Ela começa em `drivers`, garantindo uma linha para todo participante, e recebe agregações de voltas, telemetria e rádio por left join.

Campos de desempenho de volta:

- `lap_count`;
- `complete_lap_count`;
- `pit_out_lap_count`;
- `best_lap_duration_s`;
- `average_lap_duration_s`;
- `best_duration_sector_1_s`, `best_duration_sector_2_s` e `best_duration_sector_3_s`;
- `max_i1_speed_kmh`, `max_i2_speed_kmh` e `max_st_speed_kmh`.

Campos de telemetria:

- `telemetry_sample_count`;
- `telemetry_start` e `telemetry_end`;
- `max_speed_kmh` e `average_speed_kmh`;
- `max_rpm` e `average_rpm`;
- `average_throttle`;
- `brake_pressed_sample_count`;
- `drs_active_sample_count` e `drs_active_percentage`.

Campos de rádio:

- `radio_message_count`;
- `first_radio_at`;
- `last_radio_at`.

### 3.3 `lap_performance`

Mantém uma linha por volta sem descartar arrays de segmentos. A tabela acrescenta:

| Campo | Definição |
| --- | --- |
| `sector_time_sum_s` | soma dos três setores quando os três existem |
| `is_complete_lap` | `lap_duration` e setores disponíveis |
| `driver_best_lap_duration_s` | menor `lap_duration` válido do piloto |
| `delta_to_driver_best_lap_s` | duração da volta menos o melhor tempo do piloto |

Voltas de saída de box continuam na tabela, mas não são usadas para definir o melhor tempo de volta do piloto. O projeto não faz imputação de duração.

### 3.4 `telemetry_summary`

É o mart específico para telemetria. A implementação calcula:

```text
drs_active = drs ∈ {10, 12, 14}
brake_pressed = brake > 0
drs_active_percentage = média(drs_active) × 100
```

Como `drs_active` e `brake_pressed` são derivados de códigos da origem, a Silver mantém o valor original e a Gold oferece os indicadores convenientes para análise.

### 3.5 `radio_summary`

Agrega `recording_url` por piloto. A data mínima e máxima são nulas quando todas as mensagens disponíveis não têm timestamp. Um piloto sem mensagem recebe zero em `driver_session_performance`, mas não precisa criar uma linha artificial em `radio_summary`.

### 3.6 `drs_state_summary`

Conta a quantidade de amostras por código bruto de DRS. Essa tabela não substitui `drs_active_percentage`; ela permite investigar a distribuição de estados e detectar alterações na origem.

## 4. Estratégia de junção

```text
drivers ──────────────┐
                      ├── driver_session_performance
laps ── agregação ────┤
car_data ─ agregação ─┤
team_radio ─ resumo ──┘

laps ─────────────── lap_performance
car_data ────────── telemetry_summary
team_radio ──────── radio_summary
car_data ────────── drs_state_summary
sessions ────────── session_summary e contexto do piloto
```

Os agregados de `laps`, `car_data` e `team_radio` são construídos separadamente e unidos por `session_key` e `driver_number`. Adicionalmente, `telemetry_lap_summary` produz um agregado por volta usando associação temporal delimitada.

Uma amostra pertence à janela `[date_start, fim)`. O fim é o menor valor disponível entre início mais duração e início da próxima volta. Sem ambos os limites finais a amostra não é associada; sem início a volta também não é associada. Não há interpolação nem associação entre pilotos. Os testes verificam os limites exatos e gaps entre janelas. O snapshot produziu 474 grupos; uma volta não possui início válido.

## 5. Perguntas que o modelo responde

### Ritmo

- Qual piloto teve a menor volta válida?
- Qual é a diferença entre a melhor volta e a média de cada piloto?
- Quantas voltas completas cada piloto registrou?

### Telemetria

- Qual foi a maior velocidade observada por piloto?
- Quem possui maior RPM máximo ou médio?
- Qual é a janela temporal de telemetria de cada piloto?
- Qual percentual de amostras possui DRS ativo?
- Quantas amostras registraram freio pressionado?

### DRS e rádio

- Quais códigos de DRS aparecem para cada piloto?
- Quantas amostras existem por estado bruto?
- Quais pilotos têm mensagens de rádio disponíveis?
- Qual é a janela de mensagens de cada piloto?

## 6. Consulta SQL de exemplo

```sql
SELECT
    session_key,
    driver_number,
    full_name,
    team_name,
    best_lap_duration_s,
    max_speed_kmh,
    drs_active_percentage,
    radio_message_count
FROM analytics.driver_session_performance
WHERE session_key = 9158
ORDER BY best_lap_duration_s NULLS LAST, driver_number;
```

O mesmo exemplo está versionado em [`sql/queries/001_driver_session_performance.sql`](../sql/queries/001_driver_session_performance.sql). Para uma leitura apenas de telemetria, use [`sql/queries/002_telemetry_by_driver.sql`](../sql/queries/002_telemetry_by_driver.sql).

## 7. Convenções de medida

| Sufixo ou nome | Unidade |
| --- | --- |
| `*_duration_s` | segundos |
| `*_speed_kmh` | quilômetros por hora |
| `*_rpm` | rotações por minuto |
| `*_throttle` | escala da origem, interpretada como percentual no uso analítico |
| `*_percentage` | percentual de 0 a 100 |
| `*_count` | quantidade de linhas ou eventos |
| `*_at`, `date`, `date_start`, `date_end` | timestamp UTC |

Não se deve comparar `average_throttle` entre fontes diferentes sem antes confirmar se a escala e a semântica do sinal permanecem iguais.

## 8. Limitações analíticas atuais

- a Gold resume o treino, mas não classifica automaticamente stint, pit stop ou composto de pneu;
- `car_data` não é interpolado para uma frequência fixa;
- há agregação por volta, mas não interpolação por setor ou distância percorrida;
- o melhor tempo usa a disponibilidade de `lap_duration`, sem reconstrução a partir dos setores;
- uma alta velocidade máxima não é, sozinha, medida de desempenho global;
- o número de mensagens de rádio depende da cobertura da API;
- os Parquets Gold são regravados em cada construção da partição escolhida.

Esses limites fazem parte do contrato e devem ser expandidos junto com novas métricas, e não escondidos em transformações implícitas.
