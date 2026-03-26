"""
Duendes AIOS — Slack Command Dispatcher
Detects data commands in Slack messages and returns real Airtable data.
Each department channel has its own command set.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Optional


# ---------------------------------------------------------------------------
# Command detection
# ---------------------------------------------------------------------------

# Patterns: (regex, cmd_name, dept_hint)
_PATTERNS = [
    # dashboard — any dept, check first to avoid false positives with other keywords
    (re.compile(r"^(dashboard|resumen|estado del negocio|c[oó]mo vamos)$", re.IGNORECASE), "dashboard", None),

    # SDR leads — write commands (check before read commands to avoid partial matches)
    (re.compile(r"^a[nñ]adir\s+lead\s+(.+)$", re.IGNORECASE), "add_lead", "sdr"),
    (re.compile(r"^nota\s+lead\s+(\d+)\s+(.+)$", re.IGNORECASE), "lead_nota", "sdr"),
    (re.compile(r"^estado\s+lead\s+(\d+)\s+(.+)$", re.IGNORECASE), "lead_estado", "sdr"),
    (re.compile(r"^push\s+lead\s+(\d+)\s+(\d+)$", re.IGNORECASE), "push_lead", "sdr"),

    # SDR leads — read commands
    (re.compile(r"^(leads|mis leads|ver leads|lista leads)$", re.IGNORECASE), "leads", "sdr"),
    (re.compile(r"^lead\s+[#nN]?[úu]?mero?\s*(\d+)$", re.IGNORECASE), "lead", "sdr"),
    (re.compile(r"^lead\s+(\d+)$", re.IGNORECASE), "lead", "sdr"),
    (re.compile(r"^(calificar|califica leads|score leads)$", re.IGNORECASE), "calificar", "sdr"),
    (re.compile(r"^(campa[nñ]as|mis campa[nñ]as)$", re.IGNORECASE), "campanas", "sdr"),

    # COO tasks — write commands
    (re.compile(r"^(?:a[nñ]adir|nueva)\s+tarea\s+(.+)$", re.IGNORECASE), "add_task", "coo"),
    (re.compile(r"^hecho\s+(\d+)$", re.IGNORECASE), "done_task", "coo"),
    (re.compile(r"^completar\s+tarea\s+(\d+)$", re.IGNORECASE), "done_task", "coo"),
    (re.compile(r"^tarea\s+(\d+)\s+hecha$", re.IGNORECASE), "done_task", "coo"),

    # COO tasks — read commands
    (re.compile(r"^(tareas|mis tareas|qu[eé] tengo pendiente|pendientes)$", re.IGNORECASE), "tareas", "coo"),

    # AE deals — write commands
    (re.compile(r"^(?:a[nñ]adir|nuevo)\s+deal\s+(.+)$", re.IGNORECASE), "add_deal", "ae"),
    (re.compile(r"^nota\s+deal\s+(\d+)\s+(.+)$", re.IGNORECASE), "deal_nota", "ae"),
    (re.compile(r"^estado\s+deal\s+(\d+)\s+(.+)$", re.IGNORECASE), "deal_estado", "ae"),

    # AE deals — read commands
    (re.compile(r"^(deals|pipeline|mis deals|ver pipeline)$", re.IGNORECASE), "deals", "ae"),

    # CS clients — write commands
    (re.compile(r"^(?:checkin|check-in|registrar\s+checkin)\s+(\d+)$", re.IGNORECASE), "checkin", "cs"),
    (re.compile(r"^nota\s+cliente\s+(\d+)\s+(.+)$", re.IGNORECASE), "client_nota", "cs"),

    # CS clients — read commands
    (re.compile(r"^(clientes|mis clientes|clientes activos)$", re.IGNORECASE), "clientes", "cs"),
    (re.compile(r"^(churn|riesgo|alertas)$", re.IGNORECASE), "churn", "cs"),

    # CFO invoices — write commands
    (re.compile(r"^a[nñ]adir\s+factura\s+(.+)$", re.IGNORECASE), "add_invoice", "cfo"),

    # CFO invoices — read commands
    (re.compile(r"^(facturas|mis facturas|cobros pendientes)$", re.IGNORECASE), "facturas", "cfo"),
    (re.compile(r"^(mrr|ingresos|mis ingresos)$", re.IGNORECASE), "mrr", "cfo"),
]


def detect_command(text: str, dept: str) -> Optional[dict]:
    """
    Detect if the message is a known data command.

    Returns a dict like {"cmd": "leads"} or {"cmd": "lead", "n": 3},
    or None if no command is recognized.

    Detection is case-insensitive and strips leading/trailing whitespace.
    Commands are only surfaced when the dept matches (or cmd is dept-agnostic).
    """
    cleaned = text.strip()

    for pattern, cmd_name, dept_hint in _PATTERNS:
        m = pattern.match(cleaned)
        if not m:
            continue

        # Dept filtering: if a hint is set, the message dept must match
        if dept_hint is not None and dept != dept_hint:
            continue

        if cmd_name == "lead":
            try:
                n = int(m.group(1))
            except (IndexError, ValueError):
                n = 1
            return {"cmd": "lead", "n": n}

        # --- SDR write commands ---

        if cmd_name == "add_lead":
            raw = m.group(1).strip()
            parts = [p.strip() for p in raw.split("|")]
            empresa = parts[0] if len(parts) > 0 else raw
            sector = parts[1] if len(parts) > 1 else ""
            ciudad = parts[2] if len(parts) > 2 else ""
            return {"cmd": "add_lead", "empresa": empresa, "sector": sector, "ciudad": ciudad}

        if cmd_name == "lead_nota":
            try:
                n = int(m.group(1))
            except (IndexError, ValueError):
                n = 1
            nota = m.group(2).strip()
            return {"cmd": "lead_nota", "n": n, "nota": nota}

        if cmd_name == "lead_estado":
            try:
                n = int(m.group(1))
            except (IndexError, ValueError):
                n = 1
            estado = m.group(2).strip()
            return {"cmd": "lead_estado", "n": n, "estado": estado}

        if cmd_name == "push_lead":
            try:
                lead_n = int(m.group(1))
                camp_n = int(m.group(2))
            except (IndexError, ValueError):
                return None
            return {"cmd": "push_lead", "lead_n": lead_n, "camp_n": camp_n}

        # --- COO write commands ---

        if cmd_name == "add_task":
            texto = m.group(1).strip()
            return {"cmd": "add_task", "texto": texto}

        if cmd_name == "done_task":
            try:
                n = int(m.group(1))
            except (IndexError, ValueError):
                n = 1
            return {"cmd": "done_task", "n": n}

        # --- AE write commands ---

        if cmd_name == "add_deal":
            raw = m.group(1).strip()
            parts = [p.strip() for p in raw.split("|")]
            empresa = parts[0] if len(parts) > 0 else raw
            sector = parts[1] if len(parts) > 1 else ""
            return {"cmd": "add_deal", "empresa": empresa, "sector": sector}

        if cmd_name == "deal_nota":
            try:
                n = int(m.group(1))
            except (IndexError, ValueError):
                n = 1
            nota = m.group(2).strip()
            return {"cmd": "deal_nota", "n": n, "nota": nota}

        if cmd_name == "deal_estado":
            try:
                n = int(m.group(1))
            except (IndexError, ValueError):
                n = 1
            estado = m.group(2).strip()
            return {"cmd": "deal_estado", "n": n, "estado": estado}

        # --- CS write commands ---

        if cmd_name == "checkin":
            try:
                n = int(m.group(1))
            except (IndexError, ValueError):
                n = 1
            return {"cmd": "checkin", "n": n}

        if cmd_name == "client_nota":
            try:
                n = int(m.group(1))
            except (IndexError, ValueError):
                n = 1
            nota = m.group(2).strip()
            return {"cmd": "client_nota", "n": n, "nota": nota}

        # --- CFO write commands ---

        if cmd_name == "add_invoice":
            raw = m.group(1).strip()
            parts = [p.strip() for p in raw.split("|")]
            cliente = parts[0] if len(parts) > 0 else raw
            concepto = parts[1] if len(parts) > 1 else ""
            importe_raw = parts[2] if len(parts) > 2 else "0"
            # Strip currency symbols and parse
            importe_clean = re.sub(r"[€$\s]", "", importe_raw).replace(",", ".")
            try:
                importe = float(importe_clean)
            except ValueError:
                importe = 0.0
            return {"cmd": "add_invoice", "cliente": cliente, "concepto": concepto, "importe": importe}

        return {"cmd": cmd_name}

    return None


# ---------------------------------------------------------------------------
# Command execution
# ---------------------------------------------------------------------------

async def execute_command(cmd_dict: dict, dept: str, anthropic_client) -> str:
    """
    Route a detected command to the appropriate Airtable function and return
    a formatted string suitable for posting to Slack.

    All errors are caught and returned as user-friendly Spanish messages.
    """
    try:
        return await _dispatch(cmd_dict, dept, anthropic_client)
    except Exception as exc:
        cmd = cmd_dict.get("cmd", "?")
        return (
            f"Error al ejecutar el comando `{cmd}`. "
            f"Inténtalo de nuevo o contacta con soporte.\n"
            f"_(Detalle técnico: {exc})_"
        )


async def _dispatch(cmd_dict: dict, dept: str, anthropic_client) -> str:
    cmd = cmd_dict["cmd"]

    if cmd == "leads":
        from sdr_leads import list_leads, format_lead_list
        leads = await list_leads()
        return format_lead_list(leads, "Leads activos")

    elif cmd == "lead":
        from sdr_leads import list_leads, format_lead_detail
        leads = await list_leads()
        n = cmd_dict.get("n", 1)
        if leads and 1 <= n <= len(leads):
            return format_lead_detail(leads[n - 1], n)
        total = len(leads)
        return f"No existe el lead #{n}. Tienes {total} lead{'s' if total != 1 else ''}."

    elif cmd == "calificar":
        from sdr_leads import list_leads
        leads = await list_leads(estado="prospecto")
        if not leads:
            return "No hay leads nuevos para calificar."
        try:
            from sdr_qualifier import qualify_leads_batch, format_qualification_report
            results = await qualify_leads_batch(leads, anthropic_client)
            return format_qualification_report(results)
        except ImportError:
            return (
                f"Tienes {len(leads)} lead(s) con estado 'prospecto' para calificar, "
                f"pero el módulo `sdr_qualifier` no está disponible."
            )

    elif cmd == "campanas":
        try:
            from instantly_client import list_campaigns, format_campaigns
            campaigns = await list_campaigns()
            return format_campaigns(campaigns)
        except ImportError:
            return "El módulo de campañas (`instantly_client`) no está disponible."

    elif cmd == "tareas":
        from coo_tasks import list_tasks, format_task_list
        tasks = await list_tasks(status="pending")
        # Assign sequential display IDs before formatting
        for i, t in enumerate(tasks, 1):
            t._display_id = i  # type: ignore[attr-defined]
        return format_task_list(tasks, "Tareas pendientes")

    elif cmd == "deals":
        from ae_deals import list_deals, format_deal_list
        deals = await list_deals()
        # Assign sequential display IDs before formatting
        for i, d in enumerate(deals, 1):
            d._display_id = i  # type: ignore[attr-defined]
        return format_deal_list(deals, "Pipeline de deals")

    elif cmd == "facturas":
        # list_invoices() already returns a formatted string
        from cfo_invoices import list_invoices
        return await list_invoices()

    elif cmd == "mrr":
        # get_mrr() already returns a formatted string
        from cfo_invoices import get_mrr
        return await get_mrr()

    elif cmd == "clientes":
        # list_clients() already returns a formatted string
        from cs_clients import list_clients
        return await list_clients()

    elif cmd == "churn":
        # get_churn_report() already returns a formatted string
        from cs_clients import get_churn_report
        return await get_churn_report()

    elif cmd == "dashboard":
        return await _build_dashboard(anthropic_client)

    # -----------------------------------------------------------------------
    # SDR write commands
    # -----------------------------------------------------------------------

    elif cmd == "add_lead":
        from sdr_leads import add_lead
        empresa = cmd_dict.get("empresa", "").strip()
        if not empresa:
            return "❌ Debes indicar al menos el nombre de la empresa. Uso: `añadir lead [empresa] | [sector] | [ciudad]`"
        sector = cmd_dict.get("sector", "otro").strip() or "otro"
        ciudad = cmd_dict.get("ciudad", "").strip()
        try:
            lead = await add_lead(nombre=empresa, sector=sector, ciudad=ciudad)
            sector_label = lead.sector or sector
            ciudad_label = f" ({ciudad})" if ciudad else ""
            return f"✅ Lead añadido: *{lead.nombre}* [{sector_label}]{ciudad_label} — estado: prospecto"
        except Exception as exc:
            return f"❌ No se pudo añadir el lead: {exc}"

    elif cmd == "lead_nota":
        from sdr_leads import list_leads, add_lead_nota
        n = cmd_dict.get("n", 1)
        nota = cmd_dict.get("nota", "").strip()
        if not nota:
            return "❌ El texto de la nota no puede estar vacío."
        try:
            leads = await list_leads()
            if not leads or not (1 <= n <= len(leads)):
                total = len(leads) if leads else 0
                return f"❌ No existe el lead #{n}. Tienes {total} lead{'s' if total != 1 else ''}."
            lead = leads[n - 1]
            updated = await add_lead_nota(lead.id, nota)
            nombre = updated.nombre if updated else lead.nombre
            return f"✅ Nota añadida al lead #{n} ({nombre})."
        except Exception as exc:
            return f"❌ Error al añadir la nota: {exc}"

    elif cmd == "lead_estado":
        from sdr_leads import list_leads, update_lead_estado, VALID_ESTADOS
        n = cmd_dict.get("n", 1)
        estado = cmd_dict.get("estado", "").strip().lower()
        if not estado:
            return "❌ Debes indicar el nuevo estado."
        valid_list = ", ".join(sorted(VALID_ESTADOS))
        if estado not in VALID_ESTADOS:
            return f"❌ Estado no válido: `{estado}`. Válidos: {valid_list}"
        try:
            leads = await list_leads()
            if not leads or not (1 <= n <= len(leads)):
                total = len(leads) if leads else 0
                return f"❌ No existe el lead #{n}. Tienes {total} lead{'s' if total != 1 else ''}."
            lead = leads[n - 1]
            updated = await update_lead_estado(lead.id, estado)
            nombre = updated.nombre if updated else lead.nombre
            return f"✅ Lead #{n} ({nombre}) actualizado a estado: *{estado}*"
        except Exception as exc:
            return f"❌ Error al actualizar el estado: {exc}"

    elif cmd == "push_lead":
        from sdr_leads import list_leads
        lead_n = cmd_dict.get("lead_n", 1)
        camp_n = cmd_dict.get("camp_n", 1)
        try:
            leads = await list_leads()
            if not leads or not (1 <= lead_n <= len(leads)):
                total = len(leads) if leads else 0
                return f"❌ No existe el lead #{lead_n}. Tienes {total} lead{'s' if total != 1 else ''}."
            lead = leads[lead_n - 1]
            try:
                from instantly_client import list_campaigns, add_lead_to_campaign
                campaigns = await list_campaigns()
                if not campaigns or not (1 <= camp_n <= len(campaigns)):
                    total_c = len(campaigns) if campaigns else 0
                    return f"❌ No existe la campaña #{camp_n}. Tienes {total_c} campaña{'s' if total_c != 1 else ''}."
                campaign = campaigns[camp_n - 1]
                # Generate a cold email with Claude if possible
                cold_email = ""
                try:
                    from sdr_leads import generate_cold_email
                    cold_email = await generate_cold_email(lead, "", anthropic_client)
                except Exception:
                    pass
                await add_lead_to_campaign(
                    campaign_id=campaign.get("id") or campaign.get("campaign_id", ""),
                    email=lead.email,
                    first_name=lead.contacto.split()[0] if lead.contacto else "",
                    company=lead.nombre,
                    personalization=cold_email[:500] if cold_email else "",
                )
                camp_name = campaign.get("name") or campaign.get("campaign_name", f"Campaña #{camp_n}")
                return (
                    f"✅ Lead #{lead_n} ({lead.nombre}) añadido a la campaña *{camp_name}*."
                    + (f"\n\n_Email generado:_\n{cold_email[:600]}" if cold_email else "")
                )
            except ImportError:
                return "❌ El módulo `instantly_client` no está disponible."
        except Exception as exc:
            return f"❌ Error al hacer push del lead: {exc}"

    # -----------------------------------------------------------------------
    # COO write commands
    # -----------------------------------------------------------------------

    elif cmd == "add_task":
        from coo_tasks import add_task, parse_priority_and_category
        texto = cmd_dict.get("texto", "").strip()
        if not texto:
            return "❌ Debes indicar la descripción de la tarea."
        try:
            title, priority, category = parse_priority_and_category(texto)
            task = await add_task(title=title, priority=priority, category=category)
            prioridad_label = {"high": "alta", "medium": "media", "low": "baja"}.get(task.priority, task.priority)
            return f"✅ Tarea añadida: *{task.title}* [prioridad {prioridad_label} / {task.category}]"
        except Exception as exc:
            return f"❌ No se pudo añadir la tarea: {exc}"

    elif cmd == "done_task":
        from coo_tasks import list_tasks, complete_task
        n = cmd_dict.get("n", 1)
        try:
            tasks = await list_tasks(status="pending")
            # Assign display IDs consistent with the "tareas" read command
            for i, t in enumerate(tasks, 1):
                t._display_id = i  # type: ignore[attr-defined]
            if not tasks or not (1 <= n <= len(tasks)):
                total = len(tasks) if tasks else 0
                return f"❌ No existe la tarea #{n} en pendientes. Tienes {total} tarea{'s' if total != 1 else ''} pendiente{'s' if total != 1 else ''}."
            task = tasks[n - 1]
            updated = await complete_task(task.id)
            title = updated.title if updated else task.title
            return f"✅ Tarea completada: *{title}*"
        except Exception as exc:
            return f"❌ Error al completar la tarea: {exc}"

    # -----------------------------------------------------------------------
    # AE write commands
    # -----------------------------------------------------------------------

    elif cmd == "add_deal":
        from ae_deals import add_deal
        empresa = cmd_dict.get("empresa", "").strip()
        if not empresa:
            return "❌ Debes indicar al menos el nombre de la empresa. Uso: `añadir deal [empresa] | [sector]`"
        sector = cmd_dict.get("sector", "").strip()
        try:
            deal = await add_deal(empresa=empresa, sector=sector)
            sector_label = f" [{deal.sector}]" if deal.sector else ""
            return f"✅ Deal añadido: *{deal.empresa}*{sector_label} — estado: nuevo"
        except Exception as exc:
            return f"❌ No se pudo añadir el deal: {exc}"

    elif cmd == "deal_nota":
        from ae_deals import list_deals, update_deal_nota
        n = cmd_dict.get("n", 1)
        nota = cmd_dict.get("nota", "").strip()
        if not nota:
            return "❌ El texto de la nota no puede estar vacío."
        try:
            deals = await list_deals()
            for i, d in enumerate(deals, 1):
                d._display_id = i  # type: ignore[attr-defined]
            if not deals or not (1 <= n <= len(deals)):
                total = len(deals) if deals else 0
                return f"❌ No existe el deal #{n}. Tienes {total} deal{'s' if total != 1 else ''}."
            deal = deals[n - 1]
            updated = await update_deal_nota(deal.id, nota)
            nombre = updated.empresa if updated else deal.empresa
            return f"✅ Nota añadida al deal #{n} ({nombre})."
        except Exception as exc:
            return f"❌ Error al añadir la nota: {exc}"

    elif cmd == "deal_estado":
        from ae_deals import list_deals, update_deal_estado, VALID_ESTADOS as DEAL_ESTADOS
        n = cmd_dict.get("n", 1)
        estado = cmd_dict.get("estado", "").strip().lower()
        if not estado:
            return "❌ Debes indicar el nuevo estado."
        valid_list = ", ".join(sorted(DEAL_ESTADOS))
        if estado not in DEAL_ESTADOS:
            return f"❌ Estado no válido: `{estado}`. Válidos: {valid_list}"
        try:
            deals = await list_deals()
            for i, d in enumerate(deals, 1):
                d._display_id = i  # type: ignore[attr-defined]
            if not deals or not (1 <= n <= len(deals)):
                total = len(deals) if deals else 0
                return f"❌ No existe el deal #{n}. Tienes {total} deal{'s' if total != 1 else ''}."
            deal = deals[n - 1]
            updated = await update_deal_estado(deal.id, estado)
            nombre = updated.empresa if updated else deal.empresa
            return f"✅ Deal #{n} ({nombre}) actualizado a estado: *{estado}*"
        except Exception as exc:
            return f"❌ Error al actualizar el estado: {exc}"

    # -----------------------------------------------------------------------
    # CS write commands
    # -----------------------------------------------------------------------

    elif cmd == "checkin":
        from cs_clients import get_clients, log_checkin
        n = cmd_dict.get("n", 1)
        try:
            clients = await get_clients()
            clients_sorted = sorted(clients, key=lambda c: c.nombre)
            if not clients_sorted or not (1 <= n <= len(clients_sorted)):
                total = len(clients_sorted) if clients_sorted else 0
                return f"❌ No existe el cliente #{n}. Tienes {total} cliente{'s' if total != 1 else ''} activo{'s' if total != 1 else ''}."
            client = clients_sorted[n - 1]
            updated = await log_checkin(client.id)
            nombre = updated.nombre if updated else client.nombre
            from datetime import date as _date
            return f"✅ Check-in registrado para *{nombre}* ({_date.today().isoformat()})."
        except Exception as exc:
            return f"❌ Error al registrar el check-in: {exc}"

    elif cmd == "client_nota":
        from cs_clients import get_clients, log_checkin
        n = cmd_dict.get("n", 1)
        nota = cmd_dict.get("nota", "").strip()
        if not nota:
            return "❌ El texto de la nota no puede estar vacío."
        try:
            clients = await get_clients()
            clients_sorted = sorted(clients, key=lambda c: c.nombre)
            if not clients_sorted or not (1 <= n <= len(clients_sorted)):
                total = len(clients_sorted) if clients_sorted else 0
                return f"❌ No existe el cliente #{n}. Tienes {total} cliente{'s' if total != 1 else ''} activo{'s' if total != 1 else ''}."
            client = clients_sorted[n - 1]
            # log_checkin supports appending notes; passing empty string skips the date update
            # but we want to append the note without changing check-in date — use log_checkin with notas
            updated = await log_checkin(client.id, notas=nota)
            nombre = updated.nombre if updated else client.nombre
            return f"✅ Nota añadida al cliente #{n} ({nombre})."
        except Exception as exc:
            return f"❌ Error al añadir la nota: {exc}"

    # -----------------------------------------------------------------------
    # CFO write commands
    # -----------------------------------------------------------------------

    elif cmd == "add_invoice":
        from cfo_invoices import add_invoice
        from cs_clients import get_clients
        cliente_nombre = cmd_dict.get("cliente", "").strip()
        concepto = cmd_dict.get("concepto", "").strip()
        importe = cmd_dict.get("importe", 0.0)
        if not cliente_nombre:
            return "❌ Debes indicar el cliente. Uso: `añadir factura [cliente] | [concepto] | [importe]`"
        if importe <= 0:
            return "❌ El importe debe ser mayor que 0. Uso: `añadir factura [cliente] | [concepto] | [importe]`"
        try:
            # Try to resolve client record ID by matching name
            cliente_record_id = ""
            try:
                clients = await get_clients()
                needle = cliente_nombre.lower()
                match = next((c for c in clients if needle in c.nombre.lower()), None)
                if match:
                    cliente_record_id = match.id
            except Exception:
                pass
            invoice = await add_invoice(
                cliente_record_id=cliente_record_id,
                cliente_nombre=cliente_nombre,
                concepto=concepto,
                importe=importe,
            )
            return (
                f"✅ Factura añadida: *{invoice.numero}* — {cliente_nombre} — "
                f"{importe:.2f}€"
                + (f" | {concepto}" if concepto else "")
                + f" | vence: {invoice.fecha_vencimiento}"
            )
        except Exception as exc:
            return f"❌ No se pudo añadir la factura: {exc}"

    return "Comando no reconocido."


# ---------------------------------------------------------------------------
# Dashboard aggregator
# ---------------------------------------------------------------------------

async def _build_dashboard(anthropic_client) -> str:  # noqa: ARG001
    """
    Fetch a compact snapshot from all modules and return a Slack-formatted summary.
    Each module is fetched independently — one failure does not break the others.
    """
    today_str = date.today().strftime("%d/%m/%Y")

    # --- COO: pending tasks ---
    tareas_count = "?"
    try:
        from coo_tasks import list_tasks
        tasks = await list_tasks(status="pending")
        tareas_count = str(len(tasks))
    except Exception:
        pass

    # --- SDR: leads by estado ---
    leads_nuevo = "?"
    leads_contactado = "?"
    leads_reunion = "?"
    try:
        from sdr_leads import list_leads
        all_leads = await list_leads()
        leads_nuevo = str(sum(1 for l in all_leads if l.estado == "prospecto"))
        leads_contactado = str(sum(1 for l in all_leads if l.estado in {"contactado", "respondio"}))
        leads_reunion = str(sum(1 for l in all_leads if l.estado == "reunion"))
    except Exception:
        pass

    # --- AE: active deals count ---
    deals_count = "?"
    try:
        from ae_deals import list_deals
        deals = await list_deals()
        active_deals = [d for d in deals if d.estado not in {"ganado", "perdido"}]
        deals_count = str(len(active_deals))
    except Exception:
        pass

    # --- CFO: MRR from invoices ---
    mrr_value = "?"
    try:
        from cfo_invoices import get_invoices
        from datetime import timedelta, datetime, timezone
        invoices = await get_invoices()
        cutoff = (datetime.now(timezone.utc).date() - timedelta(days=30)).isoformat()
        mrr_total = sum(
            i.importe for i in invoices
            if i.estado == "pagada" and i.fecha_emision >= cutoff
        )
        mrr_value = f"{mrr_total:,.0f}€"
    except Exception:
        pass

    # --- CS: active clients count ---
    clientes_count = "?"
    try:
        from cs_clients import get_clients
        clients = await get_clients()
        clientes_count = str(len(clients))
    except Exception:
        pass

    return (
        f"*Dashboard Duendes* 📊\n"
        f"_{today_str}_\n"
        f"\n"
        f"💰 *MRR:* {mrr_value}\n"
        f"👥 *Clientes activos:* {clientes_count}\n"
        f"🎯 *Leads:* {leads_nuevo} nuevos | {leads_contactado} contactados | {leads_reunion} en reunión\n"
        f"🤝 *Pipeline AE:* {deals_count} deals activos\n"
        f"📋 *Tareas pendientes:* {tareas_count}"
    )
