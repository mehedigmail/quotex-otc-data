import os
import time
import importlib.util

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Quotex OTC Data Server",
    version="2.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["GET"],
)


@app.get("/")
async def home():
    return {
        "status": "ok",
        "message": "Quotex OTC Data Server is running",
        "version": "2.1.0"
    }


@app.get("/api/health")
async def health():
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
        "accountMode": "DEMO",
        "tradingEnabled": False
    }


@app.get("/api/otc/test")
async def test_otc_connection():

    email = os.getenv("QUOTEX_EMAIL")
    password = os.getenv("QUOTEX_PASSWORD")

    if not email or not password:
        raise HTTPException(
            status_code=400,
            detail="Credentials are not configured"
        )

    client = None

    try:
        from pyquotex.stable_api import Quotex

        client = Quotex(
            email=email,
            password=password,
            lang="en",
            asset_default="EURUSD",
            period_default=60
        )

        # DEMO MODE ONLY
        client.account_is_demo = 1

        connected, message = await client.connect()

        if not connected:
            raise HTTPException(
                status_code=502,
                detail=f"Quotex connection failed: {message}"
            )

        # Get available assets
        assets = await client.get_all_assets()

        if not assets:
            raise HTTPException(
                status_code=502,
                detail="No assets received from Quotex"
            )

        # Find EUR/USD OTC
        otc_asset = next(
            (
                name for name in assets.keys()
                if "eurusd" in name.lower()
                and "otc" in name.lower()
            ),
            None
        )

        if not otc_asset:
            available_otc = [
                name for name in assets.keys()
                if "otc" in name.lower()
            ]

            return {
                "status": "connected",
                "accountMode": "DEMO",
                "tradingEnabled": False,
                "message": "EUR/USD OTC not found",
                "availableOTC": available_otc[:30]
            }

        # Request 1-minute candles
        candles = await client.get_candles(
            otc_asset,
            time.time(),
            3600,
            60
        )

        if not candles:
            raise HTTPException(
                status_code=502,
                detail="Connected, but no candle data received"
            )

        return {
            "status": "success",
            "accountMode": "DEMO",
            "tradingEnabled": False,
            "asset": otc_asset,
            "period": "1 minute",
            "candleCount": len(candles),
            "candles": candles
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Data connection error: {str(error)}"
        )

    finally:
        if client is not None:
            try:
                await client.close()
            except Exception:
                pass
