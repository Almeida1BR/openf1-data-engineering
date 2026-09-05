SELECT
    session_key,
    driver_number,
    telemetry_sample_count,
    telemetry_start,
    telemetry_end,
    max_speed_kmh,
    average_speed_kmh,
    max_rpm,
    average_rpm,
    average_throttle,
    brake_pressed_sample_count,
    drs_active_sample_count,
    drs_active_percentage
FROM analytics.telemetry_summary
WHERE session_key = 9158
ORDER BY max_speed_kmh DESC NULLS LAST, driver_number;
