# Async Postgres persistence — one AsyncSession per operation (safe under concurrent load).
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from config.config import (
    DEFAULT_START_CREDITS,
    DEFAULT_START_IMAGE_CREDITS,
    OWNER_START_CREDITS,
    OWNER_START_IMAGE_CREDITS,
    OWNER_TELEGRAM_ID,
)
from database.database import async_session_maker
from database.models import ProcessedPayment, User


@dataclass(frozen=True)
class UserDTO:
    telegram_id: str
    credits: int
    image_generating: int
    memory_summary: str


def _is_owner_user(telegram_id: str) -> bool:
    if not OWNER_TELEGRAM_ID:
        return False
    return str(telegram_id).strip() == str(OWNER_TELEGRAM_ID).strip()


def _owner_credits_int() -> int:
    if OWNER_START_CREDITS is None or str(OWNER_START_CREDITS).strip() == "":
        return 10_000
    try:
        return int(OWNER_START_CREDITS)
    except (TypeError, ValueError):
        return 10_000


def _owner_image_credits_int() -> int:
    if OWNER_START_IMAGE_CREDITS is None or str(OWNER_START_IMAGE_CREDITS).strip() == "":
        return 10_000
    try:
        return int(OWNER_START_IMAGE_CREDITS)
    except (TypeError, ValueError):
        return 10_000


def _default_message_credits() -> int:
    try:
        return max(0, int(DEFAULT_START_CREDITS))
    except (TypeError, ValueError):
        return 30


def _default_image_credits() -> int:
    n = DEFAULT_START_IMAGE_CREDITS
    return max(0, int(n)) if n is not None else 3


def _user_to_dto(user: User) -> UserDTO:
    return UserDTO(
        telegram_id=user.telegram_id,
        credits=user.credits,
        image_generating=max(0, user.image_generating or 0),
        memory_summary=user.memory_summary or "",
    )


async def get_user(session: AsyncSession, telegram_id: str) -> User | None:
    r = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return r.scalar_one_or_none()


async def _create_user_row(session: AsyncSession, telegram_id: str) -> User:
    if _is_owner_user(telegram_id):
        user = User(
            telegram_id=telegram_id,
            credits=_owner_credits_int(),
            image_generating=_owner_image_credits_int(),
        )
    else:
        user = User(
            telegram_id=telegram_id,
            credits=_default_message_credits(),
            image_generating=_default_image_credits(),
        )
    session.add(user)
    await session.flush()
    return user


async def get_or_create_user(session: AsyncSession, telegram_id: str) -> User:
    user = await get_user(session, telegram_id)
    if user is not None:
        return user
    return await _create_user_row(session, telegram_id)


async def fetch_or_create_user(telegram_id: str) -> UserDTO:
    async with async_session_maker() as session:
        user = await get_user(session, telegram_id)
        if user is None:
            user = await _create_user_row(session, telegram_id)
            await session.commit()
            await session.refresh(user)
        return _user_to_dto(user)


async def fetch_memory_summary(telegram_id: str) -> str:
    async with async_session_maker() as session:
        user = await get_user(session, telegram_id)
        return (user.memory_summary or "") if user else ""


async def save_memory_summary(telegram_id: str, text: str) -> None:
    async with async_session_maker() as session:
        user = await get_user(session, telegram_id)
        if user is None:
            return
        user.memory_summary = text
        await session.commit()


async def clear_user_stored_memory(telegram_id: str) -> None:
    # Keeps telegram_id, credits, and image_generating; clears long-term summary only.
    async with async_session_maker() as session:
        user = await get_user(session, telegram_id)
        if user is None:
            return
        user.memory_summary = ""
        await session.commit()


# Atomic decrement — avoids lost updates when many requests overlap.
async def deduct_one_credit(telegram_id: str) -> bool:
    async with async_session_maker() as session:
        stmt = (
            update(User)
            .where(User.telegram_id == telegram_id, User.credits >= 1)
            .values(credits=User.credits - 1)
            .returning(User.telegram_id)
        )
        r = await session.execute(stmt)
        ok = r.first() is not None
        if ok:
            await session.commit()
        else:
            await session.rollback()
        return ok


async def deduct_one_image_credit(telegram_id: str) -> bool:
    async with async_session_maker() as session:
        stmt = (
            update(User)
            .where(User.telegram_id == telegram_id, User.image_generating >= 1)
            .values(image_generating=User.image_generating - 1)
            .returning(User.telegram_id)
        )
        r = await session.execute(stmt)
        ok = r.first() is not None
        if ok:
            await session.commit()
        else:
            await session.rollback()
        return ok


# Add Stripe credits once. Returns False if this payment was already processed.
async def stripe_credit_topup(payment_intent_id: str, telegram_user_id: str, credits: int) -> bool:
    async with async_session_maker() as session:
        async with session.begin():
            payment_stmt = (
                pg_insert(ProcessedPayment)
                .values(
                    payment_intent_id=payment_intent_id,
                    telegram_id=telegram_user_id,
                    credits=credits,
                )
                .on_conflict_do_nothing(index_elements=[ProcessedPayment.payment_intent_id])
                .returning(ProcessedPayment.payment_intent_id)
            )
            payment_result = await session.execute(payment_stmt)
            if payment_result.scalar_one_or_none() is None:
                return False

            start_credits = (
                _owner_credits_int()
                if _is_owner_user(telegram_user_id)
                else _default_message_credits()
            )
            start_images = (
                _owner_image_credits_int()
                if _is_owner_user(telegram_user_id)
                else _default_image_credits()
            )
            user_stmt = (
                pg_insert(User)
                .values(
                    telegram_id=telegram_user_id,
                    credits=start_credits,
                    image_generating=start_images,
                    memory_summary="",
                )
                .on_conflict_do_nothing(index_elements=[User.telegram_id])
            )
            await session.execute(user_stmt)

            await session.execute(
                update(User)
                .where(User.telegram_id == telegram_user_id)
                .values(credits=User.credits + credits)
            )
            return True
