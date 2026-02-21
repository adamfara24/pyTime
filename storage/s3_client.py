from pathlib import Path
from typing import Callable, Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from rich.console import Console

console = Console()


class S3Client:
    def __init__(self, config: dict):
        self.bucket = config["bucket_name"]
        self.region = config["aws_region"]
        self.client = boto3.client(
            "s3",
            aws_access_key_id=config["aws_access_key"],
            aws_secret_access_key=config["aws_secret_key"],
            region_name=config["aws_region"],
        )

    def verify_connection(self) -> bool:
        try:
            self.client.list_buckets()
            return True
        except ClientError as e:
            # An AccessDenied error still means credentials are valid
            if e.response["Error"]["Code"] in ("AccessDenied", "403"):
                return True
            return False
        except NoCredentialsError:
            return False

    def ensure_bucket_exists(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code in ("404", "NoSuchBucket"):
                console.print(
                    f"[yellow]Bucket '[cyan]{self.bucket}[/cyan]' not found. Creating it...[/yellow]"
                )
                try:
                    if self.region == "us-east-1":
                        self.client.create_bucket(Bucket=self.bucket)
                    else:
                        self.client.create_bucket(
                            Bucket=self.bucket,
                            CreateBucketConfiguration={"LocationConstraint": self.region},
                        )
                    console.print(
                        f"[green]Bucket '[cyan]{self.bucket}[/cyan]' created successfully.[/green]"
                    )
                except ClientError as create_error:
                    console.print(f"[red]Failed to create bucket: {create_error}[/red]")
                    raise
            else:
                console.print(f"[red]Error accessing bucket: {e}[/red]")
                raise

    def upload_file(
        self,
        local_path: Path,
        s3_key: str,
        callback: Optional[Callable[[int], None]] = None,
    ) -> None:
        self.client.upload_file(
            str(local_path),
            self.bucket,
            s3_key,
            Callback=callback,
        )
