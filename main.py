import os
import time
import logging
import importlib.util

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Quotex OTC Data Server",
    version="2.3.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["GET"],
)


def apply_response_compatibility():
    """
    Compatibility fix for curl_cffi Response.
    PyQuotex expects reason_phrase.
    """
    try:
        from curl_cffi.requests import Response

        if not hasattr(Response, "reason_phrase"):
            Response.reason_phrase = property(
                lambda self: getattr(self, "reason", "")
            )

        logger.info("Response compatibility check completed")

    except Exception:
        logger.exception("Response compatibility setup failed")


apply_response_compatibility()


@app.get("/")
async def home():
    return {
        "status": "ok",
        "message": "Quotex OTC Data Server is running",
        "version": "2.3.0"
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
            logger.error("Quotex connection failed: %s", message)

            raise HTTPException(
                status_code=502,
                detail=f"Quotex connection failed: {message}"
            )

        logger.info("Quotex connection successful")

        assets = await client.get_all_assets()

        if not assets:
            raise HTTPException(
                status_code=502,
                detail="No assets received from Quotex"
            )

        otc_assets = [
            name for name in assets.keys()
            if "otc" in name.lower()
        ]

        eurusd_otc = next(
            (
                name for name in otc_assets
                if "eurusd" in name.lower()
                or "eur/usd" in name.lower()
            ),
            None
        )

        if not eurusd_otc:
            return {
                "status": "connected",
                "accountMode": "DEMO",
                "tradingEnabled": False,
                "totalOTC": len(otc_assets),
                "message": "EUR/USD OTC not found",
                "availableOTC": otc_assets[:30]
            }

        candles = await client.get_candles(
            eurusd_otc,
            time.time(),
            3600,
            60
        )

        if not candles:
            raise HTTPException(
                status_code=502,
                detail="No candle data received"
            )

        return {
            "status": "success",
            "accountMode": "DEMO",
            "tradingEnabled": False,
            "asset": eurusd_otc,
            "period": "1 minute",
            "candleCount": len(candles),
            "candles": candles
        }

    except HTTPException:
        raise

    except Exception as error:
        logger.exception("OTC test failed")

        raise HTTPException(
            status_code=500,
            detail=(
                "OTC test failed: "
                + type(error).__name__
                + ". Check Render logs for details."
            )
        )

    finally:
        if client is not None:
            try:
                await client.close()
            except Exception:
                logger.warning("Client cleanup failed", exc_info=True)
