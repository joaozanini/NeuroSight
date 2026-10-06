"""Prepara o banco para o primeiro uso: aplica as migrações, semeia a matriz de permissões e cria
o primeiro admin, mostrando o link do convite.

    python -m app.seed --admin-email ana@lab.br --admin-name "Ana Souza"
    python -m app.seed --demo        # também cria usuários, pacientes, estímulos e sessões de exemplo

Pode rodar de novo sem estragar nada: o que já existe fica como está. Rodar com o e-mail de um
admin que ainda não aceitou o convite gera um link novo (o anterior deixa de valer).
"""
import argparse
import io
import sys
import tempfile
import time as clock
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from . import seed_media, seed_tracking
from .db import SessionLocal, migrate
from .models import Patient, Session, SessionShare, SessionStimulus, Stimulus, User, utcnow
from .services import accounts, audit, execution, passwords, permissions, tokens
from .services import patients as patient_rules
from .services import sessions as session_rules
from .services import stimuli as stimulus_rules

DEMO_PASSWORD = "NeuroSight#2026"

# Usuários da W19. O primeiro é o admin da demonstração. Cada um é cadastrado há tantas horas, para o
# Início (W04) e a auditoria terem uma história: Igor, o convite pendente, entrou hoje.
DEMO_USERS = [
    ("Carlos Lima", "carlos.lima@exemplo.com", "admin", "active", 75 * 24),
    ("Ana Souza", "ana.souza@exemplo.com", "researcher", "active", 72 * 24),
    ("Igor Mendes", "igor.mendes@exemplo.com", "researcher", "invited", 5),
    ("Bruno Castro", "bruno.castro@exemplo.com", "researcher", "active", 70 * 24),
    ("Gustavo Prado", "gustavo.prado@exemplo.com", "admin", "active", 66 * 24),
    ("Daniela Rocha", "daniela.rocha@exemplo.com", "researcher", "active", 45 * 24),
    ("Eduardo Martins", "eduardo.martins@exemplo.com", "researcher", "active", 20 * 24),
    ("Fernanda Lopes", "fernanda.lopes@exemplo.com", "researcher", "inactive", 60 * 24),
]
# Os estímulos de exemplo foram enviados à biblioteca há tantos dias, antes das sessões.
DEMO_STIMULI_DAYS = 35


# Pacientes da W06 (os oito visíveis) e mais sete, para fechar os 15 do subtítulo. A data do TCLE
# vazia quer dizer termo ainda não assinado; os assinados levam um PDF de exemplo.
DEMO_PATIENTS = [
    # código, nome, nascimento, sexo, óculos ou lentes, assinatura do TCLE, observações
    ("P-001", "Paula Ribeiro", "1985-05-19", "female", "none", "2026-08-03", None),
    ("P-002", "Tiago Almeida", "1992-10-27", "male", "glasses", "2026-08-03", None),
    ("P-003", "Juliana Costa", "2000-02-14", "female", "contacts", "2026-08-10", None),
    ("P-004", "André Barbosa", "1979-07-08", "male", "none", "2026-08-12", None),
    ("P-005", "Sofia Mendes", "2004-03-22", "female", "none", "2026-08-17", None),
    ("P-006", "Ricardo Gomes", "1988-12-01", "male", "glasses", "2026-08-20", None),
    ("P-007", "Camila Teixeira", "1987-09-14", "female", "contacts", "2026-08-24", None),
    ("P-008", "Felipe Duarte", "1993-04-02", "male", "none", "2026-08-26", None),
    ("P-009", "Rafael Nunes", "2001-11-05", "male", "none", "2026-08-28", None),
    ("P-010", "Larissa Pinto", "1999-12-17", "female", "glasses", "2026-08-31", None),
    ("P-011", "Lucas Ferreira", "1990-01-30", "male", "contacts", "2026-08-31", None),
    ("P-012", "Gabriel Moura", "2003-06-08", "male", "none", "2026-09-01", None),
    ("P-013", "Vanessa Rocha", "1996-08-11", "undisclosed", "none", None, None),
    ("P-014", "Mariana Alves", "1998-03-12", "female", "glasses", "2026-09-01", "Prefere sessões no período da manhã."),
    ("P-015", "Beatriz Carvalho", "1995-07-21", "female", "none", "2026-09-02", None),
]


