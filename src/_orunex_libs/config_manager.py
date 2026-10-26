import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "orunex_config.json")

DEFAULT_CONFIG = {
    "engine": "light",
    "ctx_len": 16384,
    "user_name": "Usuario Elite",
    "language": "es",
    "language_full": "Espanol",
    "ui_scale": 1.0,
    "auto_heal": True,
    "mem_record": True,
    "send_screenshot": True,
    "send_remote_screenshot": False,
    "num_predict": 4096,
    "voice_enabled": True,
    "screen_glow": True,        # Blue border glow when Orunex is processing
    "task_timeout_s": 3600,     # Max seconds to wait for a complex task (default 1hr)
    "copilot_enabled": True,    # Proactive copilot analysis
    "max_retries": 3            # Auto-heal retries on task failure
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return DEFAULT_CONFIG

def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
        # Sync ctx_len for LOCAL CORE (llama-cpp-python reads OLLAMA_NUM_CTX from env for compatibility)
        os.environ["OLLAMA_NUM_CTX"] = str(config.get("ctx_len", 8192))
        return True
    except:
        return False

def get_val(key):
    config = load_config()
    return config.get(key, DEFAULT_CONFIG.get(key))

def set_val(key, val):
    config = load_config()
    config[key] = val
    save_config(config)
