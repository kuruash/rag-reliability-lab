from fastapi import FastAPI

from rag_lab.config import settings

app = FastAPI(title=settings.app_name)


@app.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok"}