# Sessões da W12 (as 23 que Ana Souza vê nos últimos 30 dias, com as contagens da W06) e mais três
# que só o admin vê. As datas são relativas a hoje: "dias atrás" 0 é a sessão em andamento.
ANA, BRUNO, DANIELA = "ana.souza@exemplo.com", "bruno.castro@exemplo.com", "daniela.rocha@exemplo.com"
DEMO_SESSIONS = [
    # dias atrás, título, paciente, responsável, status, visibilidade, compartilhada com, sequência
    (0, "Rostos neutros e expressivos", "P-014", ANA, "running", "private", (), "rostos"),
    (0, "Paisagens naturais", "P-009", ANA, "awaiting_data", "private", (), "paisagens"),
    (1, "Rostos neutros e expressivos", "P-015", ANA, "configured", "private", (), "rostos"),
    (4, "Publicidade em vídeo", "P-011", BRUNO, "interrupted", "shared", (ANA,), "videos"),
    (5, "Leitura de textos curtos", "P-007", BRUNO, "completed", "all", (), "leitura"),
    (7, "Imagens de alimentos", "P-012", ANA, "completed", "shared", (BRUNO,), "alimentos"),
    (11, "Rostos neutros e expressivos", "P-010", ANA, "completed", "private", (), "rostos"),
    (14, "Paisagens naturais", "P-008", ANA, "interrupted", "private", (), "paisagens"),
    (16, "Rostos neutros e expressivos", "P-014", ANA, "completed", "private", (), "rostos"),
    (17, "Imagens de alimentos", "P-001", ANA, "completed", "private", (), "alimentos"),
    (19, "Paisagens naturais", "P-014", ANA, "completed", "private", (), "paisagens"),
    (20, "Imagens de alimentos", "P-009", ANA, "completed", "private", (), "alimentos"),
    (21, "Leitura de textos curtos", "P-007", BRUNO, "completed", "all", (), "leitura"),
    (22, "Paisagens naturais", "P-002", ANA, "completed", "private", (), "paisagens"),
    (23, "Paisagens naturais", "P-010", ANA, "completed", "private", (), "paisagens"),
    (24, "Rostos neutros e expressivos", "P-002", ANA, "completed", "private", (), "rostos"),
    (25, "Rostos neutros e expressivos", "P-006", ANA, "completed", "private", (), "rostos"),
    (26, "Paisagens naturais", "P-006", ANA, "completed", "private", (), "paisagens"),
    (27, "Rostos neutros e expressivos", "P-005", ANA, "interrupted", "private", (), "rostos"),
    (28, "Imagens de alimentos", "P-005", ANA, "completed", "private", (), "alimentos"),
    (28, "Publicidade em vídeo", "P-003", BRUNO, "completed", "all", (), "videos"),
    (29, "Paisagens naturais", "P-004", ANA, "completed", "private", (), "paisagens"),
    (29, "Rostos neutros e expressivos", "P-004", ANA, "completed", "private", (), "rostos"),
    (2, "Publicidade em vídeo", "P-003", BRUNO, "configured", "private", (), "videos"),
    (6, "Rostos neutros e expressivos", "P-001", DANIELA, "completed", "private", (), "rostos"),
    (9, "Paisagens naturais", "P-006", DANIELA, "awaiting_data", "private", (), "paisagens"),
]
# Sequências: (nome do estímulo, segundos na tela); vídeos e trocas manuais levam None.
DEMO_SEQUENCES = {
    "rostos": [(f"{label} {i:02d}", 5.0) for i in range(1, 13) for _, label, _ in [seed_media.EXPRESSIONS[(i - 1) % 3]]],
    "paisagens": [("Montanhas ao amanhecer", 8.0), ("Lago e floresta", 8.0), ("Ondas na praia", None),
                  ("Floresta com vento", None)],
    "videos": [("Ondas na praia", None), ("Floresta com vento", None)],
    "leitura": [("Montanhas ao amanhecer", 10.0), ("Lago e floresta", 10.0)],
    "alimentos": [("Frutas sobre a mesa", None), ("Montanhas ao amanhecer", 6.0)],
}
DEMO_OBJECTIVES = {
    "rostos": "Comparar o tempo de fixação e as expressões faciais diante de rostos neutros, alegres e surpresos.",
    "paisagens": "Observar a exploração visual de paisagens estáticas e em movimento.",
    "videos": "Medir a atenção a vídeos curtos, como em uma peça publicitária.",
    "leitura": "Acompanhar o percurso do olhar durante a leitura de imagens com detalhes finos.",
    "alimentos": "Comparar a atenção a imagens de alimentos com a de paisagens.",
}


