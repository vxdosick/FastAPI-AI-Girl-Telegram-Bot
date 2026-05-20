# Stripe checkout helpers shared by FastAPI and Telegram handlers.
from __future__ import annotations

import asyncio

import stripe

from config.config import (
    BOT_LINK,
    PAYMENT_BOT_CREDITS,
    PAYMENT_CONTENT,
    PAYMENT_EURO_PRICE,
    STRIPE_BOT_NAME,
    STRIPE_LIVE_SECRET_KEY,
)

stripe.api_key = STRIPE_LIVE_SECRET_KEY


def stripe_product_name() -> str:
    pack = (PAYMENT_CONTENT or f"{PAYMENT_BOT_CREDITS} messages").strip()
    return f"{STRIPE_BOT_NAME} — {pack}"


def payment_metadata(telegram_user_id: str) -> dict[str, str]:
    return {
        "bot_name": STRIPE_BOT_NAME,
        "telegram_user_id": str(telegram_user_id),
        "credits": str(PAYMENT_BOT_CREDITS),
    }


def _create_stripe_checkout_session_sync(user_id: str):
    metadata = payment_metadata(user_id)
    return stripe.checkout.Session.create(
        payment_method_types=["card"],
        metadata=metadata,
        client_reference_id=str(user_id),
        line_items=[{
            "price_data": {
                "currency": "eur",
                "product_data": {
                    "name": stripe_product_name(),
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


async def create_stripe_checkout_session(user_id: str):
    return await asyncio.to_thread(_create_stripe_checkout_session_sync, user_id)
