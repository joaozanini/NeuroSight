"""Matriz de perfis e permissões (W21): leitura, gravação, permissões travadas e efeito imediato."""
from .accounts import API, admin, audit_entries, login, make_user, researcher


def matrix(client):
    r = client.get(f"{API}/permissions")
    assert r.status_code == 200
    return r.json()


def test_matrix_has_the_twelve_permissions_of_the_prototype(client):
    admin(client)
    m = matrix(client)
    assert [r["label"] for r in m["roles"]] == ["Admin", "Pesquisador"]
    assert [g["label"] for g in m["groups"]] == ["Pacientes", "Estímulos", "Sessões", "Administração"]
    labels = [p["label"] for g in m["groups"] for p in g["permissions"]]
    assert len(labels) == 12
    assert labels[6] == "Ver sessões de outros pesquisadores"
    assert m["groups"][2]["permissions"][1]["description"].startswith("Sem esta permissão")
    assert len(m["grants"]["admin"]) == 12
    assert m["grants"]["researcher"] == ["patients.view", "patients.edit", "stimuli.edit", "sessions.run", "sessions.export"]
    assert m["locked"] == {"admin": ["admin.permissions", "admin.users"]}


def test_only_who_can_change_permissions_sees_the_matrix(client):
    assert client.get(f"{API}/permissions").status_code == 401
    researcher(client)
    assert client.get(f"{API}/permissions").status_code == 403
    assert client.put(f"{API}/permissions", json={"grants": {}}).status_code == 403


def test_saving_changes_what_the_researcher_can_do_right_away(client):
    admin(client)
    make_user("Ana Souza", "ana.souza@exemplo.com", "researcher")
    m = matrix(client)
    grants = m["grants"]
    grants["researcher"] = [p for p in grants["researcher"] if p != "sessions.export"] + ["admin.audit"]
    r = client.put(f"{API}/permissions", json={"grants": grants})
    assert r.status_code == 200
    assert "admin.audit" in r.json()["grants"]["researcher"]

    [entry] = audit_entries(entity_type="permissions")
    assert (entry.action, entry.entity_label) == ("update", "Perfis e permissões")
    assert entry.changes == [
        {"field": "researcher:sessions.export", "label": "Pesquisador · Exportar os dados das sessões", "before": "Sim", "after": "Não"},
        {"field": "researcher:admin.audit", "label": "Pesquisador · Consultar a auditoria", "before": "Não", "after": "Sim"},
    ]

    login(client, "ana.souza@exemplo.com")
    me = client.get(f"{API}/me").json()
    assert "admin.audit" in me["permissions"] and "sessions.export" not in me["permissions"]
    assert client.get(f"{API}/audit").status_code == 200
    assert client.get(f"{API}/users").status_code == 403


def test_admin_locked_permissions_cannot_be_removed(client):
    admin(client)
    grants = matrix(client)["grants"]
    grants["admin"] = ["patients.view"]
    r = client.put(f"{API}/permissions", json={"grants": grants})
    assert set(r.json()["grants"]["admin"]) == {"patients.view", "admin.users", "admin.permissions"}
    changed = {c["field"] for c in audit_entries(entity_type="permissions")[0].changes}
    assert "admin:admin.users" not in changed and "admin:admin.audit" in changed
    # Continua conseguindo administrar.
    assert client.get(f"{API}/users").status_code == 200


def test_saving_the_same_matrix_records_nothing_and_unknown_ids_are_refused(client):
    admin(client)
    grants = matrix(client)["grants"]
    assert client.put(f"{API}/permissions", json={"grants": grants}).status_code == 200
    assert audit_entries(entity_type="permissions") == []
    assert client.put(f"{API}/permissions", json={"grants": {"researcher": ["voar"]}}).status_code == 422
    assert client.put(f"{API}/permissions", json={"grants": {"dono": []}}).status_code == 422
