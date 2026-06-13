import os
import yaml
from dotenv import load_dotenv

# Ensure .env is loaded
load_dotenv()

class ConfigManager:
    def __init__(self):
        self.codeband_cfg = {}
        if os.path.exists("codeband.yaml"):
            try:
                with open("codeband.yaml", "r", encoding="utf-8") as f:
                    self.codeband_cfg = yaml.safe_load(f) or {}
            except Exception:
                pass
        
        self.agent_cfg = {}
        if os.path.exists("agent_config.yaml"):
            try:
                with open("agent_config.yaml", "r", encoding="utf-8") as f:
                    self.agent_cfg = yaml.safe_load(f) or {}
            except Exception:
                pass

    def get(self, env_key: str, yaml_path: str = None, default: str = None) -> str:
        # 1. Load from environment variable first
        val = os.getenv(env_key)
        if val is not None:
            return val
        
        # 2. Fall back to codeband.yaml if path is specified
        if yaml_path and self.codeband_cfg:
            parts = yaml_path.split(".")
            curr = self.codeband_cfg
            found = True
            for part in parts:
                if isinstance(curr, dict) and part in curr:
                    curr = curr[part]
                else:
                    found = False
                    break
            if found:
                return str(curr)
                
        return default

config = ConfigManager()
