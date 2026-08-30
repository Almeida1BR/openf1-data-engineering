import json
from pathlib import Path

import pandas as pd


BRONZE_PATH = Path("data/bronze")
SILVER_PATH = Path("data/silver")

SILVER_PATH.mkdir(parents=True, exist_ok=True)


DATETIME_COLUMNS = {
    "date",
    "date_start",
    "date_end",
}


NUMERIC_COLUMNS = {
    "meeting_key",
    "session_key",
    "driver_number",
    "speed",
    "rpm",
    "n_gear",
    "throttle",
    "brake",
    "drs",
    "lap_number",
    "lap_duration",
    "duration_sector_1",
    "duration_sector_2",
    "duration_sector_3",
    "i1_speed",
    "i2_speed",
    "st_speed",
    "year",
}


def read_json_file(file_path):
    with open(file_path, "r", encoding="utf-8") as arquivo:
        data = json.load(arquivo)

    if not data:
        return pd.DataFrame()

    if isinstance(data, list):
        df = pd.json_normalize(data)

    elif isinstance(data, dict):
        df = pd.json_normalize([data])

    else:
        return pd.DataFrame()

    df["source_file"] = file_path.name

    return df


def read_endpoint(endpoint_path):
    dataframes = []

    json_files = sorted(endpoint_path.glob("*.json"))

    for file_path in json_files:
        print(f"Lendo: {file_path.name}")

        try:
            df = read_json_file(file_path)

            if not df.empty:
                dataframes.append(df)

        except (json.JSONDecodeError, OSError) as error:
            print(f"Erro ao ler {file_path.name}: {error}")

    if not dataframes:
        return pd.DataFrame()

    return pd.concat(
        dataframes,
        ignore_index=True
    )


def normalize_columns(df):
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace(".", "_", regex=False)
    )

    return df


def clean_strings(df):
    string_columns = df.select_dtypes(
        include=["object", "string"]
    ).columns

    for column in string_columns:
        df[column] = df[column].apply(
            lambda value:
                value.strip()
                if isinstance(value, str)
                else value
        )

        df[column] = df[column].replace(
            {
                "": pd.NA,
                "None": pd.NA,
                "null": pd.NA
            }
        )

    return df


def convert_datetime_columns(df):
    for column in DATETIME_COLUMNS:
        if column in df.columns:
            df[column] = pd.to_datetime(
                df[column],
                errors="coerce",
                utc=True
            )

    return df


def convert_numeric_columns(df):
    for column in NUMERIC_COLUMNS:
        if column in df.columns:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce"
            )

    return df


def remove_duplicates(df):
    comparison_columns = []

    for column in df.columns:
        if column == "source_file":
            continue

        has_unhashable = df[column].apply(
            lambda value: isinstance(
                value,
                (list, dict)
            )
        ).any()

        if not has_unhashable:
            comparison_columns.append(column)

    if comparison_columns:
        df = df.drop_duplicates(
            subset=comparison_columns
        )

    return df


def transform_dataframe(df):
    if df.empty:
        return df

    df = normalize_columns(df)

    df = clean_strings(df)

    df = convert_datetime_columns(df)

    df = convert_numeric_columns(df)

    df = remove_duplicates(df)

    df = df.reset_index(drop=True)

    return df


def save_silver(endpoint, df):
    endpoint_path = SILVER_PATH / endpoint

    endpoint_path.mkdir(
        parents=True,
        exist_ok=True
    )

    file_path = endpoint_path / f"{endpoint}.parquet"

    df.to_parquet(
        file_path,
        engine="pyarrow",
        index=False
    )

    print(f"Silver salva em: {file_path}")


def transform_endpoint(endpoint_path):
    endpoint = endpoint_path.name

    print()
    print("=" * 60)
    print(f"Transformando endpoint: {endpoint}")
    print("=" * 60)

    df = read_endpoint(endpoint_path)

    if df.empty:
        print(f"Nenhum dado encontrado para {endpoint}.")
        return

    bronze_rows = len(df)

    print(
        f"Registros encontrados na Bronze: "
        f"{bronze_rows:,}"
    )

    df = transform_dataframe(df)

    silver_rows = len(df)

    print(
        f"Registros após transformação: "
        f"{silver_rows:,}"
    )

    print(
        f"Duplicatas removidas: "
        f"{bronze_rows - silver_rows:,}"
    )

    print(
        f"Quantidade de colunas: "
        f"{len(df.columns)}"
    )

    save_silver(
        endpoint,
        df
    )


def main():
    print()
    print("Iniciando transformação Bronze -> Silver")

    if not BRONZE_PATH.exists():
        print(
            f"Pasta Bronze não encontrada: "
            f"{BRONZE_PATH}"
        )
        return

    endpoint_paths = sorted(
        path
        for path in BRONZE_PATH.iterdir()
        if path.is_dir()
    )

    if not endpoint_paths:
        print(
            "Nenhum endpoint encontrado "
            "na camada Bronze."
        )
        return

    print(
        f"Endpoints encontrados: "
        f"{len(endpoint_paths)}"
    )

    for endpoint_path in endpoint_paths:
        transform_endpoint(
            endpoint_path
        )

    print()
    print("=" * 60)
    print("Transformação concluída.")
    print("=" * 60)


if __name__ == "__main__":
    main()