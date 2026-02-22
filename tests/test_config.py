import json
from unittest.mock import patch

import pytest

import config as config_module
from config import load_config, save_config, validate_config


def test_load_config_returns_none_when_file_missing(tmp_path):
    missing = tmp_path / "config.json"
    with patch.object(config_module, "CONFIG_FILE", missing):
        result = load_config()
    assert result is None


def test_save_and_load_config_roundtrip(tmp_path):
    config_file = tmp_path / "config.json"
    data = {
        "aws_access_key": "AKIATEST",
        "aws_secret_key": "secret",
        "aws_region": "us-east-1",
        "bucket_name": "my-bucket",
    }
    with patch.object(config_module, "CONFIG_FILE", config_file), \
         patch.object(config_module, "CONFIG_DIR", tmp_path):
        save_config(data)
        result = load_config()

    assert result == data


def test_save_config_creates_directory(tmp_path):
    nested_dir = tmp_path / "nested" / "dir"
    config_file = nested_dir / "config.json"
    with patch.object(config_module, "CONFIG_FILE", config_file), \
         patch.object(config_module, "CONFIG_DIR", nested_dir):
        save_config({"bucket_name": "test"})
    assert config_file.exists()


def test_load_config_returns_none_on_malformed_json(tmp_path):
    config_file = tmp_path / "config.json"
    config_file.write_text("this is not valid json")
    with patch.object(config_module, "CONFIG_FILE", config_file):
        result = load_config()
    assert result is None


# ---------------------------------------------------------------------------
# validate_config
# ---------------------------------------------------------------------------

_VALID = {
    "aws_access_key": "AKIATEST",
    "aws_secret_key": "secret",
    "aws_region": "us-east-1",
    "bucket_name": "my-bucket",
}


def test_validate_config_passes_for_complete_config():
    assert validate_config(_VALID) is True


def test_validate_config_fails_when_key_missing():
    for key in _VALID:
        partial = {k: v for k, v in _VALID.items() if k != key}
        assert validate_config(partial) is False, f"Should fail when '{key}' is missing"


def test_validate_config_fails_when_value_is_empty_string():
    config = {**_VALID, "aws_access_key": ""}
    assert validate_config(config) is False


def test_validate_config_fails_when_value_is_whitespace():
    config = {**_VALID, "bucket_name": "   "}
    assert validate_config(config) is False


def test_validate_config_fails_for_non_dict():
    assert validate_config(None) is False
    assert validate_config("not a dict") is False


def test_saved_config_is_valid_json(tmp_path):
    config_file = tmp_path / "config.json"
    data = {"aws_access_key": "KEY", "bucket_name": "bucket"}
    with patch.object(config_module, "CONFIG_FILE", config_file), \
         patch.object(config_module, "CONFIG_DIR", tmp_path):
        save_config(data)

    with open(config_file) as f:
        parsed = json.load(f)
    assert parsed == data
