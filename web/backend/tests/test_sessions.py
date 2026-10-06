"""Sessões (W12, W13, W16, W18): criação pelo assistente, quem vê cada sessão, filtros da lista,
edição das informações, visibilidade e duplicação, com a auditoria. E o que a Fase 3 liga nos
pacientes, estímulos e usuários: contagens, histórico, "Usado em" e "Sessões como responsável".
"""
from datetime import date, datetime, timedelta, timezone

from app.db import SessionLocal
from app.models import Patient, RolePermission, Session, Stimulus

from .accounts import API, admin, audit_entries, login, make_user, researcher

ANA = "ana.souza@exemplo.com"
BRUNO = "bruno.castro@exemplo.com"


def make_patient(code="P-015", name="Beatriz Carvalho", status="active", created_days_ago=30) -> str:
    with SessionLocal() as db:
        patient = Patient(
            code=code, name=name, birth_date=date(1995, 7, 21), sex="female", vision_correction="none",
            status=status, created_at=datetime.now(timezone.utc) - timedelta(days=created_days_ago),
        )
        db.add(patient)
        db.commit()
        return patient.id


def make_stimulus(name="Rosto neutro 01", kind="image", status="active") -> str:
    with SessionLocal() as db:
        stimulus = Stimulus(
            name=name, kind=kind, status=status, original_filename=f"{name}.{'mp4' if kind == 'video' else 'jpg'}",
            format="mp4" if kind == "video" else "jpg", size_bytes=1000, sha256="0" * 64, width=640, height=400,
            duration_seconds=45.0 if kind == "video" else None,
        )
        db.add(stimulus)
        db.commit()
        return stimulus.id


def payload(patient_id, stimuli, **overrides):
    body = {
        "patient_id": patient_id,
        "title": "Rostos neutros e expressivos",
        "objective": "Comparar o tempo de fixação diante de rostos neutros, alegres e surpresos.",
        "notes": "",
        "record": True,
        "stimuli": stimuli,
    }
    body.update(overrides)
    return body


def create(client, patient_id, stimulus_ids, **overrides):
    items = [{"stimulus_id": sid, "duration_seconds": 5} for sid in stimulus_ids]
    r = client.post(f"{API}/sessions", json=payload(patient_id, items, **overrides))
    assert r.status_code == 201, r.text
    return r.json()


def set_session(session_id, **fields):
    with SessionLocal() as db:
        session = db.get(Session, session_id)
        for key, value in fields.items():
            setattr(session, key, value)
        db.commit()


def revoke(role, permission):
    with SessionLocal() as db:
        db.query(RolePermission).filter_by(role=role, permission=permission).delete()
        db.commit()


def test_create_from_the_wizard(client):
    researcher(client)
    pid = make_patient()
    face, video = make_stimulus(), make_stimulus("Ondas na praia", "video")
    manual = make_stimulus("Rosto alegre 02")
    items = [
        {"stimulus_id": face, "duration_seconds": 5},
        {"stimulus_id": video, "duration_seconds": 5},  # ignorado: vídeo avança sozinho
        {"stimulus_id": manual, "duration_seconds": None},
    ]
    r = client.post(f"{API}/sessions", json=payload(pid, items, notes="  "))
    assert r.status_code == 201, r.text
    s = r.json()
    assert (s["status"], s["visibility"], s["type"], s["record"]) == ("configured", "private", "media_sequence", True)
    assert s["owner"]["name"] == "Ana Souza"
    assert s["patient"] == {"id": pid, "code": "P-015", "name": "Beatriz Carvalho", "birth_date": "1995-07-21",
                            "sex": "female"}
    assert s["notes"] is None
    assert [(i["position"], i["name"], i["duration_seconds"]) for i in s["items"]] == [
        (1, "Rosto neutro 01", 5.0), (2, "Ondas na praia", None), (3, "Rosto alegre 02", None),
    ]
    assert s["items"][1]["media_duration_seconds"] == 45.0
    assert s["items"][0]["thumbnail_url"] == f"{API}/stimuli/{face}/thumbnail"
    assert (s["can_edit"], s["can_run"], s["can_change_visibility"]) == (True, True, False)

    entry = audit_entries(entity_type="session")[-1]
    assert (entry.action, entry.entity_label, entry.entity_id) == ("create", "Rostos neutros e expressivos, P-015", s["id"])
    changes = {c["label"]: c["after"] for c in entry.changes}
    assert changes["Paciente"] == "P-015"
    assert changes["Gravação"] == "Sim"
    assert changes["Visibilidade"] == "Privada"
    assert changes["Estímulos"] == "1. Rosto neutro 01 (5 s); 2. Ondas na praia (vídeo); 3. Rosto alegre 02 (troca manual)"


