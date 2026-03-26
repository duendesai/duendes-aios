"""
Duendes AIOS — COO Task Management Module
Reads/writes tasks directly to Airtable (Tareas table, tblChzXpWi6hEpqfw).

Airtable fields:
  Título           (Single line text)
  Estado           (Single select: Pendiente, Completada)
  Prioridad        (Single select: High, Medium, Low)
  Categoría        (Single select: Sales, Content, Ops, Admin)
  Fecha vencimiento (Date, YYYY-MM-DD)
  Fecha completada  (Date, YYYY-MM-DD)
  Fecha creación    (Date, YYYY-MM-DD)
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from airtable_client import AirtableClient, AirtableError, TABLE_TASKS, get_client

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
logger = logging.getLogger("duendes-bot.coo_tasks")

# Re-export for bot.py compatibility
EngramConnectionError = AirtableError
EngramDataError = AirtableError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_PRIORITIES: set[str] = {"high", "medium", "low"}
VALID_CATEGORIES: set[str] = {"sales", "content", "ops", "admin"}

_AT_ESTADO_MAP: dict[str, str] = {"pendiente": "pending", "completada": "completed"}
_AT_PRIORIDAD_MAP: dict[str, str] = {"high": "high", "medium": "medium", "low": "low"}
_AT_CATEGORIA_MAP: dict[str, str] = {
    "sales": "sales", "content": "content", "ops": "ops", "admin": "admin"
}

_ESTADO_TO_AT: dict[str, str] = {"pending": "Pendiente", "completed": "Completada"}
_PRIORIDAD_TO_AT: dict[str, str] = {"high": "High", "medium": "Medium", "low": "Low"}
_CATEGORIA_TO_AT: dict[str, str] = {
    "sales": "Sales", "content": "Content", "ops": "Ops", "admin": "Admin"
}


def _f(fields: dict, name: str, default: str = "") -> str:
    v = fields.get(name, default)
    if v is None:
        return default
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    return str(v).strip()


def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Task:
    id: str                    # Airtable record ID
    title: str
    status: str                # pending | completed
    priority: str              # high | medium | low
    category: str              # sales | content | ops | admin
    created_at: str            # YYYY-MM-DD
    completed_at: str | None   # YYYY-MM-DD or None
    due_date: str | None       # YYYY-MM-DD or None

    @classmethod
    def from_airtable(cls, record: dict) -> "Task":
        f = record.get("fields", {})
        raw_estado = _f(f, "Estado").lower()
        raw_prioridad = _f(f, "Prioridad").lower()
        raw_categoria = _f(f, "Categoría").lower()
        completed = _f(f, "Fecha completada") or None
        due = _f(f, "Fecha vencimiento") or None
        created = _f(f, "Fecha creación") or record.get("createdTime", "")[:10]
        return cls(
            id=record["id"],
            title=_f(f, "Título"),
            status=_AT_ESTADO_MAP.get(raw_estado, "pending"),
            priority=_AT_PRIORIDAD_MAP.get(raw_prioridad, "medium"),
            category=_AT_CATEGORIA_MAP.get(raw_categoria, "ops"),
            created_at=created,
            completed_at=completed if completed else None,
            due_date=due if due else None,
        )

    def to_airtable_fields(self) -> dict[str, Any]:
        fields: dict[str, Any] = {}
        if self.title:
            fields["Título"] = self.title
        fields["Estado"] = _ESTADO_TO_AT.get(self.status, "Pendiente")
        fields["Prioridad"] = _PRIORIDAD_TO_AT.get(self.priority, "Medium")
        fields["Categoría"] = _CATEGORIA_TO_AT.get(self.category, "Ops")
        if self.due_date:
            fields["Fecha vencimiento"] = self.due_date
        if self.completed_at:
            fields["Fecha completada"] = self.completed_at[:10]
        if self.created_at:
            fields["Fecha creación"] = self.created_at[:10]
        return fields


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _priority_sort_key(p: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(p, 1)


def _sort_tasks(tasks: list[Task]) -> list[Task]:
    return sorted(
        tasks,
        key=lambda t: (
            0 if t.status == "pending" else 1,
            _priority_sort_key(t.priority),
            t.created_at,
        ),
    )


def _is_overdue(task: Task) -> bool:
    if not task.due_date:
        return False
    return task.due_date < _today_iso()


# ---------------------------------------------------------------------------
# CRUD — async (bot.py)
# ---------------------------------------------------------------------------

async def add_task(
    title: str,
    priority: str = "medium",
    category: str = "ops",
    due_date: str | None = None,
) -> Task:
    if priority not in VALID_PRIORITIES:
        priority = "medium"
    if category not in VALID_CATEGORIES:
        category = "ops"
    at = get_client()
    task = Task(
        id="",
        title=title.strip(),
        status="pending",
        priority=priority,
        category=category,
        created_at=_today_iso(),
        completed_at=None,
        due_date=due_date,
    )
    record = await at.create_record(TABLE_TASKS, task.to_airtable_fields())
    return Task.from_airtable(record)


async def list_tasks(
    status: str | None = None,
    category: str | None = None,
    priority: str | None = None,
) -> list[Task]:
    at = get_client()
    formula = "{Estado}='Pendiente'" if status == "pending" else None
    if status == "completed":
        formula = "{Estado}='Completada'"
    records = await at.list_records(TABLE_TASKS, filter_formula=formula)
    tasks = [Task.from_airtable(r) for r in records if r.get("fields", {}).get("Título")]
    if category:
        tasks = [t for t in tasks if t.category == category]
    if priority:
        tasks = [t for t in tasks if t.priority == priority]
    return _sort_tasks(tasks)


async def complete_task(record_id: str) -> Task | None:
    at = get_client()
    try:
        record = await at.update_record(
            TABLE_TASKS,
            record_id,
            {"Estado": "Completada", "Fecha completada": _today_iso()},
        )
        return Task.from_airtable(record)
    except Exception as exc:
        if "404" in str(exc):
            return None
        raise


async def get_pending_tasks() -> list[Task]:
    tasks = await list_tasks(status="pending")
    return sorted(
        tasks,
        key=lambda t: (
            _priority_sort_key(t.priority),
            0 if _is_overdue(t) else 1,
            t.created_at,
        ),
    )


# ---------------------------------------------------------------------------
# Brief sync helper
# ---------------------------------------------------------------------------

def get_pending_for_brief_sync() -> str:
    at = get_client()
    try:
        records = at.list_records_sync(TABLE_TASKS, filter_formula="{Estado}='Pendiente'")
        tasks = [Task.from_airtable(r) for r in records if r.get("fields", {}).get("Título")]
    except Exception as exc:
        logger.error("brief coo sync error: %s", exc)
        return "No hay tareas pendientes."

    if not tasks:
        return "No hay tareas pendientes."

    tasks = sorted(
        tasks,
        key=lambda t: (_priority_sort_key(t.priority), 0 if _is_overdue(t) else 1, t.created_at),
    )
    groups: dict[str, list[Task]] = {"high": [], "medium": [], "low": []}
    for t in tasks:
        groups.setdefault(t.priority, []).append(t)

    lines: list[str] = []
    for pk, emoji, label in [("high", "🔴", "Alta"), ("medium", "🟡", "Media"), ("low", "🟢", "Baja")]:
        group = groups.get(pk, [])
        if not group:
            continue
        lines.append(f"{emoji} {label}:")
        for t in group:
            due = f" (vence: {t.due_date})" if t.due_date else ""
            lines.append(f"- {t.title} [{t.category}]{due}")
    return "\n".join(lines).rstrip()


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def format_task_list(tasks: list[Task], title: str = "Tareas") -> str:
    if not tasks:
        return "No hay tareas pendientes."
    groups: dict[str, list[Task]] = {"high": [], "medium": [], "low": []}
    for t in tasks:
        groups.setdefault(t.priority, []).append(t)
    lines = [f"*{title}*\n"]
    for pk, emoji, label in [("high", "🔴", "Alta"), ("medium", "🟡", "Media"), ("low", "🟢", "Baja")]:
        group = groups.get(pk, [])
        if not group:
            continue
        lines.append(f"{emoji} *{label}*")
        for i, t in enumerate(group, 1):
            due = f" _(vence: {t.due_date})_" if t.due_date else ""
            lines.append(f"  #{t._display_id if hasattr(t, '_display_id') else '?'} {t.title} [{t.category}]{due}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_task_added(task: Task) -> str:
    label = {"high": "alta", "medium": "media", "low": "baja"}.get(task.priority, task.priority)
    due = f" | vence: {task.due_date}" if task.due_date else ""
    return f"Tarea creada: {task.title} [{label}/{task.category}{due}]"


def format_task_completed(task: Task) -> str:
    return f"Tarea completada: {task.title}"


# ---------------------------------------------------------------------------
# Natural language detection
# ---------------------------------------------------------------------------

_LIST_PATTERNS = [
    re.compile(r"qu[eé]\s+tengo\s+pendiente", re.IGNORECASE),
    re.compile(r"qu[eé]\s+tareas\s+tengo", re.IGNORECASE),
    re.compile(r"\bmis\s+tareas\b", re.IGNORECASE),
    re.compile(r"\btareas\s+pendientes\b", re.IGNORECASE),
    re.compile(r"qu[eé]\s+me\s+falta", re.IGNORECASE),
    re.compile(r"qu[eé]\s+queda\s+por\s+hacer", re.IGNORECASE),
]

_ADD_PATTERNS = [
    re.compile(r"(?:a[nñ]ade|agrega[rs]?|nueva|agrega)\s+tarea[:\s]+(.+)", re.IGNORECASE),
    re.compile(r"recuerd[aá]me(?:\s+que)?\s+(.+)", re.IGNORECASE),
    re.compile(r"apunta[:\s]+(.+)", re.IGNORECASE),
    re.compile(r"tengo\s+que\s+(.+)", re.IGNORECASE),
]

_COMPLETE_PATTERNS = [
    re.compile(r"tarea\s+hecha\s+(\d+)", re.IGNORECASE),
    re.compile(r"complet[eé]\s+(?:la\s+)?tarea\s+(\d+)", re.IGNORECASE),
    re.compile(r"termin[eé]\s+(?:la\s+)?(\d+)", re.IGNORECASE),
    re.compile(r"hecho\s+(?:el\s+)?(\d+)", re.IGNORECASE),
    re.compile(r"listo\s+(?:el\s+)?(\d+)", re.IGNORECASE),
    re.compile(r"ya\s+hice\s+(?:la\s+)?(\d+)", re.IGNORECASE),
]

_PENDING_PATTERNS = [
    re.compile(r"qu[eé]\s+tengo\s+para\s+hoy", re.IGNORECASE),
    re.compile(r"tareas\s+(?:para\s+hoy|urgentes)", re.IGNORECASE),
]


def detect_task_intent(text: str) -> tuple[str, dict] | None:
    text = text.strip()
    for p in _LIST_PATTERNS:
        if p.search(text):
            return ("list", {})
    for p in _PENDING_PATTERNS:
        if p.search(text):
            return ("pending", {})
    for p in _ADD_PATTERNS:
        m = p.search(text)
        if m:
            title = m.group(1).strip()
            if title:
                return ("add", {"title": title})
    for p in _COMPLETE_PATTERNS:
        m = p.search(text)
        if m:
            try:
                return ("complete", {"task_display_n": int(m.group(1))})
            except (ValueError, IndexError):
                pass
    return None


def parse_priority_and_category(text: str) -> tuple[str, str, str]:
    priority = "medium"
    category = "ops"
    title = text.strip()
    pm = re.match(r"^(alta|urgente|media|baja):\s*", title, re.IGNORECASE)
    if pm:
        priority = {"alta": "high", "urgente": "high", "media": "medium", "baja": "low"}[pm.group(1).lower()]
        title = title[pm.end():]
    for cat in VALID_CATEGORIES:
        p = re.compile(rf"#\b{cat}\b", re.IGNORECASE)
        if p.search(title):
            category = cat
            title = p.sub("", title).strip()
            break
    return (title.strip(), priority, category)
