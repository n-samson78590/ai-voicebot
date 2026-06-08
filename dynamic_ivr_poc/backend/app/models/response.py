from datetime import datetime

from sqlalchemy import Column, DateTime, Enum as SAEnum, Integer, String

from backend.app.db.base import Base
from backend.app.models.enums import CallStatusType, ResponseType


class CallResponse(Base):
    __tablename__ = "response"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(String, nullable=False)
    invitation_id = Column(Integer, nullable=False)
    call_sid = Column(String, unique=True, nullable=True)
    attempt_number = Column(Integer, nullable=True)
    call_status = Column(SAEnum(CallStatusType), nullable=True)
    digit_pressed = Column(String, nullable=True)
    ivr_response = Column(SAEnum(ResponseType), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