def _create(db: DbSession, name: str, email: str, role: str, status: str, password: str | None,
            created_by: User | None, created_at: datetime | None = None) -> User:
    user = User(
        name=name, email=email.strip().lower(), role=role, status=status,
        password_hash=passwords.hash_password(password) if password else None,
        created_by_id=created_by.id if created_by else None,
    )
    if created_at is not None:
        user.created_at = created_at
    db.add(user)
    db.flush()
    audit.record(db, None, created_by, "create", "user", user.name, user.id,
                 audit.diff({}, accounts.snapshot(user), accounts.USER_FIELD_LABELS), at=created_at)
    return user


def _invite(db: DbSession, user: User, created_by: User | None) -> None:
    raw, link = tokens.issue_link(db, user, "invite", created_by=created_by)
    db.commit()
    sent = accounts.send_link(user, raw, link, invited_by=created_by.name if created_by else None)
    where = "enviado por e-mail" if sent.email_sent else "não enviado por e-mail"
    print(f"  Convite de {user.name} <{user.email}> ({where}), vale até {sent.expires_at:%d/%m/%Y %H:%M} UTC:")
    print(f"    {sent.link}")


def seed_admin(db: DbSession, email: str, name: str) -> None:
    email = email.strip().lower()
    user = accounts.find_by_email(db, email)
    if user is None:
        user = _create(db, name, email, "admin", "invited", None, None)
        print(f"Primeiro admin criado: {user.name} <{user.email}>")
        _invite(db, user, None)
    elif user.status == "invited":
        print(f"{user.email} ainda não aceitou o convite; gerando um link novo.")
        _invite(db, user, None)
    else:
        print(f"{user.email} já existe ({accounts.STATUS_LABELS[user.status]}); nada a fazer.")


def seed_demo(db: DbSession, password: str) -> None:
    admin = db.scalar(select(User).where(User.role == "admin", User.status == "active").order_by(User.created_at))
    print(f"Usuários de exemplo (senha dos ativos e inativos: {password}):")
    now = utcnow().replace(second=0, microsecond=0)
    for name, email, role, status, hours in DEMO_USERS:
        if accounts.find_by_email(db, email):
            print(f"  {email}: já existe")
            continue
        user = _create(db, name, email, role, status, None if status == "invited" else password, admin,
                       now - timedelta(hours=hours))
        admin = admin or user
        db.commit()
        print(f"  {email}: {permissions.ROLE_LABELS[role]}, {accounts.STATUS_LABELS[status]}")
        if status == "invited":
            _invite(db, user, admin)


def seed_demo_patients(db: DbSession, actor: User | None) -> None:
    created = []
    for code, name, birth, sex, vision, signed_on, notes in DEMO_PATIENTS:
        if patient_rules.find_by_code(db, code):
            continue
        # Cadastrado no dia da assinatura do termo, antes das sessões de exemplo.
        registered_at = datetime.combine(date.fromisoformat(signed_on or "2026-09-03"), time(13), timezone.utc)
        patient = Patient(
            code=code, name=name, birth_date=date.fromisoformat(birth), sex=sex, vision_correction=vision,
            consent_signed=signed_on is not None, consent_date=date.fromisoformat(signed_on) if signed_on else None,
            notes=notes, status="active", created_by_id=actor.id if actor else None, created_at=registered_at,
        )
        db.add(patient)
        db.flush()
        if signed_on:
            pdf = seed_media.minimal_pdf(f"Termo de consentimento - {code} (exemplo)")
            patient.consent_file_key, patient.consent_file_size = patient_rules.save_consent_file(patient.id, io.BytesIO(pdf))
            patient.consent_file_name = f"termo-{code}.pdf"
        audit.record(db, None, actor, "create", "patient", code, patient.id,
                     audit.diff({}, patient_rules.snapshot(patient), patient_rules.FIELD_LABELS), at=registered_at)
        created.append(code)
    db.commit()
    print(f"Pacientes de exemplo: {len(created)} criados." if created else "Pacientes de exemplo: já existem.")


