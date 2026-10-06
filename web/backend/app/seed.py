"""Prepara o banco para o primeiro uso: aplica as migrações, semeia a matriz de permissões e cria
o primeiro admin, mostrando o link do convite.

    python -m app.seed --admin-email ana@lab.br --admin-name "Ana Souza"
    python -m app.seed --demo        # também cria usuários, pacientes e estímulos de exemplo

Pode rodar de novo sem estragar nada: o que já existe fica como está. Rodar com o e-mail de um
admin que ainda não aceitou o convite gera um link novo (o anterior deixa de valer).
"""
import argparse
import io
import sys
import tempfile
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from . import seed_media
from .db import SessionLocal, migrate
from .models import Patient, Stimulus, User, utcnow
from .services import accounts, audit, passwords, permissions, tokens
from .services import patients as patient_rules
from .services import stimuli as stimulus_rules

DEMO_PASSWORD = "NeuroSight#2026"

# Usuários da W19. O primeiro é o admin da demonstração.
DEMO_USERS = [
    ("Carlos Lima", "carlos.lima@exemplo.com", "admin", "active"),
    ("Ana Souza", "ana.souza@exemplo.com", "researcher", "active"),
    ("Igor Mendes", "igor.mendes@exemplo.com", "researcher", "invited"),
    ("Bruno Castro", "bruno.castro@exemplo.com", "researcher", "active"),
    ("Gustavo Prado", "gustavo.prado@exemplo.com", "admin", "active"),
    ("Daniela Rocha", "daniela.rocha@exemplo.com", "researcher", "active"),
    ("Eduardo Martins", "eduardo.martins@exemplo.com", "researcher", "active"),
    ("Fernanda Lopes", "fernanda.lopes@exemplo.com", "researcher", "inactive"),
]


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


def _create(db: DbSession, name: str, email: str, role: str, status: str, password: str | None,
            created_by: User | None) -> User:
    user = User(
        name=name, email=email.strip().lower(), role=role, status=status,
        password_hash=passwords.hash_password(password) if password else None,
        created_by_id=created_by.id if created_by else None,
    )
    db.add(user)
    db.flush()
    audit.record(db, None, created_by, "create", "user", user.name, user.id,
                 audit.diff({}, accounts.snapshot(user), accounts.USER_FIELD_LABELS))
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
    for name, email, role, status in DEMO_USERS:
        if accounts.find_by_email(db, email):
            print(f"  {email}: já existe")
            continue
        user = _create(db, name, email, role, status, None if status == "invited" else password, admin)
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
        patient = Patient(
            code=code, name=name, birth_date=date.fromisoformat(birth), sex=sex, vision_correction=vision,
            consent_signed=signed_on is not None, consent_date=date.fromisoformat(signed_on) if signed_on else None,
            notes=notes, status="active", created_by_id=actor.id if actor else None,
        )
        db.add(patient)
        db.flush()
        if signed_on:
            pdf = seed_media.minimal_pdf(f"Termo de consentimento - {code} (exemplo)")
            patient.consent_file_key, patient.consent_file_size = patient_rules.save_consent_file(patient.id, io.BytesIO(pdf))
            patient.consent_file_name = f"termo-{code}.pdf"
        audit.record(db, None, actor, "create", "patient", code, patient.id,
                     audit.diff({}, patient_rules.snapshot(patient), patient_rules.FIELD_LABELS))
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
            saved.append(stimulus)
    db.flush()
    stimulus_rules.audit_saved(db, None, actor, saved)
    db.commit()
    stimulus_rules.process_device_versions([s.id for s in saved])
    print(f"Estímulos de exemplo: {stimulus_rules.batch_label(saved)}.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.seed", description=__doc__.split("\n\n")[0])
    parser.add_argument("--admin-email", help="e-mail do primeiro admin (recebe o convite)")
    parser.add_argument("--admin-name", default="Administrador", help="nome do primeiro admin")
    parser.add_argument("--demo", action="store_true", help="cria usuários, pacientes e estímulos de exemplo")
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
        db.commit()
    print(f"Pronto ({utcnow():%d/%m/%Y %H:%M} UTC).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
