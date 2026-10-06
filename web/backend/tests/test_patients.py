"""Pacientes (W06–W08): cadastro com TCLE em PDF, código sugerido, lista com busca, edição,
inativação e o download autenticado do termo, tudo com auditoria."""
import json
import os

from app.services.storage import storage

from .accounts import API, admin, audit_entries, login, make_user, researcher
from .media_files import jpeg, pdf


def payload(**overrides):
    base = {
        "code": "P-016", "name": "Mariana Alves", "birth_date": "1998-03-12", "sex": "female",
        "vision_correction": "glasses", "consent_signed": False, "consent_date": None, "notes": "",
    }
    return {**base, **overrides}


def create(client, consent=None, filename="termo-P-016.pdf", **overrides):
    files = {"consent_file": (filename, consent, "application/pdf")} if consent is not None else None
    return client.post(f"{API}/patients", data={"data": json.dumps(payload(**overrides))}, files=files)


def update(client, pid, consent=None, filename="termo-novo.pdf", **overrides):
    files = {"consent_file": (filename, consent, "application/pdf")} if consent is not None else None
    return client.put(f"{API}/patients/{pid}", data={"data": json.dumps(payload(**overrides))}, files=files)


def test_requires_login_and_permission(client):
    assert client.get(f"{API}/patients").status_code == 401
    researcher(client)
    assert client.get(f"{API}/patients").status_code == 200
    # O pesquisador não inativa pacientes (W21).
    pid = create(client).json()["id"]
    r = client.put(f"{API}/patients/{pid}/status", json={"status": "inactive"})
    assert r.status_code == 403


def test_suggested_code_is_the_next_free_number(client):
    researcher(client)
    assert client.get(f"{API}/patients/next-code").json() == {"code": "P-001"}
    create(client, code="P-014")
    create(client, code="p-009", name="Rafael Nunes")  # vira maiúscula
    create(client, code="LAB-77", name="Outro Código")
    assert client.get(f"{API}/patients/next-code").json() == {"code": "P-015"}


def test_create_with_consent_pdf_and_audit(client):
    uid = researcher(client)
    r = create(client, consent=pdf(), consent_signed=True, consent_date="2026-09-01", notes="  Prefere manhã.  ")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["code"] == "P-016"
    assert body["status"] == "active"
    assert body["consent_signed"] is True and body["consent_date"] == "2026-09-01"
    assert body["consent_file"] == {"name": "termo-P-016.pdf", "size": len(pdf())}
    assert body["notes"] == "Prefere manhã."
    assert body["created_by_name"] == "Ana Souza"
    assert body["sessions_count"] == 0 and body["sessions"] == []

    doc = client.get(f"{API}/patients/{body['id']}/consent")
    assert doc.status_code == 200
    assert doc.headers["content-type"] == "application/pdf"
    assert doc.headers["content-disposition"].startswith("inline")
    assert doc.content == pdf()

    [entry] = audit_entries(action="create", entity_type="patient")
    assert entry.user_id == uid and entry.entity_label == "P-016" and entry.entity_id == body["id"]
    changes = {c["field"]: c["after"] for c in entry.changes}
    assert changes["name"] == "Mariana Alves"
    assert changes["birth_date"] == "12/03/1998"
    assert changes["sex"] == "Feminino"
    assert changes["vision_correction"] == "Óculos de grau"
    assert changes["consent_signed"] == "Sim"
    assert changes["consent_file"] == f"termo-P-016.pdf ({len(pdf())} B)"
    assert changes["status"] == "Ativo"


def test_consent_rules(client):
    researcher(client)
    r = create(client, consent_signed=True)
    assert r.status_code == 422  # assinado sem data
    r = create(client, consent=pdf())
    assert r.status_code == 422  # PDF sem marcar como assinado
    assert r.json()["detail"] == "marque o termo como assinado para anexar o PDF"
    r = create(client, consent=jpeg(), filename="termo.pdf", consent_signed=True, consent_date="2026-09-01")
    assert r.status_code == 415
    assert r.json()["detail"] == "o termo precisa ser um arquivo PDF"
    # Sem assinatura, a data some.
    body = create(client, consent_signed=False, consent_date="2026-09-01").json()
    assert body["consent_date"] is None and body["consent_file"] is None


def test_validation_and_unique_code(client):
    researcher(client)
    assert create(client).status_code == 201
    r = create(client, code="p-016", name="Outra Pessoa")
    assert r.status_code == 409
    assert r.json()["detail"] == "já existe um paciente com este código"
    for bad in ({"code": "P 016"}, {"code": ""}, {"name": "   "}, {"birth_date": "2999-01-01"}, {"sex": "x"},
                {"vision_correction": "binóculo"}):
        assert create(client, **{"code": "P-099", **bad}).status_code == 422, bad
    r = client.post(f"{API}/patients", data={"data": "não é json"})
    assert r.status_code == 422


