import requests
from pathlib import Path
import json

BRONZE_PATH = Path("data/bronze")
BRONZE_PATH.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://api.openf1.org/v1"
endpoint = "sessions"
response = requests.get(f'{BASE_URL}/{endpoint}', params =

    {

    })

data = response.json()


def save_bronze(endpoint, data):
    endpoint_path = BRONZE_PATH/endpoint
    endpoint_path.mkdir(parents=True, exist_ok=True)
    file_path = endpoint_path/"data.json"
    with open(file_path, 'w', encoding='utf-8') as arquivo:
        json.dump(data, arquivo, ensure_ascii = False, indent=4)

save_bronze(endpoint,data)
    

