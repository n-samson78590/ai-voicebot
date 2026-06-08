from datetime import datetime

from sqlalchemy import Column, Integer, String

from backend.app.db.base import Base


class CallAttempt(Base):
    __tablename__ = "call_attempt"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(String, unique=True, nullable=False)
    phone_number = Column(String, nullable=False)
    doctor_name = Column(String, nullable=False)
    event_name = Column(String, nullable=False)
    location = Column(String, nullable=False)
    event_date = Column(String, nullable=False)
    event_time = Column(String, nullable=False)
    initiated_by = Column(String, nullable=True)
    created_at = Column(String, default=lambda: datetime.utcnow().isoformat())
