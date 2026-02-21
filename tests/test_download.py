from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from storage.s3_client import S3Client

TEST_CONFIG = {
    "aws_access_key": "fake_key",
    "aws_secret_key": "fake_secret",
    "aws_region": "us-east-1",
    "bucket_name": "test-bucket",
}


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "test error"}}, "Op")


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
def mock_progress():
    with patch("ui.download.Progress") as mock_cls:
        instance = MagicMock()
        instance.__enter__ = MagicMock(return_value=instance)
        instance.__exit__ = MagicMock(return_value=False)
        mock_cls.return_value = instance
        yield instance


# ---------------------------------------------------------------------------
# S3Client.download_file
# ---------------------------------------------------------------------------

def test_download_file_calls_boto_with_correct_args(mock_boto, tmp_path):
    local_path = tmp_path / "file.txt"
    client = S3Client(TEST_CONFIG)
    client.download_file("alice/file.txt", local_path)

    mock_boto.download_file.assert_called_once_with(
        "test-bucket", "alice/file.txt", str(local_path), Callback=None
    )


def test_download_file_creates_parent_directories(mock_boto, tmp_path):
    local_path = tmp_path / "nested" / "dir" / "file.txt"
    client = S3Client(TEST_CONFIG)
    client.download_file("alice/file.txt", local_path)

    assert local_path.parent.exists()


def test_download_file_passes_callback(mock_boto, tmp_path):
    local_path = tmp_path / "file.txt"
    callback = MagicMock()
    client = S3Client(TEST_CONFIG)
    client.download_file("alice/file.txt", local_path, callback=callback)

    mock_boto.download_file.assert_called_once_with(
        "test-bucket", "alice/file.txt", str(local_path), Callback=callback
    )


# ---------------------------------------------------------------------------
# S3Client.list_all_objects
# ---------------------------------------------------------------------------

def test_list_all_objects_returns_all_files(mock_boto):
    mock_boto.get_paginator.return_value.paginate.return_value = [
        {
            "Contents": [
                {"Key": "alice/docs/a.txt", "Size": 100},
                {"Key": "alice/docs/b.txt", "Size": 200},
            ]
        }
    ]

    client = S3Client(TEST_CONFIG)
    objects = client.list_all_objects("alice/docs/")

    assert len(objects) == 2
    keys = [o["key"] for o in objects]
    assert "alice/docs/a.txt" in keys
    assert "alice/docs/b.txt" in keys


def test_list_all_objects_excludes_prefix_placeholder(mock_boto):
    mock_boto.get_paginator.return_value.paginate.return_value = [
        {
            "Contents": [
                {"Key": "alice/docs/", "Size": 0},
                {"Key": "alice/docs/file.txt", "Size": 50},
            ]
        }
    ]

    client = S3Client(TEST_CONFIG)
    objects = client.list_all_objects("alice/docs/")

    keys = [o["key"] for o in objects]
    assert "alice/docs/" not in keys
    assert "alice/docs/file.txt" in keys


# ---------------------------------------------------------------------------
# download_single_file
# ---------------------------------------------------------------------------

def test_download_single_file_uses_correct_key(mock_s3_client, tmp_path, mock_progress):
    from ui.download import download_single_file

    file_info = {"key": "alice/report.pdf", "size": 1024}

    with patch("ui.download.Prompt.ask", return_value=str(tmp_path)):
        download_single_file(mock_s3_client, file_info)

    mock_s3_client.client.download_file.assert_called_once()
    args = mock_s3_client.client.download_file.call_args[0]
    assert args[0] == "test-bucket"
    assert args[1] == "alice/report.pdf"


def test_download_single_file_saves_to_correct_path(mock_s3_client, tmp_path, mock_progress):
    from ui.download import download_single_file

    file_info = {"key": "alice/report.pdf", "size": 512}

    with patch("ui.download.Prompt.ask", return_value=str(tmp_path)):
        download_single_file(mock_s3_client, file_info)

    args = mock_s3_client.client.download_file.call_args[0]
    assert args[2] == str(tmp_path / "report.pdf")


def test_download_single_file_handles_client_error(mock_s3_client, tmp_path, mock_progress, capsys):
    from ui.download import download_single_file

    file_info = {"key": "alice/file.txt", "size": 100}
    mock_s3_client.client.download_file.side_effect = _client_error("NoSuchKey")

    with patch("ui.download.Prompt.ask", return_value=str(tmp_path)):
        download_single_file(mock_s3_client, file_info)

    assert "failed" in capsys.readouterr().out.lower()


# ---------------------------------------------------------------------------
# download_flow navigation
# ---------------------------------------------------------------------------

def test_download_flow_shows_empty_for_new_user(mock_s3_client, capsys):
    from ui.download import download_flow

    mock_s3_client.list_folder = MagicMock(return_value=([], []))
    download_flow(mock_s3_client, "alice")

    assert "nothing uploaded" in capsys.readouterr().out.lower()


def test_download_flow_quits_on_q(mock_s3_client):
    from ui.download import download_flow

    mock_s3_client.list_folder = MagicMock(
        return_value=([], [{"key": "alice/file.txt", "size": 100, "last_modified": None}])
    )

    with patch("ui.download.Prompt.ask", return_value="q"):
        download_flow(mock_s3_client, "alice")


def test_download_flow_folder_navigate_then_quit(mock_s3_client):
    from ui.download import download_flow

    def list_folder_side(prefix):
        if prefix == "alice/":
            return (["alice/docs/"], [])
        return ([], [{"key": "alice/docs/f.txt", "size": 10, "last_modified": None}])

    mock_s3_client.list_folder = MagicMock(side_effect=list_folder_side)

    # Select folder [1], choose navigate, then quit [q]
    with patch("ui.download.Prompt.ask", side_effect=["1", "navigate", "q"]):
        download_flow(mock_s3_client, "alice")

    assert mock_s3_client.list_folder.call_count == 2