def seed_demo_stimuli(db: DbSession, actor: User | None) -> None:
    """Desenha os arquivos, envia como se fosse pela W10 e gera as versões para o óculos."""
    existing = set(db.scalars(select(Stimulus.name).where(Stimulus.status != "draft")))
    images = [item for item in seed_media.IMAGES if item.name not in existing]
    videos = [item for item in seed_media.VIDEOS if item.name not in existing]
    if not images and not videos:
        print("Estímulos de exemplo: já existem.")
        return
    saved = []
    sent_at = utcnow().replace(second=0, microsecond=0) - timedelta(days=DEMO_STIMULI_DAYS)
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        files = [(item, seed_media.write_image(item, folder)) for item in images]
        files += [(item, seed_media.write_video(item, folder)) for item in videos]
        for item, path in files:
            with open(path, "rb") as f:
                stimulus = stimulus_rules.create_draft(db, actor, f, path.name)
            stimulus.name, stimulus.status = item.name, "active"
            stimulus.description = getattr(item, "description", None)
            stimulus.set_tags(list(item.tags))
            stimulus.created_at = sent_at
            saved.append(stimulus)
    db.flush()
    stimulus_rules.audit_saved(db, None, actor, saved, at=sent_at)
    db.commit()
    stimulus_rules.process_device_versions([s.id for s in saved])
    print(f"Estímulos de exemplo: {stimulus_rules.batch_label(saved)}.")


def seed_demo_sessions(db: DbSession) -> None:
    """As sessões da W12, com a sequência, a visibilidade e os registros da auditoria.

    As Concluídas e as Interrompidas ganham dados coletados sintéticos (seed_demo_data); as Aguardando
    dados ficam sem eles, como se o óculos ainda enviasse.
    """
    if db.scalar(select(Session.id).limit(1)) is not None:
        print("Sessões de exemplo: já existem.")
        seed_demo_data(db)
        return
    users = {u.email: u for u in db.scalars(select(User))}
    patients = {p.code: p for p in db.scalars(select(Patient))}
    stimuli = {s.name: s for s in db.scalars(select(Stimulus).where(Stimulus.status == "active"))}
    admin = db.scalar(select(User).where(User.role == "admin", User.status == "active").order_by(User.created_at))
    now = utcnow().replace(second=0, microsecond=0)
    created = 0
    for days, title, code, owner_email, status, visibility, shared, sequence in DEMO_SESSIONS:
        owner, patient = users.get(owner_email), patients.get(code)
        items = [(stimuli.get(name), seconds) for name, seconds in DEMO_SEQUENCES[sequence]]
        if owner is None or patient is None or any(s is None for s, _ in items):
            continue
        session = Session(
            title=title, objective=DEMO_OBJECTIVES[sequence], status=status, visibility="private", record=True,
            patient=patient, owner=owner,
        )
        session.items = [
            SessionStimulus(position=i, stimulus=s, duration_seconds=seconds if s.kind == "image" else None)
            for i, (s, seconds) in enumerate(items, start=1)
        ]
        length = sum(seconds or (s.duration_seconds or 0) for s, seconds in items) + 20
        if status == "running":
            session.started_at = now - timedelta(minutes=3)
        elif status != "configured":
            session.started_at = now - timedelta(days=days, hours=1 + (days * 5) % 6)
            session.ended_at = session.started_at + timedelta(seconds=length)
            session.end_reason = "interrupted" if status == "interrupted" else "button_b"
        session.created_at = (session.started_at or now) - timedelta(days=1 if session.started_at else days)
        db.add(session)
        db.flush()
        audit.record(db, None, owner, "create", "session", session_rules.audit_label(session), session.id,
                     audit.diff({}, session_rules.snapshot(session), session_rules.FIELD_LABELS),
                     at=session.created_at)
        if visibility != "private":
            before = session_rules.visibility_snapshot(session)
            session.visibility = visibility
            session.shares = [SessionShare(user_id=users[email].id) for email in shared if email in users]
            db.flush()
            db.expire(session, ["shares"])
            audit.record(db, None, admin, "visibility_change", "session", session_rules.audit_label(session),
                         session.id, audit.diff(before, session_rules.visibility_snapshot(session),
                                                session_rules.VISIBILITY_FIELD_LABELS),
                         at=session.created_at + timedelta(minutes=10))
        # As Concluídas e as Interrompidas entram na auditoria com os dados (seed_tracking).
        if status in ("running", "awaiting_data"):
            execution.record_start(db, None, owner, session, seed_tracking.DEMO_DEVICE["name"], at=session.started_at)
        if status == "awaiting_data":
            execution.record_end(db, None, owner, session, agent=seed_tracking.DEMO_AGENT, at=session.ended_at)
        created += 1
    db.commit()
    print(f"Sessões de exemplo: {created} criadas.")
    seed_demo_data(db)


