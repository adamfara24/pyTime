from pathlib import Path
from unittest.mock import MagicMock, call, patch

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
    return ClientError({"Error": {"Code": code, "Message": "test error"}}, "UploadFile")


@pytest.fixture
def mock_boto(monkeypatch):
    mock_instance = MagicMock()
    monkeypatch.setattr("storage.s3_client.boto3.client", lambda *a, **kw: mock_instance)
    return mock_instance


# --- S3Client.upload_file ---

def test_upload_file_calls_boto_with_correct_args(mock_boto, tmp_path):
    test_file = tmp_path / "report.pdf"
    test_file.write_text("hello")

    client = S3Client(TEST_CONFIG)
    client.upload_file(test_file, "alice/report.pdf")

    mock_boto.upload_file.assert_called_once_with(
        str(test_file),
        "test-bucket",
        "alice/report.pdf",
        Callback=None,
    )


def test_upload_file_passes_callback_when_provided(mock_boto, tmp_path):
    test_file = tmp_path / "data.csv"
    test_file.write_text("a,b,c")
    callback = MagicMock()

    client = S3Client(TEST_CONFIG)
    client.upload_file(test_file, "alice/data.csv", callback=callback)

    mock_boto.upload_file.assert_called_once_with(
        str(test_file),
        "test-bucket",
        "alice/data.csv",
        Callback=callback,
    )


# --- ui/upload.py flow ---

@pytest.fixture
def mock_s3_client(monkeypatch):
    mock_boto = MagicMock()
    monkeypatch.setattr("storage.s3_client.boto3.client", lambda *a, **kw: mock_boto)
    return S3Client(TEST_CONFIG)


def test_upload_flow_rejects_missing_file(mock_s3_client, capsys):
    from ui.upload import upload_file_flow

    with patch("ui.upload.Prompt.ask", return_value="/nonexistent/file.txt"):
        upload_file_flow(mock_s3_client, "alice")

    captured = capsys.readouterr()
    assert "not found" in captured.out.lower() or "not found" in captured.out


def test_upload_flow_rejects_directory_path(mock_s3_client, tmp_path, capsys):
    from ui.upload import upload_file_flow

    with patch("ui.upload.Prompt.ask", return_value=str(tmp_path)):
        upload_file_flow(mock_s3_client, "alice")

    captured = capsys.readouterr()
    assert "directory" in captured.out.lower()


def test_upload_flow_constructs_correct_s3_key(mock_s3_client, tmp_path):
    from ui.upload import upload_file_flow

    test_file = tmp_path / "notes.txt"
    test_file.write_text("hello world")

    with patch("ui.upload.Prompt.ask", return_value=str(test_file)), \
         patch("ui.upload.Progress") as mock_progress_cls:

        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        upload_file_flow(mock_s3_client, "alice")

    mock_s3_client.client.upload_file.assert_called_once()
    args = mock_s3_client.client.upload_file.call_args
    assert args[0][1] == "test-bucket"
    assert args[0][2] == "alice/notes.txt"


def test_upload_flow_handles_client_error_gracefully(mock_s3_client, tmp_path, capsys):
    from ui.upload import upload_file_flow

    test_file = tmp_path / "fail.txt"
    test_file.write_text("data")
    mock_s3_client.client.upload_file.side_effect = _client_error("NoSuchBucket")

    with patch("ui.upload.Prompt.ask", return_value=str(test_file)), \
         patch("ui.upload.Progress") as mock_progress_cls:

        mock_progress = MagicMock()
        mock_progress.__enter__ = MagicMock(return_value=mock_progress)
        mock_progress.__exit__ = MagicMock(return_value=False)
        mock_progress_cls.return_value = mock_progress

        upload_file_flow(mock_s3_client, "alice")

    captured = capsys.readouterr()
    assert "failed" in captured.out.lower()
