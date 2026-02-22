import json
import random
import string
from datetime import datetime, timedelta, timezone

from botocore.exceptions import ClientError

from sharing.code_provider import CodeProvider
from storage.s3_client import S3Client

# Stored at a reserved prefix that won't collide with any username namespace
_CODES_KEY = "_system/codes.json"
_CODE_CHARS = string.ascii_uppercase + string.digits
_CODE_LENGTH = 6


class S3CodeProvider(CodeProvider):
    """
    Stores share codes as a JSON file in S3 at _system/codes.json.

    JSON shape:
    {
        "ABC123": {"path": "alice/my-folder/", "created_at": "2024-01-15T10:30:00"},
        ...
    }

    Note: read-modify-write is not atomic. This is acceptable for a single-user
    CLI tool. A multi-user deployment should use DynamoDB conditional writes instead.
    """

    def __init__(self, s3_client: S3Client):
        self._boto = s3_client.client
        self._bucket = s3_client.bucket

    # ------------------------------------------------------------------
    # CodeProvider interface
    # ------------------------------------------------------------------

    def generate_code(self, path: str, expires_hours: int | None = None) -> str:
        codes = self._read_codes()
        code = _unique_code(codes)
        entry: dict = {"path": path, "created_at": datetime.now(timezone.utc).isoformat()}
        if expires_hours is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
            entry["expires_at"] = expires_at.isoformat()
        codes[code] = entry
        self._write_codes(codes)
        return code

    def resolve_code(self, code: str) -> str | None:
        entry = self._read_codes().get(code.upper())
        if entry is None:
            return None
        if "expires_at" in entry:
            expires_at = datetime.fromisoformat(entry["expires_at"])
            if datetime.now(timezone.utc) > expires_at:
                return None  # expired
        return entry["path"]

    def revoke_code(self, code: str) -> None:
        codes = self._read_codes()
        codes.pop(code.upper(), None)
        self._write_codes(codes)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_codes(self) -> dict:
        try:
            response = self._boto.get_object(Bucket=self._bucket, Key=_CODES_KEY)
            return json.loads(response["Body"].read())
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return {}
            raise

    def _write_codes(self, codes: dict) -> None:
        self._boto.put_object(
            Bucket=self._bucket,
            Key=_CODES_KEY,
            Body=json.dumps(codes, indent=2).encode(),
            ContentType="application/json",
        )


def _unique_code(existing: dict) -> str:
    while True:
        code = "".join(random.choices(_CODE_CHARS, k=_CODE_LENGTH))
        if code not in existing:
            return code