def test_create_validation(client):
    researcher(client)
    pid = make_patient()
    face = make_stimulus()

    r = client.post(f"{API}/sessions", json=payload(pid, []))
    assert r.status_code == 422
    assert "adicione pelo menos um estímulo" in r.text
    item = {"stimulus_id": face, "duration_seconds": 5}
    assert client.post(f"{API}/sessions", json=payload(pid, [item, item])).status_code == 422
    assert client.post(f"{API}/sessions", json=payload(pid, [item], title="  ")).status_code == 422
    assert client.post(f"{API}/sessions", json=payload(pid, [item], objective="")).status_code == 422
    bad_time = {"stimulus_id": face, "duration_seconds": 0}
    assert client.post(f"{API}/sessions", json=payload(pid, [bad_time])).status_code == 422

    archived = make_stimulus("Antigo", status="archived")
    r = client.post(f"{API}/sessions", json=payload(pid, [{"stimulus_id": archived}]))
    assert r.status_code == 409
    assert r.json()["detail"] == "o estímulo “Antigo” foi arquivado e não entra em novas sessões"
    draft = make_stimulus("Rascunho", status="draft")
    assert client.post(f"{API}/sessions", json=payload(pid, [{"stimulus_id": draft}])).status_code == 422

    inactive = make_patient("P-003", "Juliana Costa", status="inactive")
    r = client.post(f"{API}/sessions", json=payload(inactive, [item]))
    assert r.status_code == 409
    assert client.post(f"{API}/sessions", json=payload("naoexiste", [item])).status_code == 422
    assert audit_entries(entity_type="session") == []


def test_create_requires_the_permission(client):
    assert client.post(f"{API}/sessions", json={}).status_code == 401
    researcher(client)
    revoke("researcher", "sessions.run")
    r = client.post(f"{API}/sessions", json=payload(make_patient(), [{"stimulus_id": make_stimulus()}]))
    assert r.status_code == 403


def test_visibility_rules_in_the_list_and_detail(client):
    make_user("Bruno Castro", BRUNO, "researcher")
    make_user("Daniela Rocha", "daniela.rocha@exemplo.com", "researcher")
    admin_id = make_user()
    researcher(client)
    pid, face = make_patient(), make_stimulus()
    s = create(client, pid, [face])
    sid = s["id"]

    # Privada: Bruno não vê (nem pelo id); o admin vê, porque tem "Ver de outros".
    login(client, BRUNO)
    assert client.get(f"{API}/sessions").json()["total"] == 0
    assert client.get(f"{API}/sessions/{sid}").status_code == 404
    assert client.get(f"{API}/sessions/owners").json() == []
    login(client)
    assert client.get(f"{API}/sessions").json()["total"] == 1
    detail = client.get(f"{API}/sessions/{sid}").json()
    assert (detail["can_edit"], detail["can_run"], detail["can_change_visibility"]) == (True, False, True)

    # Compartilhada com Bruno: ele vê; Daniela não.
    candidates = client.get(f"{API}/sessions/{sid}/share-candidates").json()
    # O admin (Carlos) já vê todas: não aparece entre os que podem ser escolhidos.
    assert [c["name"] for c in candidates] == ["Bruno Castro", "Daniela Rocha"]
    bruno_id = next(c["id"] for c in candidates if c["name"] == "Bruno Castro")
    r = client.put(f"{API}/sessions/{sid}/visibility", json={"visibility": "shared", "user_ids": [bruno_id]})
    assert r.status_code == 200, r.text
    assert [u["name"] for u in r.json()["shared_with"]] == ["Bruno Castro"]
    login(client, BRUNO)
    rows = client.get(f"{API}/sessions").json()["items"]
    assert [(row["id"], row["visibility"], row["owner_name"]) for row in rows] == [(sid, "shared", "Ana Souza")]
    shared = client.get(f"{API}/sessions/{sid}").json()
    assert (shared["can_edit"], shared["can_run"]) == (False, False)
    assert client.patch(f"{API}/sessions/{sid}", json={"title": "Outro"}).status_code == 403
    login(client, "daniela.rocha@exemplo.com")
    assert client.get(f"{API}/sessions/{sid}").status_code == 404

    # Aberta a todos: Daniela também vê.
    login(client)
    r = client.put(f"{API}/sessions/{sid}/visibility", json={"visibility": "all", "user_ids": [bruno_id]})
    assert r.json()["shared_with"] == []
    login(client, "daniela.rocha@exemplo.com")
    assert client.get(f"{API}/sessions/{sid}").status_code == 200
    assert [o["name"] for o in client.get(f"{API}/sessions/owners").json()] == ["Ana Souza"]

    entries = audit_entries(action="visibility_change")
    assert [e.user_id for e in entries] == [admin_id, admin_id]
    assert entries[0].entity_label == "Rostos neutros e expressivos, P-015"
    assert entries[0].changes == [
        {"field": "visibility", "label": "Visibilidade", "before": "Privada", "after": "Compartilhada"},
        {"field": "shared_with", "label": "Pesquisadores com acesso", "before": None, "after": "Bruno Castro"},
    ]
    assert entries[1].changes[1] == {
        "field": "shared_with", "label": "Pesquisadores com acesso", "before": "Bruno Castro", "after": None,
    }


