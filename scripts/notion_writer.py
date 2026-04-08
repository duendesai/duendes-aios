"""
notion_writer.py — Escribe automáticamente en Notion desde el AIOS.

Bases de datos:
  - Tareas del AIOS  → registra tareas completadas por los agentes
  - Briefs Diarios   → guarda el brief diario como página
  - Wiki de Clientes → crea entrada cuando se cierra un deal
"""

import os
import re
import httpx
import logging
from datetime import date, datetime
from typing import Optional

logger = logging.getLogger("duendes-notion")

NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_VERSION = "2022-06-28"

# IDs de las bases de datos (obtenidos via MCP)
DB_TAREAS_AIOS   = os.getenv("NOTION_DB_TAREAS",      "2a86f01b-23b5-835d-874d-8181d2b4714e")
DB_PROYECTOS     = os.getenv("NOTION_DB_PROYECTOS",   "3f36f01b-23b5-8374-97de-0132cd62e884")
PAGE_BRIEFS      = os.getenv("NOTION_PAGE_BRIEFS",    "32f6f01b-23b5-8185-8256-d8113791de2f")
DB_WIKI_CLIENTES = os.getenv("NOTION_DB_AREAS",       "c0f6f01b-23b5-8359-bc5c-8105ba55ff27")
PAGE_BORRADORES  = os.getenv("NOTION_PAGE_BORRADORES","32f6f01b-23b5-8195-ab6a-ebd241bc5b9b")

# IDs de los departamentos en la BD Departamentos (para vincular proyectos)
DEPT_AREA_IDS = {
    "cmo": "b096f01b-23b5-8372-b46e-01f5eee13d63",  # Marketing
    "sdr": "4746f01b-23b5-83d6-9394-811b9c7515e3",  # Captación
    "ae":  "3a36f01b-23b5-83c4-a7ae-017b695303b5",  # Ventas
    "coo": "0a86f01b-23b5-8206-aeac-81438ce9dc8b",  # Operaciones
    "cfo": "8446f01b-23b5-82ce-a484-01020171d246",  # Finanzas
    "cs":  "9db6f01b-23b5-83ab-a9df-81458ee55cb8",  # Clientes
}

# Mapa canal Slack → nombre legible para Notion
DEPT_DISPLAY = {
    "orchestrator": "Orquestador",
    "cmo":          "Marketing",
    "sdr":          "Captación",
    "ae":           "Ventas",
    "coo":          "Operaciones",
    "cfo":          "Finanzas",
    "cs":           "Clientes",
}

_headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": NOTION_VERSION,
    "Content-Type": "application/json",
}


async def _post(url: str, payload: dict) -> Optional[dict]:
    if not NOTION_TOKEN:
        logger.warning("NOTION_TOKEN no configurado — skipping Notion write")
        return None
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, headers=_headers, json=payload)
        if r.status_code not in (200, 201):
            logger.error("Notion API error %s: %s", r.status_code, r.text[:200])
            return None
        return r.json()


async def log_tarea(
    tarea: str,
    dept: str,
    resultado: str = "",
    iniciado_por: str = "AIOS automático",
    canal_slack: str = "",
) -> bool:
    """Registra una tarea completada en la base de datos Tareas del AIOS."""
    dept_display = DEPT_DISPLAY.get(dept, dept.title())
    payload = {
        "parent": {"database_id": DB_TAREAS_AIOS},
        "properties": {
            "Nombre": {
                "title": [{"text": {"content": f"[{dept_display}] {tarea}"}}]
            },
            "Status": {
                "status": {"name": "Completed"}
            },
            "Fecha": {
                "date": {"start": date.today().isoformat()}
            },
            "Prioridad": {
                "select": {"name": "Media"}
            },
        }
    }
    if resultado:
        payload["properties"]["Descripción"] = {
            "rich_text": [{"text": {"content": resultado[:2000]}}]
        }

    result = await _post("https://api.notion.com/v1/pages", payload)
    if result:
        logger.info("Notion tarea registrada: %s (%s)", tarea[:50], dept_display)
        return True
    return False


