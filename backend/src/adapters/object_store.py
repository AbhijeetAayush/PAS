from __future__ import annotations

import hashlib

import boto3


class ObjectStore:
    def __init__(self, bucket: str) -> None:
        self.bucket = bucket
        self.client = boto3.client("s3")

    def put_pdf(self, key: str, data: bytes) -> str:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType="application/pdf",
        )
        return f"s3://{self.bucket}/{key}"

    def get_bytes(self, uri: str) -> bytes:
        bucket, key = _split(uri)
        response = self.client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _split(uri: str) -> tuple[str, str]:
    path = uri.removeprefix("s3://")
    bucket, _, key = path.partition("/")
    return bucket, key
