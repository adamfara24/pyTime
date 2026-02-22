import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from sharing.code_provider import CodeProvider
from sharing.s3_code_provider import S3CodeProvider, _unique_code
from storage.s3_client import S3Client

TEST_CONFIG = {
    "aws_access_key": "fake_key",
    "aws_secret_key": "fake_secret",
    "aws_region": "us-east-1",
    "bucket_name": "test-bucket",
}


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "test"}}, "Op")


@pytest.fixture
def mock_boto(monkeypatch):
    instance = MagicMock()
    monkeypatch.setattr("storage.s3_client.boto3.client", lambda *a, **kw: instance)
    return instance


@pytest.fixture
def mock_s3_client(monkeypatch):
    mock_boto = MagicMock()
    monkeypatch.setattr("storage.s3_client.boto3.client", lambda *a, **kw: mock_boto)
    return S3Client(TEST_CONFIG)


@pytest.fixture
def provider(mock_s3_client):
    return S3CodeProvider(mock_s3_client)


# ---------------------------------------------------------------------------
# CodeProvider ABC
# ---------------------------------------------------------------------------

def test_code_provider_is_abstract():
    """Cannot instantiate CodeProvider directly."""
    with pytest.raises(TypeError):
        CodeProvider()


def test_concrete_must_implement_all_methods():
    class Incomplete(CodeProvider):
        def generate_code(self, path): return ""
        # missing resolve_code and revoke_code

    with pytest.raises(TypeError):
        Incomplete()


# ---------------------------------------------------------------------------
# _unique_code helper
# ---------------------------------------------------------------------------

def test_unique_code_avoids_collisions():
    existing = {"AAAAAA": {}, "BBBBBB": {}}
    with patch("sharing.s3_code_provider.random.choices", side_effect=[
        list("AAAAAA"),  # collision
        list("BBBBBB"),  # collision
        list("CCCCCC"),  # unique
    ]):
        code = _unique_code(existing)
    assert code == "CCCCCC"


def test_unique_code_is_six_chars():
    code = _unique_code({})
    assert len(code) == 6


# ---------------------------------------------------------------------------
# S3CodeProvider._read_codes
# ---------------------------------------------------------------------------

def test_read_codes_returns_empty_dict_when_key_missing(provider, mock_s3_client):
    mock_s3_client.client.get_object.side_effect = _client_error("NoSuchKey")
    assert provider._read_codes() == {}


def test_read_codes_parses_json(provider, mock_s3_client):
    data = {"ABC123": {"path": "alice/docs/", "created_at": "2024-01-01"}}
    body = MagicMock()
    body.read.return_value = json.dumps(data).encode()
    mock_s3_client.client.get_object.return_value = {"Body": body}

    result = provider._read_codes()
    assert result == data


# ---------------------------------------------------------------------------
# S3CodeProvider.generate_code
# ---------------------------------------------------------------------------

def test_generate_code_writes_to_s3(provider, mock_s3_client):
    mock_s3_client.client.get_object.side_effect = _client_error("NoSuchKey")

    code = provider.generate_code("alice/docs/")

    assert len(code) == 6
    mock_s3_client.client.put_object.assert_called_once()
    call_kwargs = mock_s3_client.client.put_object.call_args[1]
    stored = json.loads(call_kwargs["Body"])
    assert code in stored
    assert stored[code]["path"] == "alice/docs/"


def test_generate_code_preserves_existing_codes(provider, mock_s3_client):
    existing = {"EXIST1": {"path": "alice/old/", "created_at": "2024-01-01"}}
    body = MagicMock()
    body.read.return_value = json.dumps(existing).encode()
    mock_s3_client.client.get_object.return_value = {"Body": body}

    provider.generate_code("alice/new/")

    call_kwargs = mock_s3_client.client.put_object.call_args[1]
    stored = json.loads(call_kwargs["Body"])
    assert "EXIST1" in stored


# ---------------------------------------------------------------------------
# S3CodeProvider.resolve_code
# ---------------------------------------------------------------------------

def test_resolve_code_returns_path_for_valid_code(provider, mock_s3_client):
    data = {"ABC123": {"path": "alice/docs/", "created_at": "2024-01-01"}}
    body = MagicMock()
    body.read.return_value = json.dumps(data).encode()
    mock_s3_client.client.get_object.return_value = {"Body": body}

    result = provider.resolve_code("ABC123")
    assert result == "alice/docs/"


def test_resolve_code_is_case_insensitive(provider, mock_s3_client):
    data = {"ABC123": {"path": "alice/docs/", "created_at": "2024-01-01"}}
    body = MagicMock()
    body.read.return_value = json.dumps(data).encode()
    mock_s3_client.client.get_object.return_value = {"Body": body}

    assert provider.resolve_code("abc123") == "alice/docs/"


def test_resolve_code_returns_none_for_unknown_code(provider, mock_s3_client):
    mock_s3_client.client.get_object.side_effect = _client_error("NoSuchKey")
    assert provider.resolve_code("XXXXXX") is None


# ---------------------------------------------------------------------------
# S3CodeProvider.revoke_code
# ---------------------------------------------------------------------------

def test_revoke_code_removes_entry(provider, mock_s3_client):
    data = {
        "ABC123": {"path": "alice/docs/", "created_at": "2024-01-01"},
        "XYZ789": {"path": "alice/pics/", "created_at": "2024-01-02"},
    }
    body = MagicMock()
    body.read.return_value = json.dumps(data).encode()
    mock_s3_client.client.get_object.return_value = {"Body": body}

    provider.revoke_code("ABC123")

    call_kwargs = mock_s3_client.client.put_object.call_args[1]
    stored = json.loads(call_kwargs["Body"])
    assert "ABC123" not in stored
    assert "XYZ789" in stored


