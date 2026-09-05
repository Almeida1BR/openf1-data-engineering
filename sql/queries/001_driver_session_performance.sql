SELECT
    session_key,
    driver_number,
    full_name,
    team_name,
    best_lap_duration_s,
    average_lap_duration_s,
    max_speed_kmh,
    average_speed_kmh,
    max_rpm,
    average_rpm,
    average_throttle,
    drs_active_percentage,
    radio_message_count
FROM analytics.driver_session_performance
WHERE session_key = 9158
ORDER BY best_lap_duration_s NULLS LAST, driver_number;
