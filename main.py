import os
import time
import importlib.util

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Quotex OTC Data Server",
    version="2.0.0"
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
        "credentialsConfigured": bool(
            os.getenv("QUOTEX_EMAIL")
            and os.getenv("QUOTEX_PASSWORD")
        ),
        "tradingEnabled": False,
        "accountMode": "DEMO"
    }


@app.get("/api/otc/test")
async def test_otc_connection():

    email = os.getenv("QUOTEX_EMAIL")
    password = os.getenv("QUOTEX_PASSWORD")

    if not email or not password:
        raise HTTPException(
            status_code=400,
            detail="Quotex credentials are not configured"
        )

    try:
        from pyquotex.stable_api import Quotex

        client = Quotex(
            email=email,
            password=password,
            lang="en"
        )

        # DEMO MODE ONLY
        client.account_is_demo = 1

        try:
            connected, message = await client.connect()

            if not connected:
                raise HTTPException(
                    status_code=502,
                    detail=f"Connection failed: {message}"
                )

            assets = await client.get_instruments()

            asset, asset_status = await client.get_available_asset(
                "EURUSD",
                force_open=True
            )

            candles = await client.get_candles(
                asset,
                time.time(),
                3600,
                60
            )

            return {
                "status": "success",
                "accountMode": "DEMO",
                "tradingEnabled": False,
                "asset": asset,
                "assetStatus": str(asset_status),
                "availableAssets": len(assets),
                "candlePeriod": "1 minute",
                "candleCount": len(candles or []),
                "candles": candles or []
            }

        finally:
            await client.close()

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"OTC data error: {str(error)}"
        )