async def crear_brief_diario(fecha: str, contenido: str) -> bool:
    """Crea una página de brief diario dentro de la sección Briefs Diarios."""
    titulo = f"Brief {fecha}"
    # Crear página hija dentro de la página Briefs Diarios
    payload = {
        "parent": {"page_id": PAGE_BRIEFS},
        "properties": {
            "title": [{"text": {"content": titulo}}]
        },
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": contenido[:2000]}}]
                }
            }
        ]
    }
    result = await _post("https://api.notion.com/v1/pages", payload)
    if result:
        logger.info("Notion brief creado: %s", titulo)
        return True
    return False


async def crear_wiki_cliente(
    nombre: str,
    sector: str = "",
    contacto: str = "",
    telefono: str = "",
    email: str = "",
    mrr: float = 0.0,
    tipo_agente: str = "",
) -> bool:
    """Crea una entrada en Wiki de Clientes cuando se cierra un deal."""
    # Sectores válidos en Notion
    sectores_validos = ["Fisioterapia", "Dental", "Estética", "Abogados", "Gestoría", "Otro"]
    sector_notion = sector if sector in sectores_validos else "Otro"

    payload = {
        "parent": {"page_id": DB_WIKI_CLIENTES},
        "properties": {
            "title": [{"text": {"content": nombre}}]
        },
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {
                        "content": f"Cliente: {nombre}\nSector: {sector}\nContacto: {contacto}\nEmail: {email}\nTel: {telefono}\nMRR: {mrr}€\nAgente: {tipo_agente}\nFecha inicio: {date.today().isoformat()}"
                    }}]
                }
            }
        ]
    }
    result = await _post("https://api.notion.com/v1/pages", payload)
    if result:
        logger.info("Notion wiki cliente creado: %s", nombre)
        return True
    return False


async def agregar_nota_a_proyecto(page_id: str, titulo: str, contenido: str) -> Optional[str]:
    """
    Añade una sub-página (nota) dentro de un proyecto Notion existente.
    Devuelve la URL de la nota creada, o None si falla.
    """
    chunk_size = 1990
    chunks = [contenido[i:i + chunk_size] for i in range(0, len(contenido), chunk_size)]
    children = [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": chunk}}]
            }
        }
        for chunk in chunks
    ]
    payload = {
        "parent": {"page_id": page_id},
        "properties": {
            "title": [{"text": {"content": titulo}}]
        },
        "children": children[:100],
    }
    result = await _post("https://api.notion.com/v1/pages", payload)
    if result:
        url = result.get("url", "")
        logger.info("Notion nota añadida al proyecto %s → %s", page_id, url)
        return url
    return None


async def _crear_tarea_en_proyecto(
    tarea: str,
    proyecto_id: str,
    dept: str = "",
) -> bool:
    """Crea una Tarea en DB_TAREAS_AIOS vinculada al proyecto via relación."""
    dept_display = DEPT_DISPLAY.get(dept, dept.title()) if dept else ""
    nombre = f"[{dept_display}] {tarea}" if dept_display else tarea

    payload = {
        "parent": {"database_id": DB_TAREAS_AIOS},
        "properties": {
            "Nombre": {
                "title": [{"text": {"content": nombre[:2000]}}]
            },
            "Status": {
                "status": {"name": "En proceso"}
            },
            "Fecha": {
                "date": {"start": date.today().isoformat()}
            },
            "Prioridad": {
                "select": {"name": "Media"}
            },
            "Proyecto": {
                "relation": [{"id": proyecto_id}]
            },
        }
    }
    result = await _post("https://api.notion.com/v1/pages", payload)
    if result:
        logger.info("Notion tarea creada: %s → proyecto %s", tarea[:50], proyecto_id)
        return True
    return False


async def _actualizar_status_proyecto(page_id: str, status: str) -> bool:
    """Actualiza el Status de un proyecto en DB_PROYECTOS."""
    payload = {"properties": {"Status": {"status": {"name": status}}}}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.patch(
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=_headers,
            json=payload,
        )
        return r.status_code in (200, 201)


