import requests
from pathlib import Path
import json

BRONZE_PATH = Path("data/bronze")
BRONZE_PATH.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://api.openf1.org/v1"

SESSION_KEY = 9158


def save_bronze(endpoint, data, file_name):
    endpoint_path = BRONZE_PATH / endpoint
    endpoint_path.mkdir(parents=True, exist_ok=True)

    file_path = endpoint_path / file_name

    with open(file_path, "w", encoding="utf-8") as arquivo:
        json.dump(
            data,
            arquivo,
            ensure_ascii=False,
            indent=4
        )

response = requests.get(
    f"{BASE_URL}/drivers",
    params={
        "session_key": SESSION_KEY
    }
)

response.raise_for_status()

drivers = response.json()

for driver in drivers:

    driver_number = driver["driver_number"]
    full_name = driver["full_name"]

    print(f"Buscando telemetria de {full_name}...")

    response = requests.get(
        f"{BASE_URL}/car_data",
        params={
            "driver_number": driver_number,
            "session_key": SESSION_KEY
        }
    )

    response.raise_for_status()

    data = response.json()

    file_name = f"driver_{driver_number}.json"

    save_bronze(
        "car_data",
        data,
        file_name
    )

    print(f"{full_name} salvo em {file_name}")