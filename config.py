import json
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt

CONFIG_DIR = Path.home() / ".pytime"
CONFIG_FILE = CONFIG_DIR / "config.json"

_REQUIRED_KEYS = {"aws_access_key", "aws_secret_key", "aws_region", "bucket_name"}

console = Console()


def load_config() -> dict | None:
    if not CONFIG_FILE.exists():
        return None
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, KeyError):
        return None


def validate_config(config: dict) -> bool:
    """Return True if config has all required keys with non-empty values."""
    if not isinstance(config, dict):
        return False
    return all(str(config.get(key, "")).strip() for key in _REQUIRED_KEYS)


def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def run_setup_wizard() -> dict:
    console.print("[bold]AWS Configuration Setup[/bold]\n")
    console.print(
        "You'll need an AWS account with an IAM user that has S3 permissions.\n"
        "See [cyan]README.md[/cyan] for step-by-step setup instructions.\n"
    )

    access_key = Prompt.ask("[cyan]AWS Access Key ID[/cyan]").strip()
    secret_key = Prompt.ask("[cyan]AWS Secret Access Key[/cyan]", password=True)
    region = Prompt.ask("[cyan]AWS Region[/cyan]", default="us-east-1")
    bucket = Prompt.ask("[cyan]S3 Bucket Name[/cyan]", default="pytime-files")

    return {
        "aws_access_key": access_key,
        "aws_secret_key": secret_key,
        "aws_region": region,
        "bucket_name": bucket,
    }