def _parse_structured_response(contenido: str) -> dict:
    """
    Parsea respuesta con secciones ## TAREAS / ## NOTAS / ## DOCS / ## PENDIENTE OSCAR.
    Devuelve {"intro", "tareas", "notas", "docs", "pendiente_oscar"}
    """
    sections: dict = {"intro": "", "tareas": [], "notas": "", "docs": [], "pendiente_oscar": []}

    parts = re.split(
        r'^##\s+(TAREAS|NOTAS|DOCS|PENDIENTE OSCAR|PENDIENTE)\s*$',
        contenido,
        flags=re.MULTILINE | re.IGNORECASE,
    )

    if len(parts) == 1:
        sections["intro"] = contenido
        return sections

    sections["intro"] = parts[0].strip()

    for i in range(1, len(parts), 2):
        if i + 1 >= len(parts):
            break
        section_name = parts[i].upper().strip()
        section_content = parts[i + 1].strip()

        if section_name == "TAREAS":
            for line in section_content.split("\n"):
                line = line.strip()
                if re.match(r'^[-*]\s*\[[ x]\]', line, re.IGNORECASE):
                    task_title = re.sub(r'^[-*]\s*\[[ x]\]\s*', '', line).strip()
                    if task_title:
                        sections["tareas"].append(task_title)
        elif section_name == "NOTAS":
            sections["notas"] = section_content
        elif section_name == "DOCS":
            for line in section_content.split("\n"):
                line = line.strip()
                if line.startswith("- ") or line.startswith("* "):
                    sections["docs"].append(line[2:].strip())
        elif section_name in ("PENDIENTE OSCAR", "PENDIENTE"):
            for line in section_content.split("\n"):
                line = line.strip()
                if re.match(r'^[-*]', line):
                    item = re.sub(r'^[-*]\s*\[[ x]\]?\s*', '', line).strip()
                    if item:
                        sections["pendiente_oscar"].append(item)

    return sections


async def crear_proyecto_estructurado(
    titulo: str,
    contenido: str,
    dept: str = "",
) -> Optional[dict]:
    """
    Crea un Proyecto en Notion con contenido estructurado.
    Si el contenido tiene secciones ## TAREAS / ## NOTAS / ## DOCS:
    - Crea el proyecto con el contenido completo como cuerpo
    - Crea registros individuales en DB_TAREAS_AIOS vinculados al proyecto
    Devuelve {"url": str, "id": str} o None.
    """
    parsed = _parse_structured_response(contenido)
    has_structure = bool(parsed["tareas"])

    # Crear el proyecto primero con el contenido completo
    project = await crear_proyecto(titulo, contenido, dept)
    if not project:
        return None

    # Si hay tareas estructuradas, crearlas como registros en la BD Tareas
    if has_structure:
        page_id = project["id"]
        for task_title in parsed["tareas"]:
            await _crear_tarea_en_proyecto(task_title, page_id, dept)
        logger.info(
            "Notion proyecto estructurado: %d tareas vinculadas al proyecto %s",
            len(parsed["tareas"]),
            page_id,
        )

    return project


async def crear_proyecto(titulo: str, contenido: str, dept: str = "") -> Optional[dict]:
    """
    Crea un Proyecto en la base de datos Proyectos con Status=Inbox.
    Vincula el departamento correspondiente y guarda el plan completo como contenido.
    Devuelve {"url": str, "id": str}, o None si falla.
    """
    dept_display = DEPT_DISPLAY.get(dept, dept.title()) if dept else ""
    nombre = f"[{dept_display}] {titulo}" if dept_display else titulo

    # Dividir contenido en bloques de 2000 chars (límite Notion)
    chunk_size = 1990
    chunks = [contenido[i:i + chunk_size] for i in range(0, len(contenido), chunk_size)]
    children = [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": chunk}}]
            }
        }
        for chunk in chunks
    ]

    properties: dict = {
        "Name": {
            "title": [{"text": {"content": nombre}}]
        },
        "Status": {
            "status": {"name": "Inbox"}
        },
        "Start Date": {
            "date": {"start": date.today().isoformat()}
        },
    }

    # Vincular departamento si existe en el mapa
    area_id = DEPT_AREA_IDS.get(dept)
    if area_id:
        properties["Departamento"] = {
            "relation": [{"id": area_id}]
        }

    payload = {
        "parent": {"database_id": DB_PROYECTOS},
        "properties": properties,
        "children": children[:100],
    }
    result = await _post("https://api.notion.com/v1/pages", payload)
    if result:
        url = result.get("url", "")
        page_id = result.get("id", "")
        logger.info("Notion proyecto creado: %s → %s", nombre, url)
        return {"url": url, "id": page_id}
    return None