def seed_demo_data(db: DbSession) -> None:
    """Os dados coletados (app/seed_tracking.py) das sessões de exemplo Concluídas e Interrompidas que
    ainda não os têm, inclusive as de um banco semeado antes de existir a análise."""
    executed = {(title, code, owner): sequence for _, title, code, owner, status, _, _, sequence in DEMO_SESSIONS
                if status in ("completed", "interrupted")}
    pending = [
        (session, executed[key])
        for session in db.scalars(
            select(Session).where(Session.status.in_(("completed", "interrupted")), Session.data_received_at.is_(None))
            .order_by(Session.started_at)
        )
        if (key := (session.title, session.patient.code, session.owner.email)) in executed
    ]
    if not pending:
        return
    started = clock.monotonic()
    done = sum(seed_tracking.generate(db, session, sequence) for session, sequence in pending)
    print(f"Dados coletados de exemplo: {done} sessões ({clock.monotonic() - started:.0f} s).")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.seed", description=__doc__.split("\n\n")[0])
    parser.add_argument("--admin-email", help="e-mail do primeiro admin (recebe o convite)")
    parser.add_argument("--admin-name", default="Administrador", help="nome do primeiro admin")
    parser.add_argument("--demo", action="store_true", help="cria usuários, pacientes, estímulos e sessões de exemplo")
    parser.add_argument("--demo-password", default=DEMO_PASSWORD, help="senha dos usuários de exemplo")
    args = parser.parse_args(argv)

    problem = passwords.password_problem(args.demo_password)
    if args.demo and problem:
        parser.error(f"--demo-password: {problem}")

    migrate()
    with SessionLocal() as db:
        if permissions.ensure_defaults(db):
            print("Matriz de permissões semeada com o padrão.")
        db.commit()

        has_admin = db.scalar(select(User.id).where(User.role == "admin").limit(1)) is not None
        if args.admin_email:
            seed_admin(db, args.admin_email, args.admin_name)
        elif not has_admin and not args.demo:
            print("Ainda não há admin. Rode de novo com --admin-email e --admin-name (ou --demo).", file=sys.stderr)
            return 1
        if args.demo:
            seed_demo(db, args.demo_password)
            # Os exemplos ficam em nome de quem cadastra no dia a dia (Ana Souza, pesquisadora).
            actor = accounts.find_by_email(db, "ana.souza@exemplo.com") or db.scalar(
                select(User).where(User.role == "admin").order_by(User.created_at))
            seed_demo_patients(db, actor)
            seed_demo_stimuli(db, actor)
            seed_demo_sessions(db)
        db.commit()
    print(f"Pronto ({utcnow():%d/%m/%Y %H:%M} UTC).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
