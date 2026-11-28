from typing import Literal
from uuid import UUID

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from rag_lab.config import settings
from rag_lab.db import get_session
from rag_lab.documents import (
    DocumentNameConflictError,
    UploadPersistenceError,
    UploadStorageError,
    UploadTooLargeError,
    UploadValidationError,
    store_document_upload,
)
from rag_lab.storage_clients import create_minio_client

app = FastAPI(title=settings.app_name)


@app.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok"}


class DocumentUploadResponse(BaseModel):
    document_id: UUID
    version: int
    status: Literal["pending"]


@app.post(
    "/api/v1/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),  # noqa: B008
    session: Session = Depends(get_session),  # noqa: B008
) -> DocumentUploadResponse:
    content = await file.read(settings.max_upload_size_bytes + 1)
    object_storage = None
    try:
        object_storage = create_minio_client()
        stored_document = store_document_upload(
            content=content,
            filename=file.filename,
            content_type=file.content_type,
            session=session,
            object_storage=object_storage,
        )
    except UploadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except UploadValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DocumentNameConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except UploadStorageError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except UploadPersistenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="object storage is unavailable") from exc
    finally:
        if object_storage is not None:
            object_storage.close()

    return DocumentUploadResponse(
        document_id=stored_document.document_id,
        version=stored_document.version,
        status="pending",
    )