def test_revoke_code_is_silent_for_unknown_code(provider, mock_s3_client):
    mock_s3_client.client.get_object.side_effect = _client_error("NoSuchKey")
    provider.revoke_code("DOESNT_EXIST")  # should not raise
    mock_s3_client.client.put_object.assert_called_once()


# ---------------------------------------------------------------------------
# share_flow / generate / redeem (UI)
# ---------------------------------------------------------------------------

def test_share_flow_generate_shows_code(mock_s3_client, capsys):
    from ui.share import share_flow

    mock_provider = MagicMock()
    mock_provider.generate_code.return_value = "ABC123"
    mock_s3_client.list_folder = MagicMock(
        return_value=(["alice/docs/"], [])
    )

    # "generate" → action, "1" → folder choice, "" → no expiry
    with patch("ui.share.Prompt.ask", side_effect=["generate", "1", ""]):
        share_flow(mock_s3_client, "alice", mock_provider)

    assert "ABC123" in capsys.readouterr().out


def test_share_flow_redeem_valid_code(mock_s3_client, capsys):
    from ui.share import share_flow

    mock_provider = MagicMock()
    mock_provider.resolve_code.return_value = "alice/docs/"
    mock_s3_client.list_all_objects = MagicMock(return_value=[])

    with patch("ui.share.Prompt.ask", side_effect=["redeem", "ABC123"]), \
         patch("ui.share._download_folder"):
        share_flow(mock_s3_client, "alice", mock_provider)

    assert "valid" in capsys.readouterr().out.lower()


def test_share_flow_redeem_invalid_code(mock_s3_client, capsys):
    from ui.share import share_flow

    mock_provider = MagicMock()
    mock_provider.resolve_code.return_value = None

    with patch("ui.share.Prompt.ask", side_effect=["redeem", "BADCOD"]):
        share_flow(mock_s3_client, "alice", mock_provider)

    assert "invalid" in capsys.readouterr().out.lower()


def test_share_flow_generate_no_folders_shows_hint(mock_s3_client, capsys):
    from ui.share import share_flow

    mock_provider = MagicMock()
    mock_s3_client.list_folder = MagicMock(return_value=([], []))

    with patch("ui.share.Prompt.ask", return_value="generate"):
        share_flow(mock_s3_client, "alice", mock_provider)

    assert "no folders" in capsys.readouterr().out.lower()


# ---------------------------------------------------------------------------
# Code expiration
# ---------------------------------------------------------------------------

def test_generate_code_stores_expires_at_when_hours_given(provider, mock_s3_client):
    mock_s3_client.client.get_object.side_effect = _client_error("NoSuchKey")

    provider.generate_code("alice/docs/", expires_hours=24)

    call_kwargs = mock_s3_client.client.put_object.call_args[1]
    stored = json.loads(call_kwargs["Body"])
    code = list(stored.keys())[0]
    assert "expires_at" in stored[code]


def test_generate_code_omits_expires_at_when_no_hours(provider, mock_s3_client):
    mock_s3_client.client.get_object.side_effect = _client_error("NoSuchKey")

    provider.generate_code("alice/docs/", expires_hours=None)

    call_kwargs = mock_s3_client.client.put_object.call_args[1]
    stored = json.loads(call_kwargs["Body"])
    code = list(stored.keys())[0]
    assert "expires_at" not in stored[code]


def test_resolve_code_returns_none_for_expired_code(provider, mock_s3_client):
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    data = {"ABC123": {"path": "alice/docs/", "created_at": "2024-01-01", "expires_at": past}}
    body = MagicMock()
    body.read.return_value = json.dumps(data).encode()
    mock_s3_client.client.get_object.return_value = {"Body": body}

    assert provider.resolve_code("ABC123") is None


def test_resolve_code_returns_path_for_non_expired_code(provider, mock_s3_client):
    future = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    data = {"ABC123": {"path": "alice/docs/", "created_at": "2024-01-01", "expires_at": future}}
    body = MagicMock()
    body.read.return_value = json.dumps(data).encode()
    mock_s3_client.client.get_object.return_value = {"Body": body}

    assert provider.resolve_code("ABC123") == "alice/docs/"


def test_resolve_code_returns_path_when_no_expiry(provider, mock_s3_client):
    data = {"ABC123": {"path": "alice/docs/", "created_at": "2024-01-01"}}
    body = MagicMock()
    body.read.return_value = json.dumps(data).encode()
    mock_s3_client.client.get_object.return_value = {"Body": body}

    assert provider.resolve_code("ABC123") == "alice/docs/"


# ---------------------------------------------------------------------------
# Revoke UI
# ---------------------------------------------------------------------------

def test_share_flow_revoke_valid_code(mock_s3_client, capsys):
    from ui.share import share_flow

    mock_provider = MagicMock()
    mock_provider.resolve_code.return_value = "alice/docs/"

    with patch("ui.share.Prompt.ask", side_effect=["revoke", "ABC123"]):
        share_flow(mock_s3_client, "alice", mock_provider)

    mock_provider.revoke_code.assert_called_once_with("ABC123")
    assert "revoked" in capsys.readouterr().out.lower()


def test_share_flow_revoke_unknown_code(mock_s3_client, capsys):
    from ui.share import share_flow

    mock_provider = MagicMock()
    mock_provider.resolve_code.return_value = None

    with patch("ui.share.Prompt.ask", side_effect=["revoke", "XXXXXX"]):
        share_flow(mock_s3_client, "alice", mock_provider)

    mock_provider.revoke_code.assert_not_called()
    assert "not found" in capsys.readouterr().out.lower()
