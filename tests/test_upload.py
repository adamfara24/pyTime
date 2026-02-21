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
    return ClientError({"Error": {"Code": code, "Message": "test error"}}, "UploadFile")


@pytest.fixture
def mock_boto(monkeypatch):
    mock_instance = MagicMock()
    monkeypatch.setattr("storage.s3_client.boto3.client", lambda *a, **kw: mock_instance)
    return mock_instance


@pytest.fixture
def mock_s3_client(monkeypatch):
    mock_boto = MagicMock()
    monkeypatch.setattr("storage.s3_client.boto3.client", lambda *a, **kw: mock_boto)
    return S3Client(TEST_CONFIG)


@pytest.fixture
def mock_progress():
    """Returns a context-manager-compatible Progress mock."""
    with patch("ui.upload.Progress") as mock_cls:
        instance = MagicMock()
        instance.__enter__ = MagicMock(return_value=instance)
        instance.__exit__ = MagicMock(return_value=False)
        mock_cls.return_value = instance
        yield instance


# ---------------------------------------------------------------------------
# S3Client.upload_file
# ---------------------------------------------------------------------------

def test_upload_file_calls_boto_with_correct_args(mock_boto, tmp_path):
    test_file = tmp_path / "report.pdf"
    test_file.write_text("hello")

    client = S3Client(TEST_CONFIG)
    client.upload_file(test_file, "alice/report.pdf")

    mock_boto.upload_file.assert_called_once_with(
        str(test_file), "test-bucket", "alice/report.pdf", Callback=None
    )


def test_upload_file_passes_callback_when_provided(mock_boto, tmp_path):
    test_file = tmp_path / "data.csv"
    test_file.write_text("a,b,c")
    callback = MagicMock()

    client = S3Client(TEST_CONFIG)
    client.upload_file(test_file, "alice/data.csv", callback=callback)

    mock_boto.upload_file.assert_called_once_with(
        str(test_file), "test-bucket", "alice/data.csv", Callback=callback
    )


# ---------------------------------------------------------------------------
# _upload_file_flow (single file)
# ---------------------------------------------------------------------------

def test_file_flow_rejects_missing_file(mock_s3_client, capsys):
    from ui.upload import _upload_file_flow

    with patch("ui.upload.Prompt.ask", return_value="/nonexistent/file.txt"):
        _upload_file_flow(mock_s3_client, "alice")

    assert "not found" in capsys.readouterr().out.lower()


def test_file_flow_rejects_directory_path(mock_s3_client, tmp_path, capsys):
    from ui.upload import _upload_file_flow

    with patch("ui.upload.Prompt.ask", return_value=str(tmp_path)):
        _upload_file_flow(mock_s3_client, "alice")

    assert "directory" in capsys.readouterr().out.lower()


def test_file_flow_constructs_correct_s3_key(mock_s3_client, tmp_path, mock_progress):
    from ui.upload import _upload_file_flow

    test_file = tmp_path / "notes.txt"
    test_file.write_text("hello world")

    with patch("ui.upload.Prompt.ask", return_value=str(test_file)):
        _upload_file_flow(mock_s3_client, "alice")

    args = mock_s3_client.client.upload_file.call_args[0]
    assert args[1] == "test-bucket"
    assert args[2] == "alice/notes.txt"


def test_file_flow_handles_client_error_gracefully(mock_s3_client, tmp_path, mock_progress, capsys):
    from ui.upload import _upload_file_flow

    test_file = tmp_path / "fail.txt"
    test_file.write_text("data")
    mock_s3_client.client.upload_file.side_effect = _client_error("NoSuchBucket")

    with patch("ui.upload.Prompt.ask", return_value=str(test_file)):
        _upload_file_flow(mock_s3_client, "alice")

    assert "failed" in capsys.readouterr().out.lower()


# ---------------------------------------------------------------------------
# _upload_directory_flow
# ---------------------------------------------------------------------------

def test_dir_flow_rejects_missing_directory(mock_s3_client, capsys):
    from ui.upload import _upload_directory_flow

    with patch("ui.upload.Prompt.ask", return_value="/nonexistent/dir"):
        _upload_directory_flow(mock_s3_client, "alice")

    assert "not found" in capsys.readouterr().out.lower()


def test_dir_flow_rejects_file_path(mock_s3_client, tmp_path, capsys):
    from ui.upload import _upload_directory_flow

    test_file = tmp_path / "file.txt"
    test_file.write_text("data")

    with patch("ui.upload.Prompt.ask", return_value=str(test_file)):
        _upload_directory_flow(mock_s3_client, "alice")

    assert "file" in capsys.readouterr().out.lower()


def test_dir_flow_rejects_empty_directory(mock_s3_client, tmp_path, capsys):
    from ui.upload import _upload_directory_flow

    with patch("ui.upload.Prompt.ask", return_value=str(tmp_path)):
        _upload_directory_flow(mock_s3_client, "alice")

    assert "no files" in capsys.readouterr().out.lower()


def test_dir_flow_preserves_folder_structure(mock_s3_client, tmp_path, mock_progress):
    from ui.upload import _upload_directory_flow

    # Build: myproject/main.py and myproject/src/utils.py
    project = tmp_path / "myproject"
    (project / "src").mkdir(parents=True)
    (project / "main.py").write_text("main")
    (project / "src" / "utils.py").write_text("utils")

    with patch("ui.upload.Prompt.ask", return_value=str(project)):
        _upload_directory_flow(mock_s3_client, "alice")

    uploaded_keys = [
        call[0][2]
        for call in mock_s3_client.client.upload_file.call_args_list
    ]
    assert "alice/myproject/main.py" in uploaded_keys
    assert "alice/myproject/src/utils.py" in uploaded_keys


def test_dir_flow_summary_counts_successes_and_failures(mock_s3_client, tmp_path, mock_progress, capsys):
    from ui.upload import _upload_directory_flow

    project = tmp_path / "batch"
    project.mkdir()
    (project / "good.txt").write_text("ok")
    (project / "bad.txt").write_text("fail")

    call_count = 0

    def selective_fail(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if "bad.txt" in args[2]:
            raise Exception("simulated failure")

    mock_s3_client.client.upload_file.side_effect = selective_fail

    with patch("ui.upload.Prompt.ask", return_value=str(project)):
        _upload_directory_flow(mock_s3_client, "alice")

    out = capsys.readouterr().out
    assert "1" in out   # 1 success
    assert "failed" in out.lower()
