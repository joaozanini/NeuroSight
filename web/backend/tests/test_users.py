"""Administração de usuários (W19, W20): lista, convite, edição, desativação e os links."""
import pytest
from fastapi.testclient import TestClient

from app.services import accounts, mailer

from .accounts import API, PASSWORD, admin, audit_entries, login, make_user, researcher, token_from


@pytest.fixture
def other_client(client):
    from app.main import app

    return TestClient(app)


def test_needs_login_and_the_permission(client):
    assert client.get(f"{API}/users").status_code == 401
    researcher(client)
    assert client.get(f"{API}/users").status_code == 403
    assert client.post(f"{API}/users", json={"name": "X", "email": "x@exemplo.com", "role": "admin"}).status_code == 403


def test_list_puts_you_first_inactive_last_and_filters(client):
    me = admin(client)
    make_user("Ana Souza", "ana.souza@exemplo.com", "researcher")
    make_user("Fernanda Lopes", "fernanda.lopes@exemplo.com", "researcher", "inactive")
    make_user("Igor Mendes", "igor.mendes@exemplo.com", "researcher", "invited", None)
    make_user("Bruno Castro", "bruno.castro@exemplo.com", "researcher")

    page = client.get(f"{API}/users").json()
    assert [u["name"] for u in page["items"]] == ["Carlos Lima", "Ana Souza", "Bruno Castro", "Igor Mendes", "Fernanda Lopes"]
    assert page["items"][0]["id"] == me
    assert (page["total"], page["page"], page["page_size"]) == (5, 1, 8)
    assert set(page["items"][0]) == {"id", "name", "email", "role", "status", "last_login_at", "created_at"}
    assert page["items"][0]["last_login_at"].endswith("Z") or "+00:00" in page["items"][0]["last_login_at"]

    def names(**params):
        return [u["name"] for u in client.get(f"{API}/users", params=params).json()["items"]]

    assert names(q="SOUZA") == ["Ana Souza"]
    assert names(q="bruno.castro@") == ["Bruno Castro"]
    assert names(q="%") == []
    assert names(role="admin") == ["Carlos Lima"]
    assert names(status="invited") == ["Igor Mendes"]
    second = client.get(f"{API}/users", params={"page": 2, "page_size": 2}).json()
    assert [u["name"] for u in second["items"]] == ["Bruno Castro", "Igor Mendes"]


def test_create_invites_and_records_the_creation(client):
    me = admin(client)
    r = client.post(f"{API}/users", json={"name": "  Igor   Mendes ", "email": "Igor.Mendes@Exemplo.com", "role": "researcher"})
    assert r.status_code == 201
    body = r.json()
    user = body["user"]
    assert (user["name"], user["email"], user["role"], user["status"]) == ("Igor Mendes", "igor.mendes@exemplo.com", "researcher", "invited")
    assert user["created_by_name"] == "Carlos Lima"
    assert user["last_login_at"] is None
    assert body["invite"]["email_sent"] is False
    assert token_from(body["invite"]["link"])

    [entry] = audit_entries(action="create")
    assert (entry.user_id, entry.entity_type, entry.entity_id, entry.entity_label) == (me, "user", user["id"], "Igor Mendes")
    assert entry.changes == [
        {"field": "name", "label": "Nome", "before": None, "after": "Igor Mendes"},
        {"field": "email", "label": "E-mail", "before": None, "after": "igor.mendes@exemplo.com"},
        {"field": "role", "label": "Perfil", "before": None, "after": "Pesquisador"},
        {"field": "status", "label": "Status", "before": None, "after": "Convite pendente"},
    ]


