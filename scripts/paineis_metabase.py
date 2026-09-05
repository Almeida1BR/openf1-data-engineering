PERFORMANCE = "analytics.driver_session_performance"
FILTER = "session_key = {{sessao}} [[AND driver_number = {{piloto}}]]"


def card(name, display, query, position, description, settings=None):
    return {
        "name": name, "display": display, "query": query,
        "position": position, "description": description,
        "settings": settings or {},
    }


def definitions():
    red = {"graph.colors": ["#E10600"], "graph.show_values": True}
    blue = {"graph.colors": ["#00A6D6"]}
    performance = [
        card("Melhor volta por piloto", "bar", f"SELECT name_acronym AS piloto, best_lap_duration_s AS segundos FROM {PERFORMANCE} WHERE {FILTER} ORDER BY segundos NULLS LAST", [0, 4, 12, 8], "Menor volta completa, excluindo saídas de box. Unidade: segundos.", red),
        card("Velocidade máxima por piloto", "bar", f"SELECT name_acronym AS piloto, max_speed_kmh AS velocidade_kmh FROM {PERFORMANCE} WHERE {FILTER} ORDER BY velocidade_kmh DESC", [12, 4, 12, 8], "Máximo observado em toda a sessão; não é necessariamente da melhor volta.", blue),
        card("DRS ativo por piloto (%)", "bar", f"SELECT name_acronym AS piloto, drs_active_percentage AS percentual FROM {PERFORMANCE} WHERE {FILTER} ORDER BY percentual DESC", [0, 20, 12, 8], "Percentual de amostras nos estados 10, 12 e 14; não mede tempo contínuo exato.", blue),
        card("Voltas e cobertura de telemetria", "table", f"SELECT full_name AS piloto, team_name AS equipe, lap_count AS voltas, complete_lap_count AS voltas_completas, telemetry_sample_count AS amostras, radio_message_count AS radios FROM {PERFORMANCE} WHERE {FILTER} ORDER BY piloto", [0, 28, 24, 9], "Cobertura por participante. Rádio ausente não significa ausência do piloto."),
        card("Telemetria por volta", "table", f"SELECT driver_number AS piloto, lap_number AS volta, sample_count AS amostras, max_speed_kmh AS velocidade_maxima_kmh, round(average_rpm::numeric, 0) AS rpm_medio FROM analytics.telemetry_lap_summary WHERE {FILTER} ORDER BY piloto, volta", [0, 24, 24, 9], "Amostras associadas ao intervalo da volta, sem interpolação."),
        card("Pilotos no recorte", "scalar", f"SELECT count(*) AS pilotos FROM {PERFORMANCE} WHERE {FILTER}", [0, 0, 6, 4], "Participantes após aplicar os filtros."),
        card("Amostras de telemetria", "scalar", f"SELECT coalesce(sum(telemetry_sample_count), 0) AS amostras FROM {PERFORMANCE} WHERE {FILTER}", [6, 0, 6, 4], "Quantidade de registros car_data; a granularidade é piloto e instante."),
        card("Melhor volta do recorte (s)", "scalar", f"SELECT min(best_lap_duration_s) AS segundos FROM {PERFORMANCE} WHERE {FILTER}", [12, 0, 6, 4], "Menor volta completa entre os pilotos selecionados.", {"scalar.decimals": 3}),
        card("Voltas registradas", "scalar", f"SELECT coalesce(sum(lap_count), 0) AS voltas FROM {PERFORMANCE} WHERE {FILTER}", [18, 0, 6, 4], "Inclui voltas incompletas e de saída de box."),
        card("Diferença para a melhor volta da sessão", "bar", f"SELECT name_acronym AS piloto, round((best_lap_duration_s - (SELECT min(best_lap_duration_s) FROM {PERFORMANCE} WHERE session_key = {{{{sessao}}}}))::numeric, 3) AS diferenca_s FROM {PERFORMANCE} WHERE {FILTER} ORDER BY diferenca_s NULLS LAST", [0, 12, 12, 8], "Referência: melhor volta de toda a sessão, mesmo quando um piloto é filtrado.", red),
        card("Voltas completas por piloto (%)", "bar", f"SELECT name_acronym AS piloto, round(100.0 * complete_lap_count / nullif(lap_count, 0), 1) AS percentual FROM {PERFORMANCE} WHERE {FILTER} ORDER BY percentual DESC", [12, 12, 12, 8], "Cobertura dos campos de duração e setores disponíveis. Não classifica infrações esportivas.", blue),
        card("Mensagens de rádio disponíveis", "bar", f"SELECT name_acronym AS piloto, radio_message_count AS mensagens FROM {PERFORMANCE} WHERE {FILTER} ORDER BY mensagens DESC, piloto", [12, 20, 12, 8], "Cobertura parcial da OpenF1: zero indica ausência de gravação disponível.", red),
        card("Acelerador médio por piloto", "bar", f"SELECT name_acronym AS piloto, round(average_throttle::numeric, 2) AS acelerador_medio FROM {PERFORMANCE} WHERE {FILTER} ORDER BY acelerador_medio DESC", [0, 36, 12, 8], "Média das amostras de acelerador na escala da origem; valores acima de 100 são preservados.", blue),
    ]
    telemetry = [
        card("Velocidade máxima ao longo das voltas", "line", f"SELECT lap_number AS volta, driver_number::text AS piloto, max_speed_kmh AS velocidade_kmh FROM analytics.telemetry_lap_summary WHERE {FILTER} ORDER BY volta, piloto", [0, 0, 12, 8], "Evolução por volta; use o filtro Piloto para análise individual.", blue),
        card("RPM médio ao longo das voltas", "line", f"SELECT lap_number AS volta, driver_number::text AS piloto, average_rpm AS rpm FROM analytics.telemetry_lap_summary WHERE {FILTER} ORDER BY volta, piloto", [12, 0, 12, 8], "Média das amostras da janela, incluindo trechos lentos e box.", red),
        card("Tempo por volta completa", "line", f"SELECT lap_number AS volta, driver_number::text AS piloto, lap_duration AS segundos FROM analytics.lap_performance WHERE {FILTER} AND is_complete_lap AND NOT is_pit_out_lap ORDER BY volta, piloto", [0, 8, 12, 8], "Exclui saída de box e voltas com dados incompletos; não elimina in-laps.", red),
        card("Amostras associadas por volta", "bar", f"SELECT lap_number AS volta, driver_number::text AS piloto, sample_count AS amostras FROM analytics.telemetry_lap_summary WHERE {FILTER} ORDER BY volta, piloto", [12, 8, 12, 8], "Mais amostras podem refletir uma volta mais longa, não maior frequência do sinal.", blue),
        card("Estados brutos do DRS", "bar", f"SELECT drs::text AS estado_drs, sum(sample_count) AS amostras FROM analytics.drs_state_summary WHERE {FILTER} GROUP BY drs ORDER BY drs", [0, 16, 12, 8], "Preserva os códigos da origem. Estados ativos: 10, 12 e 14.", red),
        card("Janela e cobertura por piloto", "table", f"SELECT name_acronym AS piloto, telemetry_start AS inicio_utc, telemetry_end AS fim_utc, round(average_throttle::numeric, 2) AS acelerador_medio, round(100.0 * brake_pressed_sample_count / nullif(telemetry_sample_count, 0), 2) AS amostras_com_freio_pct FROM {PERFORMANCE} WHERE {FILTER} ORDER BY piloto", [12, 16, 12, 8], "Acelerador na escala da origem, com valores acima de 100 preservados. Freio é percentual de amostras, não de tempo."),
    ]
    return performance + telemetry


def dashboards():
    return [
        {"key": "dashboard_id", "name": "OpenF1 — Visão da sessão", "cards": [5, 6, 7, 8, 0, 1, 9, 10, 2, 11, 3, 12], "driver": None,
         "description": "Visão de desempenho e cobertura. Sessão 9158: TL1 de Singapura, 15/09/2023. DRS e freio são proporções de amostras. Rádio tem cobertura parcial."},
        {"key": "telemetry_dashboard_id", "name": "OpenF1 — Telemetria e voltas", "cards": [13, 14, 15, 16, 17, 18, 4], "driver": "1",
         "description": "Análise por piloto e volta. Padrão: piloto 1, sessão 9158. Janelas com início inclusivo e fim exclusivo, sem interpolação. Valores de acelerador acima de 100 são preservados."},
    ]
