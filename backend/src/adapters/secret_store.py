from __future__ import annotations

import boto3


class SecretStore:
    def get(self, secret_id: str) -> str:
        response = boto3.client("secretsmanager").get_secret_value(SecretId=secret_id)
        return str(response["SecretString"])