def test_create_refuses_duplicate_or_invalid_email(client):
    admin(client)
    r = client.post(f"{API}/users", json={"name": "Outro", "email": "CARLOS.LIMA@exemplo.com", "role": "admin"})
    assert r.status_code == 409
    assert r.json()["detail"] == "já existe um usuário com este e-mail"
    assert client.post(f"{API}/users", json={"name": "Outro", "email": "sem-arroba", "role": "admin"}).status_code == 422
    assert client.post(f"{API}/users", json={"name": "   ", "email": "a@exemplo.com", "role": "admin"}).status_code == 422
    assert client.post(f"{API}/users", json={"name": "A", "email": "a@exemplo.com", "role": "dono"}).status_code == 422


def test_with_smtp_the_link_is_not_shown(client, monkeypatch):
    sent = []
    monkeypatch.setattr(mailer, "send", lambda *args: sent.append(args) or True)
    admin(client)
    r = client.post(f"{API}/users", json={"name": "Igor Mendes", "email": "igor.mendes@exemplo.com", "role": "researcher"})
    assert r.json()["invite"]["email_sent"] is True
    assert r.json()["invite"]["link"] is None
    [(name, email, subject, text)] = sent
    assert (name, email, subject) == ("Igor Mendes", "igor.mendes@exemplo.com", "Seu acesso ao NeuroSight")
    assert "Carlos Lima criou uma conta para você" in text
    assert "http://site.teste/aceitar-convite?token=" in text
    assert "vale por 7 dias" in text


def test_edit_records_the_diff(client):
    me = admin(client)
    uid = make_user("Bruno Castro", "bruno.castro@exemplo.com", "researcher")
    r = client.get(f"{API}/users/{uid}")
    assert r.json()["sessions_as_owner"] == 0

    r = client.patch(f"{API}/users/{uid}", json={"name": "Bruno C. Castro", "role": "admin", "email": "bruno.castro@exemplo.com"})
    assert r.status_code == 200
    assert (r.json()["name"], r.json()["role"]) == ("Bruno C. Castro", "admin")
    [entry] = audit_entries(action="update")
    assert entry.user_id == me
    assert entry.entity_label == "Bruno C. Castro"
    assert entry.changes == [
        {"field": "name", "label": "Nome", "before": "Bruno Castro", "after": "Bruno C. Castro"},
        {"field": "role", "label": "Perfil", "before": "Pesquisador", "after": "Admin"},
    ]

    # Salvar sem mudar nada não gera registro.
    client.patch(f"{API}/users/{uid}", json={"name": "Bruno C. Castro", "status": "active"})
    assert len(audit_entries(action="update")) == 1


def test_edit_guards(client):
    me = admin(client)
    uid = make_user("Ana Souza", "ana.souza@exemplo.com", "researcher")
    assert client.patch(f"{API}/users/{me}", json={"role": "researcher"}).status_code == 409
    assert client.patch(f"{API}/users/{me}", json={"status": "inactive"}).status_code == 409
    assert client.patch(f"{API}/users/{me}", json={"name": "Carlos A. Lima"}).status_code == 200
    r = client.patch(f"{API}/users/{uid}", json={"email": "carlos.lima@exemplo.com"})
    assert r.status_code == 409
    assert client.patch(f"{API}/users/nao-existe", json={"name": "X"}).status_code == 404
    assert client.patch(f"{API}/users/{uid}", json={"status": "invited"}).status_code == 422


def test_the_last_active_admin_cannot_be_removed(client):
    carlos = admin(client)
    grant_researchers(client, "admin.users")
    researcher(client)  # Ana gerencia usuários, mas não é admin
    for change in ({"status": "inactive"}, {"role": "researcher"}):
        r = client.patch(f"{API}/users/{carlos}", json=change)
        assert r.status_code == 409
        assert r.json()["detail"] == "o sistema precisa de pelo menos um admin ativo"
    make_user("Gustavo Prado", "gustavo.prado@exemplo.com", "admin")
    assert client.patch(f"{API}/users/{carlos}", json={"status": "inactive"}).status_code == 200