async def ejecutar_proyecto(
    titulo: str,
    contenido: str,
    dept: str = "",
) -> Optional[dict]:
    """
    Modo ejecución: crea un Proyecto con Status=In Progress,
    crea tareas completadas por el agente (Status=Completed)
    y tareas pendientes para Oscar (Status=Not started).
    Al terminar, marca el proyecto como Completed si no hay pendientes para Oscar.
    Devuelve {"url": str, "id": str, "pendiente_oscar": list[str]} o None.
    """
    parsed = _parse_structured_response(contenido)

    # Crear proyecto con Status=In Progress
    dept_display = DEPT_DISPLAY.get(dept, dept.title()) if dept else ""
    nombre = f"[{dept_display}] {titulo}" if dept_display else titulo

    chunk_size = 1990
    chunks = [contenido[i:i + chunk_size] for i in range(0, len(contenido), chunk_size)]
    children = [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": chunk}}]}
        }
        for chunk in chunks
    ]

    properties: dict = {
        "Name": {"title": [{"text": {"content": nombre}}]},
        "Status": {"status": {"name": "In Progress"}},
        "Start Date": {"date": {"start": date.today().isoformat()}},
    }
    area_id = DEPT_AREA_IDS.get(dept)
    if area_id:
        properties["Departamento"] = {"relation": [{"id": area_id}]}

    payload = {
        "parent": {"database_id": DB_PROYECTOS},
        "properties": properties,
        "children": children[:100],
    }
    result = await _post("https://api.notion.com/v1/pages", payload)
    if not result:
        return None

    url = result.get("url", "")
    page_id = result.get("id", "")
    logger.info("Notion proyecto ejecución: %s → %s", nombre, url)

    # Tareas completadas por el agente
    for task_title in parsed["tareas"]:
        await _crear_tarea_ejecutada(task_title, page_id, dept)

    # Tareas pendientes para Oscar (Status=Not started, sin dept prefix)
    for item in parsed["pendiente_oscar"]:
        await _crear_tarea_inbox_oscar(item, page_id)

    # Si no hay pendientes de Oscar → marcar proyecto como Completed
    if not parsed["pendiente_oscar"]:
        await _actualizar_status_proyecto(page_id, "Completed")

    return {
        "url": url,
        "id": page_id,
        "pendiente_oscar": parsed["pendiente_oscar"],
    }


async def _crear_tarea_ejecutada(tarea: str, proyecto_id: str, dept: str = "") -> bool:
    """Crea tarea completada por el agente (Status=Completed) vinculada al proyecto."""
    dept_display = DEPT_DISPLAY.get(dept, dept.title()) if dept else ""
    nombre = f"[{dept_display}] {tarea}" if dept_display else tarea
    payload = {
        "parent": {"database_id": DB_TAREAS_AIOS},
        "properties": {
            "Nombre": {"title": [{"text": {"content": nombre[:2000]}}]},
            "Status": {"status": {"name": "Completed"}},
            "Fecha": {"date": {"start": date.today().isoformat()}},
            "Prioridad": {"select": {"name": "Media"}},
            "Proyecto": {"relation": [{"id": proyecto_id}]},
        }
    }
    result = await _post("https://api.notion.com/v1/pages", payload)
    return bool(result)


async def _crear_tarea_inbox_oscar(tarea: str, proyecto_id: str) -> bool:
    """Crea tarea pendiente para Oscar (Status=Inbox) vinculada al proyecto."""
    payload = {
        "parent": {"database_id": DB_TAREAS_AIOS},
        "properties": {
            "Nombre": {"title": [{"text": {"content": f"👤 {tarea[:2000]}"}}]},
            "Status": {"status": {"name": "Inbox"}},
            "Fecha": {"date": {"start": date.today().isoformat()}},
            "Prioridad": {"select": {"name": "Alta"}},
            "Proyecto": {"relation": [{"id": proyecto_id}]},
        }
    }
    result = await _post("https://api.notion.com/v1/pages", payload)
    if result:
        logger.info("Notion tarea inbox Oscar: %s", tarea[:50])
    return bool(result)
