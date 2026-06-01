"""
Análisis post-llamada del power dialer.

Flujo:
1. Localiza la grabación en Zadarma (stats de la centralita por extensión + número).
2. Descarga el MP3.
3. Transcribe con Groq Whisper (rápido, barato, buen español).
4. Claude resume la llamada + extrae próximos pasos + redacta un borrador de
   email de seguimiento en voz Duendes (si procede).

Devuelve un dict con transcripción + análisis estructurado, listo para guardar
en Airtable y mostrar en la ficha del dialer.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from services.zadarma_service import ZadarmaService

logger = logging.getLogger(__name__)

GROQ_TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_WHISPER_MODEL = "whisper-large-v3-turbo"
GROQ_LLM_MODEL = "llama-3.3-70b-versatile"


class CallAnalysisError(Exception):
    pass


def _normalize_number(raw: str | int | None) -> str:
    if raw is None:
        return ""
    return str(raw).lstrip("+").replace(" ", "").replace("-", "")


async def find_recording(
    zadarma: ZadarmaService,
    to_number: str,
    *,
    sip_ext: str = "100",
) -> dict[str, Any] | None:
    """Busca la grabación más reciente hacia `to_number` desde la extensión `sip_ext`."""
    stats = await zadarma._request("/v1/statistics/pbx/", {})
    target = _normalize_number(to_number)
    calls = stats.get("stats", []) if isinstance(stats, dict) else []
    matches = [
        c
        for c in calls
        if _normalize_number(c.get("destination")) == target
        and str(c.get("is_recorded")) == "true"
    ]
    if not matches:
        return None
    matches.sort(key=lambda c: c.get("callstart", ""), reverse=True)
    call = matches[0]
    link_resp = await zadarma._request(
        "/v1/pbx/record/request/", {"call_id": call["call_id"], "lifetime": "3600"}
    )
    url = link_resp.get("link") if isinstance(link_resp, dict) else None
    if not url:
        return None
    return {
        "call_id": call["call_id"],
        "url": url,
        "seconds": call.get("seconds"),
        "callstart": call.get("callstart"),
    }


async def _transcribe_groq(audio_bytes: bytes, groq_api_key: str) -> str:
    """Transcribe audio con Groq Whisper (API compatible OpenAI)."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            GROQ_TRANSCRIBE_URL,
            headers={"Authorization": f"Bearer {groq_api_key}"},
            files={"file": ("call.mp3", audio_bytes, "audio/mpeg")},
            data={"model": GROQ_WHISPER_MODEL, "language": "es", "response_format": "text"},
        )
        if resp.status_code >= 400:
            raise CallAnalysisError(f"Groq transcribe {resp.status_code}: {resp.text}")
        return resp.text.strip()


_ANALYSIS_PROMPT = """\
Eres el SDR de Duendes (duendes.net), consultora de implantación de IA para pymes \
españolas. Acabas de hacer una llamada de prospección en frío. Te paso la \
transcripción. Analízala y devuelve SOLO un JSON válido (sin texto alrededor) con \
esta forma exacta:

{{
  "resumen": "2-3 frases de qué pasó en la llamada",
  "puntos_clave": ["dato relevante 1", "dato relevante 2"],
  "proximos_pasos": ["acción concreta 1", "acción concreta 2"],
  "necesita_email": true|false,
  "email_asunto": "asunto si necesita_email, si no cadena vacía",
  "email_cuerpo": "borrador del email de seguimiento si necesita_email, si no cadena vacía"
}}

Reglas del email (si aplica):
- Español peninsular, tuteo, directo y humano. Nada de "en el mundo actual", \
nada de corporativismo, sin emojis.
- Engancha con lo concreto que se habló en la llamada.
- 60-110 palabras. Una sola llamada a la acción.

Contexto de la llamada:
- Prospecto: {prospect_name}
- Resultado/disposición registrada: {disposition}

Transcripción:
\"\"\"
{transcript}
\"\"\"
"""


async def _analyze_with_groq(
    transcript: str,
    groq_api_key: str,
    *,
    prospect_name: str,
    disposition: str,
) -> dict[str, Any]:
    prompt = _ANALYSIS_PROMPT.format(
        prospect_name=prospect_name or "(desconocido)",
        disposition=disposition or "(sin registrar)",
        transcript=transcript,
    )
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            GROQ_CHAT_URL,
            headers={"Authorization": f"Bearer {groq_api_key}"},
            json={
                "model": GROQ_LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.4,
                "max_tokens": 1500,
            },
        )
        if resp.status_code >= 400:
            raise CallAnalysisError(f"Groq chat {resp.status_code}: {resp.text}")
        text = resp.json()["choices"][0]["message"]["content"].strip()
    try:
        return json.loads(text)
    except (ValueError, TypeError) as exc:
        logger.warning("Groq LLM no devolvió JSON válido: %s", exc)
        return {
            "resumen": text[:500],
            "puntos_clave": [],
            "proximos_pasos": [],
            "necesita_email": False,
            "email_asunto": "",
            "email_cuerpo": "",
        }


async def analyze_call(
    *,
    zadarma: ZadarmaService,
    groq_api_key: str,
    to_number: str,
    prospect_name: str = "",
    disposition: str = "",
    sip_ext: str = "100",
) -> dict[str, Any]:
    """Orquesta el análisis completo de la última llamada a `to_number`."""
    if not groq_api_key:
        raise CallAnalysisError("GROQ_API_KEY vacía — añádela al .env")

    rec = await find_recording(zadarma, to_number, sip_ext=sip_ext)
    if not rec:
        return {"ok": False, "reason": "no se encontró grabación para ese número"}

    async with httpx.AsyncClient(timeout=120.0) as client:
        audio_resp = await client.get(rec["url"])
        if audio_resp.status_code >= 400:
            raise CallAnalysisError(f"Descarga grabación {audio_resp.status_code}")
        audio_bytes = audio_resp.content

    transcript = await _transcribe_groq(audio_bytes, groq_api_key)
    analysis = await _analyze_with_groq(
        transcript, groq_api_key, prospect_name=prospect_name, disposition=disposition
    )

    return {
        "ok": True,
        "recording_url": rec["url"],
        "call_id": rec["call_id"],
        "seconds": rec.get("seconds"),
        "callstart": rec.get("callstart"),
        "transcript": transcript,
        "analysis": analysis,
    }
