from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.db import init_db
from backend.app.routers.label import router as label_router
from backend.app.routers.pipeline import router as pipeline_router
from backend.app.routers.pubmed import router as pubmed_router


app = FastAPI(title="Keytruda Safety Signal API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # broaden for local development; tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(label_router, prefix="/api/v1")
app.include_router(pipeline_router, prefix="/api/v1")
app.include_router(pubmed_router, prefix="/api/v1")


@app.on_event("startup")
def _startup() -> None:
    init_db()


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/v1/info")
def info():
    return {
        "name": "keytruda-safety-signal",
        "version": "0.1.0",
        "description": "PubMed to safety signal detection pipeline for pembrolizumab (Keytruda).",
    }


