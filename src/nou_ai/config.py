"""Configuration loading for NoU_AI."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from YAML file and .env."""
    load_dotenv()

    if config_path is None:
        config_path = os.getenv("NOU_AI_CONFIG", "config.yaml")

    config: Dict[str, Any] = {}
    path = Path(config_path)
    if path.exists():
        with open(path) as f:
            config = yaml.safe_load(f) or {}

    # Inject GEMINI_API_KEY from env
    stages = config.get("pipeline", {}).get("stages", {})
    gemini_cfg = stages.get("gemini", {})
    if not gemini_cfg.get("api_key"):
        gemini_cfg["api_key"] = os.getenv("GEMINI_API_KEY", "")
    stages["gemini"] = gemini_cfg
    config.setdefault("pipeline", {})["stages"] = stages

    return config
