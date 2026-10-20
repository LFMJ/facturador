"""
Configuración local (por equipo): dónde está el servidor y la sesión del
usuario que entró en este equipo (o la clave maestra, si es el dueño).
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


def save_server(server, username: str = ""):
    """Guarda URL + sesión. Con token no se guarda la contraseña, solo la sesión."""
    LOCAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {"server_url": server.base_url, "token": server.token, "api_key": server.api_key, "username": username}
    with open(LOCAL_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    try:
        LOCAL_CONFIG_FILE.chmod(0o600)
    except OSError:
        pass


def forget_session():
    """Cierra la sesión en este equipo pero recuerda la URL y el usuario."""
    cfg = load_config() or {}
    cfg["token"] = ""
    cfg["api_key"] = ""
    LOCAL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOCAL_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def get_server():
    from db import Server
    cfg = load_config()
    if not cfg:
        return None
    return Server(base_url=cfg.get("server_url", ""), api_key=cfg.get("api_key", ""), token=cfg.get("token", ""))


def last_username() -> str:
    return (load_config() or {}).get("username", "")
