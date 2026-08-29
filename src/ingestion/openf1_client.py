import requests 
import json
import pandas as pd

BASE_URL = "https://api.openf1.org/v1"

response = requests.get(f'{BASE_URL}/car_data',
params = {
    'driver_number': 55,
    'session_key': 9159
}
)

print(response.status_code)

data = response.json()
with open ('data/bronze/car_data.json', 'w', 
encoding = "utf-8") as arquivo:
    json.dump(data,arquivo, ensure_ascii = False)


df = pd.DataFrame(data)
print(df.head)
print(df.columns)