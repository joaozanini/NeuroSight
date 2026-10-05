"""Auditoria (W22, W23): lista com filtros, detalhe com o diff e o CSV."""
import csv
import io
from datetime import datetime, timedelta, timezone

from app.db import SessionLocal
from app.services import audit

from .accounts import API, admin, audit_entries, make_user, researcher


def add_entry(action="update", entity_type="session", label="Rostos neutros e expressivos, P-015", days_ago=0.0,
              user_name="Ana Souza", changes=None):
    with SessionLocal() as db:
        entry = audit.record(db, None, None, action, entity_type, label, "s1", changes)
        entry.user_name, entry.user_role = user_name, "researcher"
        entry.created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
        db.commit()
        return entry.id


def test_needs_the_permission(client):
    assert client.get(f"{API}/audit").status_code == 401
    researcher(client)
    for path in ("/audit", "/audit/filters", "/audit/export.csv", "/audit/1"):
        assert client.get(f"{API}{path}").status_code == 403


def test_list_is_newest_first_with_ten_per_page(client):
    admin(client)  # o login entra como registro
    for i in range(12):
        add_entry(label=f"Sessão {i}", days_ago=1 + i / 100)
    page = client.get(f"{API}/audit").json()
    assert (page["total"], page["page_size"], len(page["items"])) == (13, 10, 10)
    assert [i["action"] for i in page["items"][:2]] == ["login", "update"]
    assert page["items"][1]["entity_label"] == "Sessão 0"
    assert "changes" not in page["items"][0]
    assert len(client.get(f"{API}/audit", params={"page": 2}).json()["items"]) == 3


def test_filters(client):
    me = admin(client)
    add_entry(action="visibility_change", days_ago=2)
    add_entry(action="export", entity_type="session", days_ago=10)
    make_user("Ana Souza", "ana.souza@exemplo.com", "researcher")

    def actions(**params):
        return [i["action"] for i in client.get(f"{API}/audit", params=params).json()["items"]]

    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    assert actions(since=since) == ["login", "visibility_change"]
    assert actions(until=since) == ["export"]
    assert actions(action="export") == ["export"]
    assert actions(entity_type="system") == ["login"]
    assert actions(user_id=me) == ["login"]

    f = client.get(f"{API}/audit/filters").json()
    assert {"value": "visibility_change", "label": "Mudança de visibilidade"} in f["actions"]
    assert {"value": "user", "label": "Usuário"} in f["entity_types"]
    assert [u["label"] for u in f["users"]] == ["Ana Souza", "Carlos Lima"]


def test_detail_has_where_from_and_what_changed(client):
    admin(client)
    entry_id = add_entry(action="visibility_change", changes=[
        audit.change("visibility", "Visibilidade", "Só o responsável", "Pesquisadores escolhidos"),
        audit.change("shared_with", "Pesquisadores com acesso", None, "Bruno Castro"),
    ])
    d = client.get(f"{API}/audit/{entry_id}").json()
    assert d["changes"][1] == {"field": "shared_with", "label": "Pesquisadores com acesso", "before": None, "after": "Bruno Castro"}
    assert d["user_name"] == "Ana Souza"

    login_entry = audit_entries(action="login")[0]
    d = client.get(f"{API}/audit/{login_entry.id}").json()
    assert d["ip"] == "testclient"
    assert d["user_agent"]
    assert d["changes"] == []
    assert client.get(f"{API}/audit/999999").status_code == 404


def test_csv_export(client):
    admin(client)
    add_entry(label="=HYPERLINK(\"x\")", changes=[audit.change("status", "Status", "Ativo", "Inativo")])
    add_entry(action="export", days_ago=30)
    r = client.get(f"{API}/audit/export.csv", params={"tz": "America/Sao_Paulo", "action": "update"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.headers["content-disposition"].startswith('attachment; filename="auditoria-')
    text = r.content.decode("utf-8")
    assert text.startswith("﻿")
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿")), delimiter=";"))
    assert rows[0] == ["Data e hora", "Usuário", "Perfil", "Ação", "Tipo de item", "Item afetado", "IP", "Navegador", "O que mudou"]
    assert len(rows) == 2
    row = rows[1]
    assert row[1:6] == ["Ana Souza", "Pesquisador", "Edição", "Sessão", "'=HYPERLINK(\"x\")"]
    assert row[8] == "Status: Ativo → Inativo"
    datetime.strptime(row[0], "%d/%m/%Y %H:%M:%S")
    # A exportação também fica registrada.
    [entry] = audit_entries(action="export", entity_type="system")
    assert entry.entity_label == "Registros da auditoria (CSV)"


def test_csv_streams_in_batches(client, monkeypatch):
    from app.routers import audit as audit_router

    monkeypatch.setattr(audit_router, "CSV_BATCH", 3)
    admin(client)
    for i in range(7):
        add_entry(label=f"Sessão {i}")
    with client.stream("GET", f"{API}/audit/export.csv", params={"tz": "fuso/inexistente"}) as r:
        body = "".join(r.iter_text())
    # Cabeçalho, as 7, o login e a própria exportação (gravada antes de o arquivo começar).
    assert len(body.strip().splitlines()) == 1 + 7 + 2