def test_deactivating_blocks_access_at_once_and_reactivating_restores_it(client, other_client):
    admin(client)
    uid = make_user("Ana Souza", "ana.souza@exemplo.com", "researcher")
    login(other_client, "ana.souza@exemplo.com")
    assert other_client.get(f"{API}/me").status_code == 200

    r = client.patch(f"{API}/users/{uid}", json={"status": "inactive"})
    assert r.json()["status"] == "inactive"
    assert other_client.get(f"{API}/me").status_code == 401
    r = other_client.post(f"{API}/auth/login", json={"email": "ana.souza@exemplo.com", "password": PASSWORD})
    assert r.status_code == 403
    [entry] = audit_entries(action="update")
    assert entry.changes == [{"field": "status", "label": "Status", "before": "Ativo", "after": "Inativo"}]

    assert client.patch(f"{API}/users/{uid}", json={"status": "active"}).json()["status"] == "active"
    # Reativar não ressuscita a sessão antiga: precisa entrar de novo.
    assert other_client.get(f"{API}/me").status_code == 401
    login(other_client, "ana.souza@exemplo.com")


def test_reactivating_someone_who_never_set_a_password_goes_back_to_the_invite(client):
    admin(client)
    r = client.post(f"{API}/users", json={"name": "Igor Mendes", "email": "igor.mendes@exemplo.com", "role": "researcher"})
    uid, old_link = r.json()["user"]["id"], r.json()["invite"]["link"]
    client.patch(f"{API}/users/{uid}", json={"status": "inactive"})
    # Desativar invalida o convite pendente.
    assert client.get(f"{API}/auth/link", params={"token": token_from(old_link), "kind": "invite"}).status_code == 404
    assert client.patch(f"{API}/users/{uid}", json={"status": "active"}).json()["status"] == "invited"


def test_resend_invite(client):
    admin(client)
    r = client.post(f"{API}/users", json={"name": "Igor Mendes", "email": "igor.mendes@exemplo.com", "role": "researcher"})
    uid, first = r.json()["user"]["id"], r.json()["invite"]["link"]
    r = client.post(f"{API}/users/{uid}/resend-invite")
    assert r.status_code == 200
    second = r.json()["link"]
    assert second != first
    assert client.get(f"{API}/auth/link", params={"token": token_from(first), "kind": "invite"}).status_code == 404
    assert client.get(f"{API}/auth/link", params={"token": token_from(second), "kind": "invite"}).status_code == 200
    [entry] = audit_entries(action="invite")
    assert entry.changes[0]["after"] == "Reenviado para igor.mendes@exemplo.com"

    active = make_user("Ana Souza", "ana.souza@exemplo.com", "researcher")
    assert client.post(f"{API}/users/{active}/resend-invite").status_code == 409


def test_send_reset_keeps_the_current_password_until_the_link_is_used(client, other_client):
    admin(client)
    uid = make_user("Bruno Castro", "bruno.castro@exemplo.com", "researcher")
    r = client.post(f"{API}/users/{uid}/send-reset")
    assert r.status_code == 200
    link = r.json()["link"]
    assert link.startswith("http://site.teste/redefinir-senha?token=")
    login(other_client, "bruno.castro@exemplo.com")
    [entry] = audit_entries(action="password_reset")
    assert entry.entity_id == uid

    invited = make_user("Igor Mendes", "igor.mendes@exemplo.com", "researcher", "invited", None)
    assert client.post(f"{API}/users/{invited}/send-reset").status_code == 409


def grant_researchers(client, permission: str) -> None:
    grants = client.get(f"{API}/permissions").json()["grants"]
    grants["researcher"].append(permission)
    assert client.put(f"{API}/permissions", json={"grants": grants}).status_code == 200


def test_snapshot_uses_the_labels():
    from app.models import User

    assert accounts.snapshot(User(name="A", email="a@b.c", role="researcher", status="invited")) == {
        "name": "A", "email": "a@b.c", "role": "Pesquisador", "status": "Convite pendente",
    }
