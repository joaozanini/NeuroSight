"""Prepara o banco para o primeiro uso: aplica as migrações, semeia a matriz de permissões e cria
o primeiro admin, mostrando o link do convite.

    python -m app.seed --admin-email ana@lab.br --admin-name "Ana Souza"
    python -m app.seed --demo        # também cria os usuários de exemplo dos protótipos

Pode rodar de novo sem estragar nada: o que já existe fica como está. Rodar com o e-mail de um
admin que ainda não aceitou o convite gera um link novo (o anterior deixa de valer).
"""
import argparse
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from .db import SessionLocal, migrate
from .models import User, utcnow
from .services import accounts, audit, passwords, permissions, tokens

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.seed", description=__doc__.split("\n\n")[0])
    parser.add_argument("--admin-email", help="e-mail do primeiro admin (recebe o convite)")
    parser.add_argument("--admin-name", default="Administrador", help="nome do primeiro admin")
    parser.add_argument("--demo", action="store_true", help="cria os usuários de exemplo dos protótipos")
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
        db.commit()
    print(f"Pronto ({utcnow():%d/%m/%Y %H:%M} UTC).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