def test_visibility_change_rules(client):
    owner = researcher(client)
    s = create(client, make_patient(), [make_stimulus()])
    url = f"{API}/sessions/{s['id']}/visibility"
    # O pesquisador não tem "Alterar a visibilidade" na matriz padrão.
    assert client.put(url, json={"visibility": "all"}).status_code == 403
    assert client.get(f"{API}/sessions/{s['id']}/share-candidates").status_code == 403

    inactive = make_user("Fernanda Lopes", "fernanda.lopes@exemplo.com", "researcher", "inactive")
    admin(client)
    r = client.put(url, json={"visibility": "shared", "user_ids": []})
    assert r.status_code == 422 and r.json()["detail"] == "escolha pelo menos um pesquisador"
    for bad in (inactive, owner, "naoexiste"):
        assert client.put(url, json={"visibility": "shared", "user_ids": [bad]}).status_code == 422
    # Sem mudança, sem registro.
    assert client.put(url, json={"visibility": "private"}).status_code == 200
    assert audit_entries(action="visibility_change") == []


def test_edit_information(client):
    researcher(client)
    s = create(client, make_patient(), [make_stimulus()])
    url = f"{API}/sessions/{s['id']}"
    r = client.patch(url, json={"title": "Rostos alegres", "notes": "Paciente chegou cansado.", "record": False})
    assert r.status_code == 200, r.text
    assert (r.json()["title"], r.json()["notes"], r.json()["record"]) == ("Rostos alegres", "Paciente chegou cansado.", False)
    entry = audit_entries(action="update", entity_type="session")[-1]
    assert entry.entity_label == "Rostos alegres, P-015"
    assert [(c["label"], c["before"], c["after"]) for c in entry.changes] == [
        ("Título", "Rostos neutros e expressivos", "Rostos alegres"),
        ("Observações", None, "Paciente chegou cansado."),
        ("Gravação", "Sim", "Não"),
    ]

    # Sem mudança, sem registro; objetivo vazio é recusado.
    client.patch(url, json={"title": "Rostos alegres"})
    assert len(audit_entries(action="update", entity_type="session")) == 1
    assert client.patch(url, json={"objective": " "}).status_code == 422

    # Depois de executada, só as informações mudam; a gravação, não.
    set_session(s["id"], status="completed", started_at=datetime(2026, 9, 29, 17, 26, tzinfo=timezone.utc),
                ended_at=datetime(2026, 9, 29, 17, 27, 50, tzinfo=timezone.utc))
    assert client.patch(url, json={"record": True}).status_code == 409
    r = client.patch(url, json={"objective": "Outro objetivo."})
    assert r.status_code == 200
    assert r.json()["duration_seconds"] == 110
    assert r.json()["date"].startswith("2026-09-29T17:26")


def test_list_filters_and_pages(client):
    make_user("Bruno Castro", BRUNO, "researcher")
    admin(client)
    p15, p9 = make_patient(), make_patient("P-009", "Rafael Nunes")
    face = make_stimulus()
    first = create(client, p15, [face])
    second = create(client, p9, [face], title="Paisagens naturais")
    old = create(client, p9, [face], title="Imagens de alimentos")
    login(client, BRUNO)
    bruno = create(client, p15, [face], title="Leitura de textos curtos")
    login(client)
    # A data da executada é o início: "Paisagens" (em andamento) passa para o topo.
    set_session(old["id"], status="completed", started_at=datetime.now(timezone.utc) - timedelta(days=40))
    set_session(second["id"], status="running", started_at=datetime.now(timezone.utc))

    def ids(**params):
        return [row["id"] for row in client.get(f"{API}/sessions", params=params).json()["items"]]

    assert ids() == [second["id"], bruno["id"], first["id"], old["id"]]
    assert ids(q="paisagens") == [second["id"]]
    assert ids(q="P-009") == [second["id"], old["id"]]
    assert ids(q="beatriz") == [bruno["id"], first["id"]]
    assert ids(status="running") == [second["id"]]
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    assert old["id"] not in ids(since=since) and len(ids(since=since)) == 3
    owner_ids = {o["name"]: o["id"] for o in client.get(f"{API}/sessions/owners").json()}
    assert list(owner_ids) == ["Bruno Castro", "Carlos Lima"]
    assert ids(owner_id=owner_ids["Bruno Castro"]) == [bruno["id"]]
    page = client.get(f"{API}/sessions", params={"page": 2, "page_size": 3}).json()
    assert (page["total"], [r["id"] for r in page["items"]]) == (4, [old["id"]])
    assert client.get(f"{API}/sessions", params={"status": "outro"}).status_code == 422


