import json
import os
from pathlib import Path
import secrets

import requests

from scripts.paineis_metabase import dashboards, definitions


def main():
    base = os.getenv("METABASE_URL", "http://localhost:3000")
    state_path = Path("logs/metabase-config.json")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    if state_path.exists():
        state = json.loads(state_path.read_text())
    else:
        state = {"email": "almeida@openf1.local", "password": secrets.token_urlsafe(24)}
        state_path.touch(mode=0o600)
        state_path.write_text(json.dumps(state, indent=2))
    session = requests.Session()

    def request(method, path, **kwargs):
        response = session.request(method, base + path, timeout=120, **kwargs)
        if not response.ok:
            raise RuntimeError(f"Metabase: {method} {path} retornou {response.status_code}: {response.text[:500]}")
        return response.json() if response.content else None

    properties = request("GET", "/api/session/properties")
    if properties.get("setup-token"):
        response = request("POST", "/api/setup", json={
            "token": properties["setup-token"],
            "user": {"first_name": "Almeida", "last_name": "OpenF1", "email": state["email"], "password": state["password"]},
            "prefs": {"site_name": "OpenF1 — Central de telemetria", "allow_tracking": False},
        })
    else:
        response = request("POST", "/api/session", json={"username": state["email"], "password": state["password"]})
    session.headers["X-Metabase-Session"] = response["id"]
    request("PUT", "/api/setting/site-locale", json={"value": "pt-BR"})
    databases = request("GET", "/api/database")["data"]
    database = next((item for item in databases if item["name"] == "OpenF1 Analytics"), None)
    if database is None:
        database = request("POST", "/api/database", json={
            "name": "OpenF1 Analytics", "engine": "postgres",
            "details": {"host": "postgres", "port": 5432, "dbname": "openf1", "user": "openf1_leitura", "password": "leitura_local", "ssl": False},
        })
    state["database_id"] = database["id"]
    queries = definitions()
    cards = []
    existing_cards = state.get("card_ids", [])
    for index, definition in enumerate(queries):
        payload = {
            "name": definition["name"], "display": definition["display"],
            "description": definition["description"],
            "dataset_query": {"type": "native", "database": database["id"], "native": {
                "query": definition["query"], "template-tags": {
                    "sessao": {"id": "sessao", "name": "sessao", "display-name": "Sessão", "type": "number", "default": "9158", "required": True},
                    "piloto": {"id": "piloto", "name": "piloto", "display-name": "Piloto", "type": "number", "required": False},
                },
            }},
            "visualization_settings": definition["settings"],
        }
        if index < len(existing_cards):
            card = request("PUT", f"/api/card/{existing_cards[index]}", json=payload)
        else:
            card = request("POST", "/api/card", json=payload)
        cards.append(card)
        state["card_ids"] = [item["id"] for item in cards] + existing_cards[len(cards):]
        state_path.write_text(json.dumps(state, indent=2))
    for board in dashboards():
        if not state.get(board["key"]):
            dashboard = request("POST", "/api/dashboard", json={
                "name": board["name"], "description": board["description"], "parameters": [],
            })
            state[board["key"]] = dashboard["id"]
            state_path.write_text(json.dumps(state, indent=2))
        placements = []
        for index in board["cards"]:
            x, y, width, height = queries[index]["position"]
            placements.append({
                "id": -(index + 1), "card_id": cards[index]["id"],
                "row": y, "col": x, "size_x": width, "size_y": height,
                "visualization_settings": {},
                "parameter_mappings": [
                    {"parameter_id": field, "card_id": cards[index]["id"], "target": ["variable", ["template-tag", field]]}
                    for field in ["sessao", "piloto"]
                ],
            })
        parameters = [
            {"id": "sessao", "name": "Sessão", "slug": "sessao", "type": "number/=", "default": "9158"},
            {"id": "piloto", "name": "Piloto (número)", "slug": "piloto", "type": "number/="},
        ]
        if board["driver"]:
            parameters[1]["default"] = board["driver"]
        request("PUT", f"/api/dashboard/{state[board['key']]}", json={
            "name": board["name"], "description": board["description"],
            "parameters": parameters, "dashcards": placements,
        })
        print(f"{board['name']}: {base}/dashboard/{state[board['key']]}")
    for card in cards:
        result = request("POST", f"/api/card/{card['id']}/query", json={})
        if result.get("status") != "completed":
            raise RuntimeError(f"Consulta falhou: {card['name']}")
        print(f"{card['name']}: {len(result['data']['rows'])} linhas")
    print(f"Dashboard: {base}/dashboard/{state['dashboard_id']}")
    print(f"Credenciais locais salvas em {state_path}")


if __name__ == "__main__":
    main()
