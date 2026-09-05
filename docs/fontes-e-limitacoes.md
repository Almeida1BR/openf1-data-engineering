# Fontes, cobertura e limitações

## 1. Fontes consultadas

O desenvolvimento foi conferido contra:

- [documentação oficial da OpenF1](https://openf1.org/docs/);
- [página oficial da OpenF1](https://openf1.org/);
- [repositório do projeto no GitHub](https://github.com/Almeida1BR/openf1-data-engineering);
- arquivos locais versionados em `data/bronze`.

Os nomes de endpoint e campo citados neste documento devem ser conferidos na documentação oficial quando uma nova temporada ou versão da API for incorporada.

## 2. O que a OpenF1 oferece ao projeto

A OpenF1 expõe endpoints HTTP que retornam dados em JSON e podem ser filtrados por parâmetros. O projeto usa cinco deles:

| Endpoint | Papel no projeto |
| --- | --- |
| `sessions` | contexto de sessão e circuito |
| `drivers` | participantes e descoberta de `driver_number` |
| `laps` | tempos, setores e velocidades por volta |
| `team_radio` | mensagens de rádio disponíveis |
| `car_data` | telemetria do carro por piloto e instante |

A documentação pública indica que o histórico começa em 2023 e pode ser consultado sem autenticação, enquanto o acesso em tempo real possui condições diferentes. O pipeline, portanto, trata a API como fonte externa sujeita a disponibilidade, limites e mudança de cobertura.

## 3. `car_data` e a interpretação correta

O endpoint `car_data` é o centro do projeto. Cada registro representa sinais do carro associados a um piloto e a um instante. A documentação informa frequência aproximada de 3,7 Hz e campos como velocidade, marcha, DRS, acelerador, freio e RPM.

O projeto interpreta a chave operacional assim:

```text
car_data(session_key=9158, driver_number=1)
```

não assim:

```text
car_data(evento inteiro sem separação por piloto)
```

O código primeiro consulta `drivers?session_key=9158`. Depois, para cada `driver_number`, consulta `car_data?session_key=9158&driver_number=N`. Essa regra é testada em `tests/test_ingestion.py` e validada novamente quando a resposta chega.

## 4. Campos e semântica relevante

### `speed`

É tratada como km/h. Valores negativos são considerados erro. A Gold fornece máximo e média por piloto, mas uma máxima isolada não mede o desempenho completo.

### `rpm`

É tratada como rotação por minuto. Valores negativos são considerados erro. A Gold calcula máximo e média.

### `n_gear`

É a marcha do carro. A validação aceita 0 a 8. O zero pode representar condição sem marcha engatada ou estado equivalente da origem; a interpretação exata deve continuar vinculada à documentação.

### `throttle`

É preservado numericamente. O snapshot apresenta valores acima de 100; a transformação gera aviso e não aplica truncamento. Isso evita esconder uma diferença entre a descrição esperada e a resposta observada.

### `brake`

É preservado como código da origem. A documentação descreve principalmente 0 e 100; o snapshot também apresenta 104. A validação alerta para códigos fora de 0, 100 e 104. A Gold utiliza `brake > 0` apenas para criar a contagem de amostras com freio.

### `drs`

É preservado como estado inteiro. A documentação descreve estados intermediários, e a Gold define `10`, `12` e `14` como estados ativos. `drs_state_summary` mantém a distribuição bruta para permitir revisão dessa regra.

## 5. Cobertura por endpoint

Os endpoints não possuem a mesma cobertura:

- `drivers` descreve os participantes da sessão;
- `car_data` pode possuir telemetria de todos ou de parte dos pilotos;
- `laps` pode conter voltas incompletas, setores ausentes e horários nulos;
- `team_radio` tem disponibilidade limitada e não deve ser usado como dimensão completa de pilotos;
- `sessions` pode servir como catálogo maior, por isso o filtro por `session_key` é indispensável.

No snapshot 9158, todos os 20 pilotos têm `car_data`, enquanto somente 15 aparecem no resumo de rádio.

## 6. Datas e fuso horário

A Silver converte `date`, `date_start` e `date_end` para timestamp UTC com Pandas. A sessão 9158 aparece na origem como 15 de setembro de 2023, das 09:30 às 10:30 UTC, com deslocamento de circuito informado separadamente.

Não se deve converter o timestamp para horário local durante a ingestão. A camada analítica pode criar uma apresentação local em uma etapa posterior, mantendo o instante UTC como referência.

## 7. Limites de requisição

A página pública da OpenF1 informa limites por segundo e por minuto. O padrão `OPENF1_MIN_REQUEST_INTERVAL=2.1` mantém um cliente sequencial abaixo de 30 chamadas por minuto. Instâncias independentes compartilham o limite externo e devem ser coordenadas. O cliente respeita intervalos e repete falhas transitórias; a ingestão completa usa uma chamada por piloto para `car_data`.

O número de chamadas pode crescer com retries. Por isso, o cliente também trata `429` e respeita `Retry-After` quando presente. A ingestão não deve ser paralelizada sem uma política explícita de limite.

## 8. Fonte não oficial e uso responsável

A OpenF1 é uma fonte comunitária não oficial. O projeto não deve:

- afirmar que os dados são um feed oficial da Fórmula 1;
- inferir que ausência de dado equivale a ausência do fenômeno;
- atribuir uma métrica derivada como se fosse um campo original;
- remover warnings de qualidade para melhorar um dashboard;
- redistribuir gravações de rádio ignorando os termos da fonte.

Os Parquets Gold devem ser acompanhados do manifesto e da referência à fonte para que o consumidor conheça a procedência.

## 9. Mudanças futuras da API

A documentação registra campos cuja situação pode mudar, incluindo `country_code` em alguns contextos. O projeto não usa esse campo como chave. Se a OpenF1 retirar, renomear ou alterar a semântica de um campo:

1. atualize `ENDPOINT_SCHEMAS`;
2. revise a conversão em `transform.py`;
3. ajuste a Gold se a métrica depender do campo;
4. atualize o contrato e o roadmap;
5. adicione teste de regressão;
6. execute uma amostra real e compare o manifesto.

## 10. Limitações que permanecem no projeto

- não há garantia de atualização em tempo real;
- não há versionamento externo do conteúdo da API além do `run_id` local;
- os checksums SHA-256 cobrem os artefatos Gold; não se arquivam cabeçalhos HTTP completos;
- a associação temporal não interpola amostras nem inventa limites ausentes;
- não há correção automática de outliers;
- não há monitoramento remoto de disponibilidade;
- o carregador SQL exige snapshots completos e substitui apenas a sessão;
- o dashboard e a DAG locais estão disponíveis; publicação externa ainda depende da infraestrutura escolhida;
- a imagem gerada por IA é material editorial, não evidência do conteúdo da API.

## 11. Como citar a procedência

Uma análise deve informar, no mínimo:

```text
Fonte: OpenF1 API
Sessão: session_key=9158
Endpoint: car_data
Granularidade: driver_number + date
Camada: Gold telemetry_summary
Execução: run_id ou manifesto correspondente
```
