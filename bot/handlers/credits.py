# Imports
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config.config import (
    PAYMENT_BOT_CREDITS,
    PAYMENT_IMAGE_CREDITS,
    PAYMENT_IMAGES_CONTENT,
    PAYMENT_IMAGES_EURO_PRICE,
    PAYMENT_IMAGES_STARS_PRICE,
    PAYMENT_MESSAGES_CONTENT,
    PAYMENT_MESSAGES_EURO_PRICE,
    PAYMENT_MESSAGES_STARS_PRICE,
)
from repositories.repositories import fetch_or_create_user, payment_topup
from services.chat_messages import track_chat_message
from services.payments import (
    ProductKind,
    pack_amount,
    parse_stars_invoice_payload,
    stars_invoice_description,
    stars_invoice_payload,
    stars_invoice_prices,
    stars_invoice_title,
    stars_price,
)

log = logging.getLogger(__name__)

CALLBACK_PAY_STRIPE_MESSAGES = "pay:stripe:messages"
CALLBACK_PAY_STRIPE_IMAGES = "pay:stripe:images"
CALLBACK_PAY_STARS_MESSAGES = "pay:stars:messages"
CALLBACK_PAY_STARS_IMAGES = "pay:stars:images"

STRIPE_UNAVAILABLE_REPLY = (
    "Card payments aren’t available yet, baby 💳 "
    "They’re coming soon — for now you can grab a pack with Stars ⭐"
)
STARS_BUSY_REPLY = (
    "I couldn’t send the Stars invoice right now, sweetie 🥺 "
    "Please try /credits again in a little while~"
)
PAYMENT_SUCCESS_REPLY = (
    "Payment received, baby 💖 Your balance is updated — check /credits anytime~"
)


def _format_euro_price(cents: int) -> str:
    return f"€{cents / 100:.2f}"


def _messages_pack_label() -> str:
    return (PAYMENT_MESSAGES_CONTENT or f"{PAYMENT_BOT_CREDITS} messages").strip()


def _images_pack_label() -> str:
    return (PAYMENT_IMAGES_CONTENT or f"{PAYMENT_IMAGE_CREDITS} images").strip()


def build_credits_text(messages_left: int, images_left: int) -> str:
    messages_pack = _messages_pack_label()
    images_pack = _images_pack_label()
    messages_price = _format_euro_price(PAYMENT_MESSAGES_EURO_PRICE)
    images_price = _format_euro_price(PAYMENT_IMAGES_EURO_PRICE)

    return (
        f"<b>{messages_left}</b> messages left, my love… 💬\n"
        f"<b>{images_left}</b> anime picture generations left… 🎨\n\n"
        f"<b>Messages pack</b> 💬\n"
        f"Pay <b>{messages_price}</b> — you get <b>{messages_pack}</b>\n"
        f"Or <b>{PAYMENT_MESSAGES_STARS_PRICE}</b> ⭐ with Telegram Stars\n\n"
        f"<b>Images pack</b> 🎨\n"
        f"Pay <b>{images_price}</b> — you get <b>{images_pack}</b>\n"
        f"Or <b>{PAYMENT_IMAGES_STARS_PRICE}</b> ⭐ with Telegram Stars\n\n"
        f"Pick a payment method below, baby~"
    )


def credits_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Messages 💳", callback_data=CALLBACK_PAY_STRIPE_MESSAGES),
                InlineKeyboardButton("Images 💳", callback_data=CALLBACK_PAY_STRIPE_IMAGES),
            ],
            [
                InlineKeyboardButton("Messages ⭐", callback_data=CALLBACK_PAY_STARS_MESSAGES),
                InlineKeyboardButton("Images ⭐", callback_data=CALLBACK_PAY_STARS_IMAGES),
            ],
        ]
    )


async def credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user = await fetch_or_create_user(user_id)

    await update.message.reply_text(
        build_credits_text(user.credits, user.image_generating),
        parse_mode="HTML",
        reply_markup=credits_keyboard(),
    )


async def _send_stars_invoice(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    product: ProductKind,
) -> None:
    query = update.callback_query
    user_id = str(query.from_user.id)
    chat_id = query.message.chat_id

    try:
        await context.bot.send_invoice(
            chat_id=chat_id,
            title=stars_invoice_title(product),
            description=stars_invoice_description(product),
            payload=stars_invoice_payload(user_id, product),
            provider_token="",
            currency="XTR",
            prices=stars_invoice_prices(product),
        )
    except Exception:
        log.exception("Stars invoice failed for user_id=%s product=%s", user_id, product)
        await query.message.reply_text(STARS_BUSY_REPLY)


async def credits_pay_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data in {CALLBACK_PAY_STRIPE_MESSAGES, CALLBACK_PAY_STRIPE_IMAGES}:
        await query.message.reply_text(STRIPE_UNAVAILABLE_REPLY)
        return

    handlers = {
        CALLBACK_PAY_STARS_MESSAGES: lambda: _send_stars_invoice(update, context, "messages"),
        CALLBACK_PAY_STARS_IMAGES: lambda: _send_stars_invoice(update, context, "images"),
    }
    handler = handlers.get(query.data or "")
    if handler is None:
        return
    await handler()


async def credits_precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    parsed = parse_stars_invoice_payload(query.invoice_payload or "")
    if parsed is None:
        await query.answer(ok=False, error_message="This invoice is no longer valid. Try /credits again.")
        return

    product, payload_user_id = parsed
    if payload_user_id != str(query.from_user.id):
        await query.answer(ok=False, error_message="This invoice belongs to another account.")
        return

    expected_stars = stars_price(product)
    if query.total_amount != expected_stars or query.currency != "XTR":
        await query.answer(ok=False, error_message="Invoice price changed. Open /credits again.")
        return

    await query.answer(ok=True)


async def credits_successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    if payment is None:
        return

    parsed = parse_stars_invoice_payload(payment.invoice_payload or "")
    if parsed is None:
        log.warning("Unknown stars payload: %s", payment.invoice_payload)
        return

    product, payload_user_id = parsed
    user_id = str(update.effective_user.id)
    if payload_user_id != user_id:
        log.warning("Stars payment user mismatch payload=%s actual=%s", payload_user_id, user_id)
        return

    charge_id = payment.telegram_payment_charge_id
    if not charge_id:
        log.warning("Stars payment without charge id for user_id=%s", user_id)
        return

    amount = pack_amount(product)
    added = await payment_topup(f"stars:{charge_id}", user_id, product, amount)
    if not added:
        log.info("Stars payment already processed: %s", charge_id)
        return

    msg = update.effective_message
    chat = update.effective_chat
    if msg and chat:
        await track_chat_message(user_id, chat.id, msg.message_id)

    await update.message.reply_text(PAYMENT_SUCCESS_REPLY)
