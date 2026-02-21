from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from storage.s3_client import S3Client
from ui.browse import _fmt_date, _fmt_size

TEST_CONFIG = {
    "aws_access_key": "fake_key",
    "aws_secret_key": "fake_secret",
    "aws_region": "us-east-1",
    "bucket_name": "test-bucket",
}


def _make_page(folders=(), files=()):
    page = {}
    if folders:
        page["CommonPrefixes"] = [{"Prefix": f} for f in folders]
    if files:
        page["Contents"] = files
    return page


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


# ---------------------------------------------------------------------------
# S3Client.list_folder
# ---------------------------------------------------------------------------

def test_list_folder_returns_folders_and_files(mock_boto):
    dt = datetime(2024, 1, 15, 10, 30)
    mock_boto.get_paginator.return_value.paginate.return_value = [
        _make_page(
            folders=["alice/docs/"],
            files=[{"Key": "alice/readme.txt", "Size": 1024, "LastModified": dt}],
        )
    ]

    client = S3Client(TEST_CONFIG)
    folders, files = client.list_folder("alice/")

    assert folders == ["alice/docs/"]
    assert len(files) == 1
    assert files[0]["key"] == "alice/readme.txt"
    assert files[0]["size"] == 1024


def test_list_folder_excludes_prefix_placeholder(mock_boto):
    """S3 sometimes stores a zero-byte object at the prefix itself — exclude it."""
    dt = datetime(2024, 1, 1)
    mock_boto.get_paginator.return_value.paginate.return_value = [
        _make_page(
            files=[
                {"Key": "alice/", "Size": 0, "LastModified": dt},
                {"Key": "alice/file.txt", "Size": 500, "LastModified": dt},
            ]
        )
    ]

    client = S3Client(TEST_CONFIG)
    _, files = client.list_folder("alice/")

    keys = [f["key"] for f in files]
    assert "alice/" not in keys
    assert "alice/file.txt" in keys


def test_list_folder_handles_empty_result(mock_boto):
    mock_boto.get_paginator.return_value.paginate.return_value = [{}]

    client = S3Client(TEST_CONFIG)
    folders, files = client.list_folder("alice/")

    assert folders == []
    assert files == []


def test_list_folder_spans_multiple_pages(mock_boto):
    dt = datetime(2024, 1, 1)
    mock_boto.get_paginator.return_value.paginate.return_value = [
        _make_page(files=[{"Key": "alice/a.txt", "Size": 1, "LastModified": dt}]),
        _make_page(files=[{"Key": "alice/b.txt", "Size": 2, "LastModified": dt}]),
    ]

    client = S3Client(TEST_CONFIG)
    _, files = client.list_folder("alice/")

    assert len(files) == 2


# ---------------------------------------------------------------------------
# browse_flow
# ---------------------------------------------------------------------------

def test_browse_flow_shows_empty_message_for_new_user(mock_s3_client, capsys):
    from ui.browse import browse_flow

    mock_s3_client.list_folder = MagicMock(return_value=([], []))

    browse_flow(mock_s3_client, "alice")

    assert "nothing uploaded" in capsys.readouterr().out.lower()


def test_browse_flow_quits_on_q(mock_s3_client):
    from ui.browse import browse_flow

    dt = datetime(2024, 1, 1)
    mock_s3_client.list_folder = MagicMock(
        return_value=([], [{"key": "alice/file.txt", "size": 100, "last_modified": dt}])
    )

    with patch("ui.browse.Prompt.ask", return_value="q"):
        browse_flow(mock_s3_client, "alice")  # should not hang or error


def test_browse_flow_navigates_into_subfolder(mock_s3_client):
    from ui.browse import browse_flow

    dt = datetime(2024, 1, 1)

    def list_folder_side_effect(prefix):
        if prefix == "alice/":
            return (["alice/docs/"], [])
        if prefix == "alice/docs/":
            return ([], [{"key": "alice/docs/notes.txt", "size": 50, "last_modified": dt}])
        return ([], [])

    mock_s3_client.list_folder = MagicMock(side_effect=list_folder_side_effect)

    # Select folder [1], then quit [q]
    with patch("ui.browse.Prompt.ask", side_effect=["1", "q"]):
        browse_flow(mock_s3_client, "alice")

    assert mock_s3_client.list_folder.call_count == 2


def test_browse_flow_back_navigation(mock_s3_client):
    from ui.browse import browse_flow

    dt = datetime(2024, 1, 1)

    def list_folder_side_effect(prefix):
        if prefix == "alice/":
            return (["alice/docs/"], [])
        return ([], [{"key": "alice/docs/notes.txt", "size": 50, "last_modified": dt}])

    mock_s3_client.list_folder = MagicMock(side_effect=list_folder_side_effect)

    # Drill into folder [1], go back [b], quit [q]
    with patch("ui.browse.Prompt.ask", side_effect=["1", "b", "q"]):
        browse_flow(mock_s3_client, "alice")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def test_fmt_size_bytes():
    assert _fmt_size(512) == "512 B"


def test_fmt_size_kilobytes():
    assert _fmt_size(2048) == "2.0 KB"


def test_fmt_size_megabytes():
    assert _fmt_size(5 * 1024 * 1024) == "5.0 MB"


def test_fmt_date_formats_correctly():
    dt = datetime(2024, 3, 21, 14, 30)
    assert _fmt_date(dt) == "2024-03-21 14:30"
