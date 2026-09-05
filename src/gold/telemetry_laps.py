import pandas as pd


def telemetry_by_lap(car_data, laps):
    results = []
    for (session, driver), samples in car_data.groupby(["session_key", "driver_number"]):
        windows = laps[laps.session_key.eq(session) & laps.driver_number.eq(driver)].copy()
        windows["date_start"] = pd.to_datetime(windows.date_start, utc=True)
        windows = windows.dropna(subset=["date_start"]).sort_values("date_start")
        windows["window_end"] = windows.date_start + pd.to_timedelta(windows.lap_duration, unit="s")
        next_start = windows.date_start.shift(-1)
        windows["window_end"] = pd.concat([windows.window_end, next_start], axis=1).min(axis=1)
        samples = samples.copy()
        samples["date"] = pd.to_datetime(samples.date, utc=True)
        joined = pd.merge_asof(
            samples.sort_values("date"),
            windows[["date_start", "window_end", "lap_number"]],
            left_on="date", right_on="date_start", direction="backward",
        )
        joined = joined[joined.date.lt(joined.window_end) & joined.lap_number.notna()]
        joined["lap_number"] = joined.lap_number.astype("int64")
        grouped = joined.groupby(["session_key", "driver_number", "lap_number"], as_index=False).agg(
            sample_count=("date", "size"),
            max_speed_kmh=("speed", "max"),
            average_speed_kmh=("speed", "mean"),
            average_rpm=("rpm", "mean"),
            telemetry_start=("date", "min"),
            telemetry_end=("date", "max"),
        )
        results.append(grouped)
    if results:
        return pd.concat(results, ignore_index=True)
    return pd.DataFrame(columns=[
        "session_key", "driver_number", "lap_number", "sample_count", "max_speed_kmh",
        "average_speed_kmh", "average_rpm", "telemetry_start", "telemetry_end",
    ])
