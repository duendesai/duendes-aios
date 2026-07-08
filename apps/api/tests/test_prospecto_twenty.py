"""
Tests del camino Twenty del dialer (`services.prospecto_twenty`).

Validan la lógica pura (sin red): filtrado/orden de la cola, mapeo de resultado de
llamada a los campos del objeto `prospecto`, y conversión value→label del DTO.
El cliente Twenty se sustituye por un fake que captura los updates.
"""
from __future__ import annotations

from services import prospecto_twenty as ptw
from services.crm.models import option_value


class _FakeClient:
    def __init__(self, nodes: list[dict]) -> None:
        self._nodes = nodes
        self.updated: list[tuple[str, dict]] = []

    async def list_all(self) -> list[dict]:
        return self._nodes

    async def get(self, pid: str):
        return next((n for n in self._nodes if n["id"] == pid), None)

    async def update(self, pid: str, fields: dict) -> None:
        self.updated.append((pid, fields))


def _node(**over):
    base = {
        "id": "x", "name": "N", "phone": "+34600000000", "estado": "PENDIENTE",
        "prioridad": "MEDIA", "campana": "FISIOS_MALAGA", "intentos": 0,
        "noLlamar": False, "proximoIntento": None, "ultimoIntento": None,
        "score": 0, "email": None, "notas": "",
    }
    base.update(over)
    return base


async def test_fetch_queue_excludes_ineligibles_and_orders():
    nodes = [
        _node(id="nuevo", estado="PENDIENTE", intentos=0),
        _node(id="sin_tel", phone=None),
        _node(id="no_llamar", noLlamar=True),
        _node(id="cerrado", estado=option_value("Demo agendada")),  # excluido
        _node(id="callback", estado=option_value("Rellamar"),
              proximoIntento="2020-01-01T00:00:00+00:00"),  # vencido → primero
        _node(id="reintento", estado="PENDIENTE", intentos=3),
    ]
    queue = await ptw.fetch_queue(_FakeClient(nodes))
    ids = [p["id"] for p in queue]

    assert "sin_tel" not in ids
    assert "no_llamar" not in ids
    assert "cerrado" not in ids
    # callback vencido primero; nuevo (intentos 0) antes que reintento (intentos 3)
    assert ids == ["callback", "nuevo", "reintento"]


async def test_fetch_queue_hides_future_callback():
    nodes = [
        _node(id="futuro", estado=option_value("Rellamar"),
              proximoIntento="2999-01-01T00:00:00+00:00"),
    ]
    queue = await ptw.fetch_queue(_FakeClient(nodes))
    assert queue == []


async def test_submit_call_result_maps_disposition():
    client = _FakeClient([_node(id="p1", intentos=1, notas="previo")])
    result = await ptw.submit_call_result(client, {
        "prospect_id": "p1",
        "disposition": "No interesa",
        "motivo_perdida": "Precio",
        "notas": "no le interesa",
    })
    assert result["ok"] is True
    assert result["partial"] is False
    pid, fields = client.updated[0]
    assert pid == "p1"
    assert fields["estado"] == option_value("No interesa")   # "NO_INTERESA"
    assert fields["outcome"] == option_value("no_interesa")  # "NO_INTERESA"
    assert fields["intentos"] == 2                            # 1 + 1
    assert fields["motivoPerdida"] == "Precio"
    assert "no le interesa" in fields["notas"]
    assert "previo" in fields["notas"]                        # append, no overwrite


async def test_submit_no_llamar_sets_flag():
    client = _FakeClient([_node(id="p2")])
    await ptw.submit_call_result(client, {"prospect_id": "p2", "disposition": "No llamar"})
    _, fields = client.updated[0]
    assert fields["noLlamar"] is True


async def test_submit_rellamar_sets_next_attempt():
    client = _FakeClient([_node(id="p3")])
    await ptw.submit_call_result(client, {
        "prospect_id": "p3", "disposition": "Rellamar",
        "callback_at": "2026-07-10T15:00:00+00:00", "callback_notas": "mañana",
    })
    _, fields = client.updated[0]
    assert fields["proximoIntento"] == "2026-07-10T15:00:00+00:00"
    assert fields["callbackSolicitado"] == "2026-07-10T15:00:00+00:00"
    assert fields["callbackNotas"] == "mañana"


def test_to_dto_converts_value_to_label():
    dto = ptw._to_dto(_node(estado="PENDIENTE", campana="FISIOS_MALAGA", prioridad="ALTA"))
    assert dto["estado"] == "Pendiente"
    assert dto["campaign"] == "Fisios Málaga"
    assert dto["prioridad"] == "Alta"