def test_patient_name_only_with_the_patient_permission(client):
    researcher(client)
    s = create(client, make_patient(), [make_stimulus()])
    revoke("researcher", "patients.view")
    detail = client.get(f"{API}/sessions/{s['id']}").json()
    assert detail["patient"] == {"id": detail["patient"]["id"], "code": "P-015", "name": None, "birth_date": None,
                                 "sex": None}
    assert client.get(f"{API}/sessions", params={"q": "beatriz"}).json()["total"] == 0


def test_duplicate_for_another_patient(client):
    make_user("Bruno Castro", BRUNO, "researcher")
    researcher(client, ANA)
    face, archived = make_stimulus(), make_stimulus("Antigo")
    source = create(client, make_patient(), [face])
    other = make_patient("P-014", "Mariana Alves")
    copy = create(client, other, [face], duplicated_from_id=source["id"])
    assert copy["duplicated_from"] == {"id": source["id"], "title": "Rostos neutros e expressivos"}
    entry = audit_entries(action="create", entity_type="session")[-1]
    assert {c["label"]: c["after"] for c in entry.changes}["Duplicada de"] == "Rostos neutros e expressivos, P-015"
    assert archived  # o assistente deixa os arquivados de fora; o servidor recusa (test_create_validation)

    # Quem não vê a sessão de origem não consegue duplicá-la.
    login(client, BRUNO)
    item = [{"stimulus_id": face}]
    r = client.post(f"{API}/sessions", json=payload(other, item, duplicated_from_id=source["id"]))
    assert r.status_code == 404


def test_patients_stimuli_and_users_show_the_sessions(client):
    make_user("Bruno Castro", BRUNO, "researcher")
    researcher(client)
    p15 = make_patient(created_days_ago=60)
    p14 = make_patient("P-014", "Mariana Alves", created_days_ago=50)
    newest = make_patient("P-016", "Paciente Novo", created_days_ago=1)
    face, unused = make_stimulus(), make_stimulus("Nunca usado")
    s1 = create(client, p14, [face])
    set_session(s1["id"], started_at=datetime.now(timezone.utc) - timedelta(days=5), status="completed")
    s2 = create(client, p14, [face], title="Paisagens naturais")

    # W06: contagem, última sessão e a ordem pelo movimento mais recente.
    rows = client.get(f"{API}/patients").json()["items"]
    assert [(r["code"], r["sessions_count"]) for r in rows] == [("P-014", 2), ("P-016", 0), ("P-015", 0)]
    assert rows[0]["last_session_at"] is not None and rows[1]["last_session_at"] is None
    assert newest

    # W08: histórico com o número de estímulos.
    detail = client.get(f"{API}/patients/{p14}").json()
    assert detail["sessions_count"] == 2
    assert [(s["title"], s["owner_name"], s["stimuli_count"], s["status"]) for s in detail["sessions"]] == [
        ("Paisagens naturais", "Ana Souza", 1, "configured"),
        ("Rostos neutros e expressivos", "Ana Souza", 1, "completed"),
    ]

    # W11: "Usado em" e o estímulo usado não pode ser excluído.
    st = client.get(f"{API}/stimuli/{face}").json()
    assert (st["sessions_count"], st["can_delete"]) == (2, False)
    assert [s["id"] for s in st["sessions"]] == [s2["id"], s1["id"]]
    assert st["sessions"][0]["patient_code"] == "P-014"
    assert client.get(f"{API}/stimuli/{unused}").json()["can_delete"] is True

    # Outro pesquisador não vê as sessões privadas: nem na contagem, nem no histórico, nem no "Usado em".
    login(client, BRUNO)
    assert client.get(f"{API}/patients/{p14}").json()["sessions"] == []
    st = client.get(f"{API}/stimuli/{face}").json()
    assert (st["sessions_count"], st["sessions"]) == (2, [])

    # W20: sessões como responsável.
    admin(client)
    ana = next(u for u in client.get(f"{API}/users").json()["items"] if u["name"] == "Ana Souza")
    assert client.get(f"{API}/users/{ana['id']}").json()["sessions_as_owner"] == 2
    assert client.delete(f"{API}/stimuli/{face}").status_code == 409
