from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError, NoCredentialsError

from storage.s3_client import S3Client

TEST_CONFIG = {
    "aws_access_key": "fake_key",
    "aws_secret_key": "fake_secret",
    "aws_region": "us-east-1",
    "bucket_name": "test-bucket",
}


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "test"}}, "TestOp")


@pytest.fixture
def mock_boto(monkeypatch):
    mock_instance = MagicMock()
    monkeypatch.setattr("storage.s3_client.boto3.client", lambda *a, **kw: mock_instance)
    return mock_instance


# --- verify_connection ---

def test_verify_connection_returns_true_on_success(mock_boto):
    client = S3Client(TEST_CONFIG)
    assert client.verify_connection() is True
    mock_boto.list_buckets.assert_called_once()


def test_verify_connection_returns_false_on_no_credentials(mock_boto):
    mock_boto.list_buckets.side_effect = NoCredentialsError()
    client = S3Client(TEST_CONFIG)
    assert client.verify_connection() is False


def test_verify_connection_returns_true_on_access_denied(mock_boto):
    # AccessDenied means credentials ARE valid, just restricted
    mock_boto.list_buckets.side_effect = _client_error("AccessDenied")
    client = S3Client(TEST_CONFIG)
    assert client.verify_connection() is True


def test_verify_connection_returns_false_on_other_client_error(mock_boto):
    mock_boto.list_buckets.side_effect = _client_error("SomeOtherError")
    client = S3Client(TEST_CONFIG)
    assert client.verify_connection() is False


# --- ensure_bucket_exists ---

def test_ensure_bucket_exists_does_nothing_when_bucket_found(mock_boto):
    client = S3Client(TEST_CONFIG)
    client.ensure_bucket_exists()
    mock_boto.head_bucket.assert_called_once_with(Bucket="test-bucket")
    mock_boto.create_bucket.assert_not_called()


def test_ensure_bucket_creates_bucket_when_not_found(mock_boto):
    mock_boto.head_bucket.side_effect = _client_error("404")
    client = S3Client(TEST_CONFIG)
    client.ensure_bucket_exists()
    mock_boto.create_bucket.assert_called_once_with(Bucket="test-bucket")


def test_ensure_bucket_uses_location_constraint_outside_us_east_1(mock_boto):
    config = {**TEST_CONFIG, "aws_region": "us-west-2"}
    mock_boto.head_bucket.side_effect = _client_error("404")
    client = S3Client(config)
    client.ensure_bucket_exists()
    mock_boto.create_bucket.assert_called_once_with(
        Bucket="test-bucket",
        CreateBucketConfiguration={"LocationConstraint": "us-west-2"},
    )


def test_ensure_bucket_raises_on_unexpected_error(mock_boto):
    mock_boto.head_bucket.side_effect = _client_error("403")
    client = S3Client(TEST_CONFIG)
    with pytest.raises(ClientError):
        client.ensure_bucket_exists()
