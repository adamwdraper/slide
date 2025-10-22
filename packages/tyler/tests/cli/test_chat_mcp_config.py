import io
import json
from unittest.mock import patch

from tyler.cli.chat import load_config


def test_chat_config_mcp_pass_through(tmp_path, monkeypatch):
    # Create a temporary YAML config with mcp section
    cfg = {
        "name": "Tyler",
        "model_name": "gpt-4.1",
        "mcp": {
            "connect_on_start": True,
            "servers": [
                {"name": "wandb_docs", "transport": "sse", "url": "https://docs.wandb.ai/mcp"}
            ]
        }
    }
    # Write as JSON for simplicity; loader supports json too
    cfg_file = tmp_path / "tyler-chat-config.json"
    cfg_file.write_text(json.dumps(cfg))

    # Call loader with explicit path
    with patch("pathlib.Path.exists", return_value=True), 
         patch("pathlib.Path.__truediv__", return_value=cfg_file), 
         patch("pathlib.Path.suffix", new_callable=lambda: ".json"):
        config = load_config(str(cfg_file))

    # Ensure mcp mapping occurred
    assert "mcp" in config
    assert config["mcp"].get("connect_on_init") is True
    servers = config["mcp"].get("servers")
    assert servers and servers[0]["name"] == "wandb_docs"


