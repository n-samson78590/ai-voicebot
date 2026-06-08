from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.schemas.ticket import TicketCreateRequest, TicketCreateResponse
from backend.app.services.ticket_service import create_ticket, get_logs, get_ticket_snapshot

router = APIRouter(prefix="/api", tags=["tickets"])


@router.post("/tickets", response_model=TicketCreateResponse)
async def create_ticket_endpoint(payload: TicketCreateRequest, db: Session = Depends(get_db)) -> TicketCreateResponse:
    return create_ticket(payload=payload, db=db)


@router.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return get_ticket_snapshot(ticket_id=ticket_id, db=db)


@router.get("/logs")
async def get_response_logs(ticket_id: str | None = None, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return get_logs(ticket_id=ticket_id, db=db)
