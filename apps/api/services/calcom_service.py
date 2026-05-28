"""
CalcomService — wrapper async sobre Cal.com API v2.

Event Type ID por defecto: 4879655 (cal.com/duendes/consulta, "Demo Gratuita", 30 min).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

_BASE = "https://api.cal.com/v2"
_API_VERSION_SLOTS = "2024-09-04"
_API_VERSION_BOOKINGS = "2024-08-13"


class CalcomError(Exception):
    def __init__(self, message: str, status_code: int | None = None, body: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class CalcomService:
    def __init__(self, api_key: str, event_type_id: int, timeout: float = 15.0) -> None:
        if not api_key:
            raise CalcomError("CALCOM_API_KEY vacío — añádelo al .env de la raíz")
        if not event_type_id:
            raise CalcomError("CALCOM_EVENT_TYPE_ID vacío")
        self._api_key = api_key
        self._event_type_id = event_type_id
        self._timeout = timeout

    def _headers(self, api_version: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "cal-api-version": api_version,
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        url: str,
        *,
        api_version: str,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.request(
                method, url, headers=self._headers(api_version), params=params, json=json
            )
            if resp.status_code >= 400:
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text
                logger.error("Cal.com %s %s → %s: %s", method, url, resp.status_code, body)
                raise CalcomError(
                    f"Cal.com {resp.status_code}: {body}",
                    status_code=resp.status_code,
                    body=body,
                )
            return resp.json()

    async def list_slots(
        self,
        start: datetime,
        end: datetime,
        timezone: str = "Europe/Madrid",
    ) -> list[dict[str, str]]:
        """
        Devuelve slots disponibles entre start y end.
        Respuesta normalizada: [{"start": "...ISO...", "end": "...ISO..."}].
        Cal.com v2 devuelve `{ data: { "YYYY-MM-DD": [{ "start": "ISO" }, ...] } }`.
        """
        params = {
            "eventTypeId": self._event_type_id,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "timeZone": timezone,
        }
        data = await self._request("GET", f"{_BASE}/slots", api_version=_API_VERSION_SLOTS, params=params)

        # Format con el slot duration del event type. Para evento de 30 min:
        slot_minutes = 30

        slots: list[dict[str, str]] = []
        raw = data.get("data") or {}
        # Acepta dos formatos: {date: [...]} o lista plana
        if isinstance(raw, dict):
            for _date, items in raw.items():
                for item in items:
                    start_iso = item.get("start") or item.get("time")
                    if not start_iso:
                        continue
                    try:
                        start_dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                    end_dt = start_dt + timedelta(minutes=slot_minutes)
                    slots.append({"start": start_dt.isoformat(), "end": end_dt.isoformat()})
        elif isinstance(raw, list):
            for item in raw:
                start_iso = item.get("start") or item.get("time")
                if not start_iso:
                    continue
                try:
                    start_dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
                except ValueError:
                    continue
                end_dt = start_dt + timedelta(minutes=slot_minutes)
                slots.append({"start": start_dt.isoformat(), "end": end_dt.isoformat()})
        return slots

    async def create_booking(
        self,
        *,
        slot_start: datetime,
        attendee_name: str,
        attendee_email: str,
        attendee_phone: Optional[str] = None,
        timezone: str = "Europe/Madrid",
        language: str = "es",
        notes: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Crea booking y devuelve dict normalizado con uid, meetingUrl, start, end."""
        attendee: dict[str, Any] = {
            "name": attendee_name,
            "email": attendee_email,
            "timeZone": timezone,
            "language": language,
        }
        if attendee_phone:
            attendee["phoneNumber"] = attendee_phone

        payload: dict[str, Any] = {
            "start": slot_start.isoformat(),
            "eventTypeId": self._event_type_id,
            "attendee": attendee,
        }
        if notes:
            payload["bookingFieldsResponses"] = {"notes": notes}
        if metadata:
            payload["metadata"] = metadata

        data = await self._request(
            "POST", f"{_BASE}/bookings", api_version=_API_VERSION_BOOKINGS, json=payload
        )
        body = data.get("data") or data
        return {
            "booking_uid": body.get("uid") or body.get("bookingUid") or "",
            "booking_id": str(body.get("id") or body.get("uid") or ""),
            "meeting_url": body.get("meetingUrl") or body.get("location") or None,
            "start": body.get("start") or slot_start.isoformat(),
            "end": body.get("end") or (slot_start + timedelta(minutes=30)).isoformat(),
        }
