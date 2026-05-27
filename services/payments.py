# Stripe checkout and Telegram Stars invoice helpers.
from __future__ import annotations

import asyncio
from typing import Literal

import stripe
from telegram import LabeledPrice

from config.config import (
    BOT_LINK,
    PAYMENT_BOT_CREDITS,
    PAYMENT_IMAGE_CREDITS,
    PAYMENT_IMAGES_CONTENT,
    PAYMENT_IMAGES_EURO_PRICE,
    PAYMENT_IMAGES_STARS_PRICE,
    PAYMENT_MESSAGES_CONTENT,
    PAYMENT_MESSAGES_EURO_PRICE,
    PAYMENT_MESSAGES_STARS_PRICE,
    STRIPE_BOT_NAME,
    STRIPE_LIVE_SECRET_KEY,
)

stripe.api_key = STRIPE_LIVE_SECRET_KEY

ProductKind = Literal["messages", "images"]
PAYMENT_PREFIX = "swy"


def _messages_pack_label() -> str:
    return (PAYMENT_MESSAGES_CONTENT or f"{PAYMENT_BOT_CREDITS} messages").strip()


def _images_pack_label() -> str:
    return (PAYMENT_IMAGES_CONTENT or f"{PAYMENT_IMAGE_CREDITS} images").strip()


def pack_label(product: ProductKind) -> str:
    if product == "images":
        return _images_pack_label()
    return _messages_pack_label()


def pack_amount(product: ProductKind) -> int:
    return PAYMENT_IMAGE_CREDITS if product == "images" else PAYMENT_BOT_CREDITS


def euro_price_cents(product: ProductKind) -> int:
    return PAYMENT_IMAGES_EURO_PRICE if product == "images" else PAYMENT_MESSAGES_EURO_PRICE


def stars_price(product: ProductKind) -> int:
    return PAYMENT_IMAGES_STARS_PRICE if product == "images" else PAYMENT_MESSAGES_STARS_PRICE


def stripe_product_name(product: ProductKind) -> str:
    return f"{STRIPE_BOT_NAME} — {pack_label(product)}"


def payment_metadata(telegram_user_id: str, product: ProductKind) -> dict[str, str]:
    return {
        "bot_name": STRIPE_BOT_NAME,
        "telegram_user_id": str(telegram_user_id),
        "product_type": product,
        "credits": str(pack_amount(product)),
    }


def stars_invoice_payload(telegram_user_id: str, product: ProductKind) -> str:
    return f"{PAYMENT_PREFIX}|stars|{product}|{telegram_user_id}"


def parse_stars_invoice_payload(payload: str) -> tuple[ProductKind, str] | None:
    parts = payload.split("|")
    if len(parts) != 4:
        return None
    prefix, channel, product, telegram_user_id = parts
    if prefix != PAYMENT_PREFIX or channel != "stars":
        return None
    if product not in {"messages", "images"}:
        return None
    if not telegram_user_id:
        return None
    return product, telegram_user_id


def _create_stripe_checkout_session_sync(user_id: str, product: ProductKind):
    metadata = payment_metadata(user_id, product)
    return stripe.checkout.Session.create(
        payment_method_types=["card"],
        metadata=metadata,
        client_reference_id=str(user_id),
        line_items=[{
            "price_data": {
                "currency": "eur",
                "product_data": {
                    "name": stripe_product_name(product),
                },
                "unit_amount": euro_price_cents(product),
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


async def create_stripe_checkout_session(user_id: str, product: ProductKind = "messages"):
    return await asyncio.to_thread(_create_stripe_checkout_session_sync, user_id, product)


def stars_invoice_title(product: ProductKind) -> str:
    if product == "images":
        return f"{STRIPE_BOT_NAME} — image pack"
    return f"{STRIPE_BOT_NAME} — message pack"


def stars_invoice_description(product: ProductKind) -> str:
    return pack_label(product)


def stars_invoice_prices(product: ProductKind) -> list[LabeledPrice]:
    return [LabeledPrice(label=pack_label(product), amount=stars_price(product))]
