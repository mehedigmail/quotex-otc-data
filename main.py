import importlib.util
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Quotex OTC Data Server",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {
        "status": "ok",
        "message": "Quotex OTC Data Server is running"
    }

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "server": "running",
        "pyquotexInstalled": (
            importlib.util.find_spec("pyquotex") is not None
        ),
        "dataConnected": False,
        "tradingEnabled": False
    }
