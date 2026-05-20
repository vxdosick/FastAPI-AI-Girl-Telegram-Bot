from sqlalchemy import Column, DateTime, Integer, String, Text, func
from database.database import Base

class User(Base):
    __tablename__ = "users"

    telegram_id = Column(String, primary_key=True, index=True)
    credits = Column(Integer, nullable=False, default=30)
    image_generating = Column(Integer, nullable=False, default=3)
    memory_summary = Column(Text, nullable=False, default="")


class ProcessedPayment(Base):
    __tablename__ = "processed_payments"

    payment_intent_id = Column(String, primary_key=True)
    telegram_id = Column(String, nullable=False, index=True)
    credits = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)