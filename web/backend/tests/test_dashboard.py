"""Início (W04): períodos, os números de cada visão, as listas, o selo do menu e as frases da auditoria."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.db import SessionLocal
from app.models import AuditLog, User, utcnow
from app.services import audit
from app.services.dashboard import periods

from .accounts import API, admin, login, make_user, researcher
from .test_sessions import BRUNO, create, make_patient, make_stimulus, revoke, set_session

SP = ZoneInfo("America/Sao_Paulo")


def local(*args) -> datetime:
    return datetime(*args, tzinfo=SP)


def test_periods_compare_with_the_same_stretch_of_the_previous_month():
    p = periods(local(2026, 10, 6, 14, 30).astimezone(timezone.utc), SP)
    assert (p.month_name, p.previous_month_name) == ("outubro", "setembro")
    assert p.month[0] == local(2026, 10, 1)
    assert p.previous_month == (local(2026, 9, 1), local(2026, 9, 6, 14, 30))
    assert p.today[0] == local(2026, 10, 6)
    assert p.yesterday == (local(2026, 10, 5), local(2026, 10, 5, 14, 30))
    assert len(p.weeks) == len(p.days) == 8
    assert p.weeks[-1][1] - p.weeks[-1][0] == timedelta(days=7)
    assert p.days[0][0] == local(2026, 9, 29) and p.days[-1][0] == local(2026, 10, 6)

    # Mês anterior mais curto: o trecho acaba no fim dele. Janeiro compara com dezembro.
    march = periods(local(2026, 3, 31, 10).astimezone(timezone.utc), SP)
    assert march.previous_month == (local(2026, 2, 1), local(2026, 3, 1))
    january = periods(local(2027, 1, 2).astimezone(timezone.utc), SP)
    assert (january.month_name, january.previous_month_name) == ("janeiro", "dezembro")


def executed(session_id, started_at, minutes=10, status="completed", received=True):
    ended = started_at + timedelta(minutes=minutes)
    set_session(session_id, status=status, started_at=started_at, ended_at=ended, end_reason="button_b",
                data_received_at=ended + timedelta(seconds=40) if received else None)


def middle(period):
    return period[0] + (min(period[1], utcnow()) - period[0]) / 2


def test_researcher_sees_own_sessions(client):
    make_user("Bruno Castro", BRUNO, "researcher")
    researcher(client)
    p = periods(utcnow(), SP)
    p1, p2, p3 = make_patient("P-001", "Paula"), make_patient("P-002", "Tiago"), make_patient("P-003", "Juliana")
    face, other = make_stimulus(), make_stimulus("Rosto alegre 02")

    running = create(client, p1, [face, other], title="Rostos ao vivo")["id"]
    set_session(running, status="running", started_at=utcnow() - timedelta(minutes=3))
    waiting = create(client, p2, [face], title="Paisagens naturais")["id"]
    executed(waiting, utcnow() - timedelta(hours=1), status="awaiting_data", received=False)
    this_month = create(client, p1, [face, other], title="Concluída no mês")["id"]
    executed(this_month, middle(p.month), minutes=20)
    last_month = create(client, p3, [face], title="Do mês passado")["id"]
    executed(last_month, middle(p.previous_month), minutes=5, status="interrupted")
    configured = create(client, p3, [face], title="Ainda configurada")["id"]

    # De Bruno, compartilhada com Ana e em andamento: não precisa da atenção dela.
    login(client, BRUNO)
    bruno = create(client, p1, [face], title="Sessão do Bruno")["id"]
    set_session(bruno, status="running", started_at=utcnow(), visibility="all")
    login(client, "ana.souza@exemplo.com")

    d = client.get(f"{API}/dashboard", params={"tz": "America/Sao_Paulo"}).json()
    assert d["view"] == "researcher"
    assert d["badge"] == 2
    assert client.get(f"{API}/dashboard/badge").json() == {"sessions": 2}
    assert (d["users"], d["audit"], d["audit_entries"]) == (None, None, None)

    # Em andamento primeiro; o pesquisador responsável abre o controle.
    assert [(a["id"], a["status"], a["data_status"], a["can_run"]) for a in d["attention"]] == [
        (running, "running", "none", True), (waiting, "awaiting_data", "waiting", True),
    ]
    assert d["attention"][0]["patient_code"] == "P-001"

    # Sessões do mês: as que começaram nele (a em andamento, a aguardando e a concluída, ou só
    # parte delas se o mês começou há menos de uma hora).
    recent_starts = (utcnow() - timedelta(minutes=3), utcnow() - timedelta(hours=1))
    if all(start >= p.month[0] for start in recent_starts):  # fora da primeira hora do mês
        assert d["sessions"]["value"] == 3
        assert d["patients"]["value"] == 2
        assert d["sessions"]["previous"] == 1
        assert d["patients"]["previous"] == 1
        assert d["collection_seconds"]["previous"] == 300
    assert d["sessions"]["series"][-1] >= 2
    assert d["awaiting"]["value"] == 1
    assert (d["awaiting"]["latest_id"], d["awaiting"]["latest_title"], d["awaiting"]["latest_data_status"]) == (
        waiting, "Paisagens naturais", "waiting")
    # Retrato no fim de cada semana: agora, só a que ainda espera os dados (a concluída esperou 40 s).
    assert d["awaiting"]["series"][-1] == 1

    # Recentes: as próprias, sem a em andamento, a mais nova primeiro.
    recent = [(r["id"], r["stimuli_count"]) for r in d["recent"]]
    assert running not in [r for r, _ in recent] and bruno not in [r for r, _ in recent]
    # A configurada entra pela data em que foi configurada (agora).
    assert recent[:2] == [(configured, 1), (waiting, 1)]
    assert {r for r, _ in recent} == {waiting, this_month, last_month, configured}
    assert d["month"] and d["previous_month"]


def test_admin_sees_the_lab_users_and_audit(client):
    make_user("Ana Souza", "ana.souza@exemplo.com", "researcher")
    make_user("Igor Mendes", "igor.mendes@exemplo.com", "researcher", "invited", None)
    make_user("Fernanda Lopes", "fernanda.lopes@exemplo.com", "researcher", "inactive")
    admin_id = admin(client)
    login(client, "ana.souza@exemplo.com")
    sid = create(client, make_patient(), [make_stimulus()])["id"]
    set_session(sid, status="running", started_at=utcnow())
    login(client)

    p = periods(utcnow(), SP)
    with SessionLocal() as db:
        me = db.get(User, admin_id)
        # Ontem antes da mesma hora (conta) e depois dela (não conta).
        audit.record(db, None, me, "login", "system", "Acesso ao sistema", at=p.yesterday[0] + timedelta(seconds=1))
        if p.yesterday[1] < p.today[0] - timedelta(seconds=1):
            audit.record(db, None, me, "login", "system", "Acesso ao sistema", at=p.today[0] - timedelta(seconds=1))
        db.commit()
        today = [e for e in db.query(AuditLog) if e.created_at >= p.today[0]]

    d = client.get(f"{API}/dashboard", params={"tz": "America/Sao_Paulo"}).json()
    assert d["view"] == "admin"
    assert d["badge"] == 1
    assert d["attention"][0]["can_run"] is False
    assert d["attention"][0]["owner_name"] == "Ana Souza"
    assert d["users"]["active"] == 2 and d["users"]["invited"] == 1
    assert d["users"]["series"][-1] == 2
    assert d["audit"]["today"] == len(today)
    assert d["audit"]["yesterday"] == 1
    assert sum(d["audit"]["series"]) >= len(today) + 1
    # Os logins contam nos registros de hoje, mas ficam fora das últimas ações.
    assert [line["text"] for line in d["audit_entries"]] == ["Criou a sessão Rostos neutros e expressivos"]
    assert d["audit_entries"][0]["user_name"] == "Ana Souza"

    # Sem "Consultar a auditoria", a parte da auditoria some.
    revoke("admin", "admin.audit")
    d = client.get(f"{API}/dashboard").json()
    assert (d["audit"], d["audit_entries"]) == (None, None)
    assert d["users"] is not None


def test_dashboard_requires_login(client):
    assert client.get(f"{API}/dashboard").status_code == 401
    assert client.get(f"{API}/dashboard/badge").status_code == 401


def test_unknown_timezone_falls_back_to_utc(client):
    researcher(client)
    r = client.get(f"{API}/dashboard", params={"tz": "Lugar/Nenhum"})
    assert r.status_code == 200
    assert r.json()["badge"] == 0


def entry(action, entity_type, label, entity_id="x", user_id="u", changes=None) -> AuditLog:
    return AuditLog(action=action, entity_type=entity_type, entity_label=label, entity_id=entity_id,
                    user_id=user_id, changes=changes or [])


def change(field, after):
    return {"field": field, "label": field, "before": None, "after": after}


def test_audit_summaries_as_in_the_prototype():
    s = audit.summary
    assert s(entry("session_start", "session", "Rostos neutros e expressivos, P-014")) == \
        "Iniciou a sessão Rostos neutros e expressivos"
    assert s(entry("session_end", "session", "Paisagens naturais, P-009")) == "Encerrou a sessão Paisagens naturais"
    assert s(entry("create", "user", "Igor Mendes")) == "Criou o usuário Igor Mendes"
    batch = [change(f"stimulus:{i}", "Imagem") for i in range(6)]
    assert s(entry("create", "stimulus", "6 imagens enviadas à biblioteca", None, changes=batch)) == "Enviou 6 estímulos"
    assert s(entry("visibility_change", "session", "Leitura de textos curtos, P-007")) == \
        "Alterou a visibilidade da sessão Leitura de textos curtos"
    # O título com vírgula continua inteiro: só o código do paciente sai.
    assert s(entry("create", "session", "Rostos, neutros, P-001")) == "Criou a sessão Rostos, neutros"
    assert s(entry("create", "stimulus", "Rosto 01")) == "Enviou o estímulo Rosto 01"
    assert s(entry("create", "patient", "P-015")) == "Cadastrou o paciente P-015"
    assert s(entry("update", "patient", "P-015", changes=[change("status", "Inativo")])) == "Inativou o paciente P-015"
    assert s(entry("update", "stimulus", "Rosto 01", changes=[change("status", "Na biblioteca")])) == \
        "Desarquivou o estímulo Rosto 01"
    assert s(entry("update", "user", "Ana", "u", "u", [change("password", "Alterada")])) == "Alterou a senha"
    assert s(entry("update", "user", "Ana", "u", "u", [change("status", "Ativo"), change("password", "Criada")])) == \
        "Aceitou o convite"
    assert s(entry("update", "permissions", "Perfis e permissões", None)) == "Alterou os perfis e permissões"
    assert s(entry("password_reset", "user", "Ana", "u", "u")) == "Pediu a redefinição de senha"
    assert s(entry("password_reset", "user", "Ana", "a", "u")) == "Enviou a redefinição de senha para Ana"
    assert s(entry("export", "session", "Paisagens naturais, P-009")) == "Exportou os dados da sessão Paisagens naturais"
    assert s(entry("export", "system", "Registros da auditoria (CSV)", None)) == "Exportou os registros da auditoria"
    assert s(entry("login", "system", "Acesso ao sistema", None)) == "Entrou no sistema"
