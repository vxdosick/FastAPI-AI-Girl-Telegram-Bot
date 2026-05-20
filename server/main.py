# Imports
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from telegram import Update
import stripe

_SERVER_DIR = Path(__file__).resolve().parent

# Bot imports
from database.database import dispose_engine, init_db_schema
from repositories.repositories import stripe_credit_topup
from bot.bot import app as tg_app, bot
from services.services import close_redis, init_redis

# Define tokens
from config.config import (
    STRIPE_LIVE_SECRET_KEY,
    STRIPE_LIVE_WEBHOOK_SECRET,
    PAYMENT_CONTENT,
    PAYMENT_EURO_PRICE,
    PAYMENT_BOT_CREDITS,
    BOT_LINK,
    REDIS_URL,
)
stripe.api_key = STRIPE_LIVE_SECRET_KEY

STRIPE_BOT_NAME = "She Wants You"

# Project initialisation
async def init_telegram():
    await bot.initialize()
    await tg_app.initialize()

@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    await init_db_schema()
    await init_redis(REDIS_URL)
    await init_telegram()
    yield
    await close_redis()
    await dispose_engine()

# FastAPI server creating
server = FastAPI(lifespan=lifespan)

templates = Jinja2Templates(directory=str(_SERVER_DIR / "templates"))
server.mount("/static", StaticFiles(directory=str(_SERVER_DIR / "static")), name="static")

# FastAPI Endpoints


@server.get("/privacy-policy", response_class=HTMLResponse)
async def privacy_policy(request: Request):
    return templates.TemplateResponse(
        "privacy_policy.html",
        {"request": request},
    )

def _create_stripe_checkout_session(user_id: str):
    metadata = {
        "bot_name": STRIPE_BOT_NAME,
        "telegram_user_id": user_id,
        "credits": str(PAYMENT_BOT_CREDITS),
    }
    return stripe.checkout.Session.create(
        payment_method_types=["card"],
        metadata=metadata,
        line_items=[{
            "price_data": {
                "currency": "eur",
                "product_data": {
                    "name": PAYMENT_CONTENT,
                },
                "unit_amount": PAYMENT_EURO_PRICE,
            },
            "quantity": 1,
        }],
        mode="payment",
        payment_intent_data={
            "metadata": metadata,
        },
        success_url=f"{BOT_LINK}?start=payment_success",
        cancel_url=f"{BOT_LINK}?start=payment_cancel",
    )


def _retrieve_payment_intent(payment_intent_id: str):
    return stripe.PaymentIntent.retrieve(payment_intent_id)


@server.post("/create-checkout-session/{user_id}")
async def create_checkout(user_id: str):
    try:
        session = await asyncio.to_thread(_create_stripe_checkout_session, user_id)
    except Exception as e:
        print("STRIPE CHECKOUT ERROR:", e)
        raise HTTPException(status_code=502)
    return {"url": session.url}

# Stripe webhook
@server.post("/stripe-webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            STRIPE_LIVE_WEBHOOK_SECRET
        )
    except Exception as e:
        print("STRIPE WEBHOOK ERROR:", e)
        raise HTTPException(status_code=400)

    print("EVENT TYPE:", event["type"])

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        session_meta = session.get("metadata") or {}

        payment_intent_id = session.get("payment_intent")
        if isinstance(payment_intent_id, dict):
            payment_intent_id = payment_intent_id.get("id")
        if not payment_intent_id:
            print("STRIPE WEBHOOK ERROR: NO PAYMENT INTENT")
            return {"status": "ok"}

        pi_meta: dict = {}
        try:
            pi = await asyncio.to_thread(_retrieve_payment_intent, payment_intent_id)
            pi_meta = pi.get("metadata") or {}
        except Exception as e:
            print("STRIPE PAYMENT INTENT ERROR:", e)
            # Fall back to checkout session metadata (same as working bot flow)
            pi_meta = {}

        def _meta(key: str) -> str | None:
            val = pi_meta.get(key) or session_meta.get(key)
            return str(val).strip() if val is not None and str(val).strip() else None

        bot_name = _meta("bot_name")
        if bot_name and bot_name != STRIPE_BOT_NAME:
            print("STRIPE WEBHOOK: SKIP OTHER BOT:", bot_name)
            return {"status": "ok"}

        telegram_user_id = _meta("telegram_user_id")
        try:
            credits = int(_meta("credits") or 0)
        except (TypeError, ValueError):
            credits = 0

        print(
            "STRIPE WEBHOOK: PAYMENT OK:",
            telegram_user_id,
            credits,
            "session_meta=",
            session_meta,
            "pi_meta=",
            pi_meta,
        )

        if not telegram_user_id or credits <= 0:
            print("STRIPE WEBHOOK ERROR: INVALID METADATA")
            return {"status": "ok"}

        added = await stripe_credit_topup(
            str(payment_intent_id),
            str(telegram_user_id),
            credits,
        )
        if not added:
            print("STRIPE WEBHOOK: PAYMENT ALREADY PROCESSED:", payment_intent_id)
        else:
            print("STRIPE WEBHOOK: CREDITS ADDED:", telegram_user_id, credits)

    return {"status": "ok"}

# Telegram webhook
@server.post("/tg-webhook")
async def telegram_webhook(request: Request):
    payload = await request.json()
    update = Update.de_json(payload, bot)
    await tg_app.process_update(update)
    return {"ok": True}
