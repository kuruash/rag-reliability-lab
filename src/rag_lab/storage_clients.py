from dataclasses import dataclass

import boto3
from botocore.client import BaseClient
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError
from qdrant_client import QdrantClient

from rag_lab.config import Settings, settings


class StorageConnectionError(ConnectionError):
    """Raised when a configured external storage service cannot be contacted."""


@dataclass
class StorageClients:
    """Reusable external-storage clients with explicit cleanup."""

    qdrant: QdrantClient
    object_storage: BaseClient

    def close(self) -> None:
        self.qdrant.close()
        self.object_storage.close()

    def __enter__(self) -> "StorageClients":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()


def create_qdrant_client(config: Settings = settings) -> QdrantClient:
    """Create a Qdrant client from application settings."""
    return QdrantClient(
        url=config.qdrant_url,
        api_key=config.qdrant_api_key or None,
        timeout=config.qdrant_timeout_seconds,
    )


def create_minio_client(config: Settings = settings) -> BaseClient:
    """Create an S3 client configured for the MinIO endpoint."""
    return boto3.client(
        "s3",
        endpoint_url=config.minio_endpoint,
        aws_access_key_id=config.minio_root_user,
        aws_secret_access_key=config.minio_root_password,
        region_name=config.minio_region,
        use_ssl=config.minio_secure,
        config=BotoConfig(s3={"addressing_style": "path"}),
    )


def create_storage_clients(config: Settings = settings) -> StorageClients:
    """Create both external-storage clients for one application configuration."""
    return StorageClients(
        qdrant=create_qdrant_client(config),
        object_storage=create_minio_client(config),
    )


def list_qdrant_collections(client: QdrantClient) -> list[str]:
    """Verify Qdrant connectivity and return the visible collection names."""
    try:
        return [collection.name for collection in client.get_collections().collections]
    except Exception as exc:
        raise StorageConnectionError(
            "Qdrant connection failed; check RAG_LAB_QDRANT_URL and RAG_LAB_QDRANT_API_KEY"
        ) from exc


def list_minio_buckets(client: BaseClient) -> list[str]:
    """Verify MinIO connectivity and return the visible bucket names."""
    try:
        return [bucket["Name"] for bucket in client.list_buckets().get("Buckets", [])]
    except Exception as exc:
        raise StorageConnectionError(
            "MinIO connection failed; check the endpoint and RAG_LAB_MINIO credentials"
        ) from exc


def ensure_minio_bucket(client: BaseClient, bucket_name: str) -> None:
    """Ensure the configured bucket exists without replacing an existing bucket."""
    try:
        client.head_bucket(Bucket=bucket_name)
        return
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code not in {"404", "NoSuchBucket", "NotFound"}:
            raise StorageConnectionError(
                "MinIO bucket check failed; check the endpoint and credentials"
            ) from exc

    try:
        client.create_bucket(Bucket=bucket_name)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code not in {"BucketAlreadyExists", "BucketAlreadyOwnedByYou"}:
            raise StorageConnectionError("MinIO bucket creation failed") from exc
