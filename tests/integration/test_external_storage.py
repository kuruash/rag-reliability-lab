import io
import uuid

import pytest

from rag_lab.storage_clients import (
    StorageConnectionError,
    create_minio_client,
    create_qdrant_client,
    list_minio_buckets,
    list_qdrant_collections,
)

pytestmark = pytest.mark.integration


def test_qdrant_connectivity_and_collection_listing() -> None:
    client = create_qdrant_client()
    try:
        collections = list_qdrant_collections(client)
    except StorageConnectionError as exc:
        pytest.fail(str(exc))
    finally:
        client.close()

    assert len(collections) == len(set(collections))


def test_minio_object_lifecycle_in_dedicated_bucket() -> None:
    client = create_minio_client()
    bucket_name = f"rag-lab-it-{uuid.uuid4().hex}"
    object_key = "connectivity-check.txt"
    object_data = b"RAG Reliability Lab storage connectivity test"
    bucket_created = False
    object_created = False

    try:
        try:
            list_minio_buckets(client)
            client.create_bucket(Bucket=bucket_name)
            bucket_created = True
            client.put_object(
                Bucket=bucket_name,
                Key=object_key,
                Body=io.BytesIO(object_data),
                ContentType="text/plain",
            )
            object_created = True
            response = client.get_object(Bucket=bucket_name, Key=object_key)
            try:
                assert response["Body"].read() == object_data
            finally:
                response["Body"].close()
            client.delete_object(Bucket=bucket_name, Key=object_key)
            object_created = False
        except StorageConnectionError as exc:
            pytest.fail(str(exc))
    finally:
        if object_created:
            client.delete_object(Bucket=bucket_name, Key=object_key)
        if bucket_created:
            client.delete_bucket(Bucket=bucket_name)
        client.close()
