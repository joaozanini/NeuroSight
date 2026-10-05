"""Senhas: hash argon2 e as regras da W03/W05.

As regras repetem `web/frontend/src/lib/password.ts`, que as marca ao vivo no formulário; as duas
listas precisam mudar juntas. "Maiúscula", "número" e "símbolo" seguem as classes Unicode do
JavaScript (\\p{Lu}, \\p{Ll}, \\p{Nd}, e o que não é letra, número nem espaço).
"""
import unicodedata

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()

MIN_LENGTH = 8
# Limite só para não aceitar um corpo enorme no hash; nenhuma senha real chega perto.
MAX_LENGTH = 256

RULE_LABELS = {
    "length": "Pelo menos 8 caracteres",
    "case": "Letras maiúsculas e minúsculas",
    "number": "Pelo menos um número",
    "symbol": "Pelo menos um símbolo, como ! ou #",
}


def check_rules(password: str) -> dict[str, bool]:
    categories = [unicodedata.category(c) for c in password]
    return {
        "length": len(password) >= MIN_LENGTH,
        "case": "Lu" in categories and "Ll" in categories,
        "number": "Nd" in categories,
        "symbol": any(
            not cat.startswith(("L", "N")) and not c.isspace() for c, cat in zip(password, categories)
        ),
    }


def password_problem(password: str) -> str | None:
    """Mensagem para a pessoa se a senha não serve, ou None."""
    if len(password) > MAX_LENGTH:
        return f"A senha pode ter no máximo {MAX_LENGTH} caracteres."
    missing = [RULE_LABELS[rule] for rule, ok in check_rules(password).items() if not ok]
    if missing:
        return "A senha precisa ter: " + "; ".join(m[0].lower() + m[1:] for m in missing) + "."
    return None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    if not password_hash:
        # Mesmo custo de uma verificação real, para o tempo de resposta não revelar a conta.
        _burn(password)
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


_DUMMY_HASH = _hasher.hash("senha-que-ninguem-usa")


def _burn(password: str) -> None:
    try:
        _hasher.verify(_DUMMY_HASH, password)
    except (VerificationError, InvalidHashError):
        pass
