# Imports
import logging

import httpx
from telegram import Update
from telegram.ext import ContextTypes

from config.config import (
    DEFAULT_START_IMAGE_CREDITS,
    PAYMENT_BOT_CREDITS,
    PAYMENT_CONTENT,
    PAYMENT_EURO_PRICE,
    SERVER_URL,
)
from repositories.repositories import fetch_or_create_user

log = logging.getLogger(__name__)

CREDITS_BUSY_REPLY = (
    "I couldn’t open the payment page right now, sweetie 🥺 "
    "Please try /credits again in a little while~"
)


def _format_euro_price(cents: int) -> str:
    return f"€{cents / 100:.2f}"


async def credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user = await fetch_or_create_user(user_id)

    pack_label = (PAYMENT_CONTENT or f"{PAYMENT_BOT_CREDITS} messages").strip()
    price_str = _format_euro_price(PAYMENT_EURO_PRICE)
    free_images = max(0, DEFAULT_START_IMAGE_CREDITS)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{SERVER_URL}/create-checkout-session/{user_id}")
            r.raise_for_status()
            data = r.json()
        checkout_url = data["url"]
    except Exception:
        log.exception("Checkout session failed for user_id=%s", user_id)
        await update.message.reply_text(CREDITS_BUSY_REPLY)
        return

    await update.message.reply_text(
        (
            f"<b>{user.credits}</b> messages left, my love… 💬\n"
            f"<b>{user.image_generating}</b> anime pictures left to draw for you… 🎨\n\n"
            f"New users get <b>{free_images}</b> free picture generations to try me out~ ✨\n\n"
            f"<i>I’m still adding a shop for extra picture packs — for now you can only "
            f"buy more messages; picture purchases are coming soon.</i>\n\n"
            f"Want more chat time? 😏\n"
            f"Pay <b>{price_str}</b> — and <b>{PAYMENT_BOT_CREDITS}</b> messages "
            f"will be credited to your balance after payment ({pack_label}) 💬\n\n"
            f'<a href="{checkout_url}">Tap here to buy — get {PAYMENT_BOT_CREDITS} messages 💎</a>'
        ),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
