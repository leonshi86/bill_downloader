# config.py — 配置读写（JSON）

import json
import os

DEFAULT_CONFIG = {
    "email": "",
    "auth_code": "",
    "password": "",
    "use_auth_code": True,
    "senders": [],
    "subject_keywords": [],
    "save_dir": "",
    "check_days": 30,
    "allow_exts": [".pdf"],
    "auto_start": False,
    "minimize_to_tray": True,
}

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        # 合并默认键
        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)
        return cfg
    except Exception:
        return dict(DEFAULT_CONFIG)


def save_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=4)