def test_list_search_inactive_and_counts(client):
    admin(client)
    ids = {}
    for i, name in enumerate(["Mariana Alves", "Rafael Nunes", "Beatriz Carvalho"], start=14):
        ids[name] = create(client, code=f"P-{i:03d}", name=name).json()["id"]
    client.put(f"{API}/patients/{ids['Rafael Nunes']}/status", json={"status": "inactive"})

    page = client.get(f"{API}/patients").json()
    assert [p["code"] for p in page["items"]] == ["P-016", "P-014"]  # mais recentes primeiro, sem inativos
    assert page["total"] == 2
    assert page["counts"] == {"active": 2, "inactive": 1}
    assert set(page["items"][0]) == {"id", "code", "name", "birth_date", "status", "sessions_count", "last_session_at"}

    page = client.get(f"{API}/patients", params={"include_inactive": True}).json()
    assert [p["code"] for p in page["items"]] == ["P-016", "P-014", "P-015"]  # inativos por último
    assert client.get(f"{API}/patients", params={"q": "nunes", "include_inactive": True}).json()["total"] == 1
    assert client.get(f"{API}/patients", params={"q": "p-014"}).json()["items"][0]["name"] == "Mariana Alves"
    assert client.get(f"{API}/patients", params={"q": "%"}).json()["total"] == 0
    page = client.get(f"{API}/patients", params={"page": 2, "page_size": 1}).json()
    assert [p["code"] for p in page["items"]] == ["P-014"]


def test_update_replaces_and_removes_the_pdf(client):
    researcher(client)
    created = create(client, consent=pdf("primeiro"), consent_signed=True, consent_date="2026-09-01").json()
    pid = created["id"]
    first_files = os.listdir(storage.patient_dir(pid))
    assert len(first_files) == 1

    r = update(client, pid, consent=pdf("segundo"), consent_signed=True, consent_date="2026-09-02",
               name="Mariana Alves Souza", vision_correction="contacts")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "Mariana Alves Souza"
    assert body["consent_file"]["name"] == "termo-novo.pdf"
    assert client.get(f"{API}/patients/{pid}/consent").content == pdf("segundo")
    assert os.listdir(storage.patient_dir(pid)) != first_files  # o PDF antigo saiu do disco
    assert len(os.listdir(storage.patient_dir(pid))) == 1

    [entry] = audit_entries(action="update", entity_type="patient")
    changes = {c["field"]: (c["before"], c["after"]) for c in entry.changes}
    assert changes["name"] == ("Mariana Alves", "Mariana Alves Souza")
    assert changes["vision_correction"] == ("Óculos de grau", "Lentes de contato")
    assert changes["consent_date"] == ("01/09/2026", "02/09/2026")
    assert changes["consent_file"][1] == f"termo-novo.pdf ({len(pdf('segundo'))} B)"
    assert "code" not in changes

    # Desmarcar a assinatura tira a data e o PDF.
    body = update(client, pid, consent_signed=False, name="Mariana Alves Souza", vision_correction="contacts").json()
    assert body["consent_signed"] is False and body["consent_date"] is None and body["consent_file"] is None
    assert os.listdir(storage.patient_dir(pid)) == []
    assert client.get(f"{API}/patients/{pid}/consent").status_code == 404

    # Salvar sem mudar nada não gera registro.
    update(client, pid, consent_signed=False, name="Mariana Alves Souza", vision_correction="contacts")
    assert len(audit_entries(action="update", entity_type="patient")) == 2


def test_update_keeps_the_pdf_when_no_new_file(client):
    researcher(client)
    pid = create(client, consent=pdf(), consent_signed=True, consent_date="2026-09-01").json()["id"]
    body = update(client, pid, consent_signed=True, consent_date="2026-09-01", notes="Nova observação").json()
    assert body["consent_file"] == {"name": "termo-P-016.pdf", "size": len(pdf())}
    assert client.get(f"{API}/patients/{pid}/consent").content == pdf()


def test_update_rejects_a_code_in_use(client):
    researcher(client)
    create(client, code="P-001")
    pid = create(client, code="P-002", name="Outra").json()["id"]
    r = update(client, pid, code="P-001", name="Outra")
    assert r.status_code == 409


def test_deactivate_and_reactivate(client):
    admin(client)
    pid = create(client).json()["id"]
    r = client.put(f"{API}/patients/{pid}/status", json={"status": "inactive"})
    assert r.status_code == 200 and r.json()["status"] == "inactive"
    assert client.get(f"{API}/patients").json()["total"] == 0
    # Inativo continua acessível pelo link e editável.
    assert client.get(f"{API}/patients/{pid}").json()["status"] == "inactive"
    client.put(f"{API}/patients/{pid}/status", json={"status": "inactive"})  # repetir não registra de novo
    r = client.put(f"{API}/patients/{pid}/status", json={"status": "active"})
    assert r.json()["status"] == "active"
    entries = audit_entries(action="update", entity_type="patient")
    assert [(e.changes[0]["before"], e.changes[0]["after"]) for e in entries] == [("Ativo", "Inativo"), ("Inativo", "Ativo")]
    assert entries[0].changes[0]["label"] == "Situação"


def test_consent_download_requires_login(client):
    make_user("Ana Souza", "ana.souza@exemplo.com", "researcher")
    login(client, "ana.souza@exemplo.com")
    pid = create(client, consent=pdf(), consent_signed=True, consent_date="2026-09-01").json()["id"]
    client.cookies.clear()
    assert client.get(f"{API}/patients/{pid}/consent").status_code == 401
    assert client.get(f"{API}/patients/naoexiste").status_code == 401
