"""Regras de senha iguais às do front (src/lib/password.test.ts) e o hash argon2."""
import pytest

from app.services.passwords import check_rules, hash_password, password_problem, verify_password


def test_each_rule_is_checked_separately():
    assert check_rules("") == {"length": False, "case": False, "number": False, "symbol": False}
    assert check_rules("Senha123") == {"length": True, "case": True, "number": True, "symbol": False}
    assert check_rules("senha!") == {"length": False, "case": False, "number": False, "symbol": True}


def test_accented_letters_count_as_upper_and_lower_case():
    assert check_rules("ÁGUAágua")["case"] is True


@pytest.mark.parametrize("password, strong", [("Senha123", False), ("Senha123!", True), ("Sa1!", False),
                                              ("Senha 123", False), ("ÁGUAágua1#", True)])
def test_only_strong_with_all_four_rules(password, strong):
    assert (password_problem(password) is None) is strong


def test_problem_lists_what_is_missing():
    assert password_problem("senha") == (
        "A senha precisa ter: pelo menos 8 caracteres; letras maiúsculas e minúsculas; pelo menos um número; "
        "pelo menos um símbolo, como ! ou #."
    )


def test_hash_and_verify():
    h = hash_password("Senha123!")
    assert h.startswith("$argon2")
    assert verify_password(h, "Senha123!")
    assert not verify_password(h, "senha123!")
    assert not verify_password(None, "Senha123!")
    assert not verify_password("lixo", "Senha123!")
