"""
Configuración local (por equipo): dónde está el servidor y con qué clave.
Todos los equipos deben usar el mismo servidor y la misma clave para
compartir la información.
"""
import json
from pathlib import Path

LOCAL_CONFIG_DIR = Path.home() / ".facturador"
LOCAL_CONFIG_FILE = LOCAL_CONFIG_DIR / "config.json"


def load_config():
    if not LOCAL_CONFIG_FILE.exists():
        return None
    try:
        with open(LOCAL_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_config(server_url: str, api_key: str):
    LOCAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOCAL_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"server_url": server_url, "api_key": api_key}, f, indent=2)


def get_server():
    from db import Server
    cfg = load_config()
    if not cfg:
        return None
    return Server(base_url=cfg.get("server_url", ""), api_key=cfg.get("api_key", ""))
