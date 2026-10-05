"""Site estático: o fallback do SPA não pode servir nada fora da pasta do build."""
import os

import pytest

from app.main import resolve_static_file

from .conftest import SECRET_FILE, STATIC_DIR

INDEX = "<!doctype html><title>NeuroSight</title>"


def test_health(client):
    assert client.get("/healthz").json() == {"ok": True}


@pytest.mark.parametrize("url", [
    "http://testserver//etc/passwd",
    "http://testserver//etc/hostname",
    "/..%2f..%2f..%2fetc/passwd",
    "/%2e%2e/%2e%2e/%2e%2e/etc/passwd",
    "/assets/..%2f..%2f..%2f..%2fetc/passwd",
])
def test_absolute_and_dotdot_paths_do_not_leak_system_files(client, url):
    r = client.get(url)
    assert "root:" not in r.text
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert r.text == INDEX


@pytest.mark.parametrize("url", [
    "/..%2fsegredo.txt",
    "/%2e%2e/segredo.txt",
    f"http://testserver/{SECRET_FILE}",
])
def test_files_next_to_static_dir_are_not_served(client, url):
    r = client.get(url)
    assert "conteudo secreto" not in r.text


def test_serves_files_inside_static_dir(client):
    assert client.get("/favicon.svg").status_code == 200
    r = client.get("/assets/app.js")
    assert r.status_code == 200
    assert "console.log" in r.text


def test_spa_routes_return_index(client):
    for path in ("/", "/pacientes", "/sessoes/abc123/analise", "/admin/usuarios"):
        r = client.get(path)
        assert r.status_code == 200
        assert r.text == INDEX


def test_unknown_api_route_is_json_404(client):
    r = client.get("/api/v1/nao-existe")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")
    assert r.json() == {"detail": "rota não encontrada"}


@pytest.mark.parametrize("requested", [
    "/etc/passwd",
    "//etc/passwd",
    "../segredo.txt",
    "assets/../../segredo.txt",
    "nao-existe.js",
    "assets",
])
def test_resolve_static_file_rejects(requested):
    assert resolve_static_file(str(STATIC_DIR), requested) is None


def test_resolve_static_file_accepts_files_inside():
    found = resolve_static_file(str(STATIC_DIR), "assets/app.js")
    assert found == os.path.realpath(STATIC_DIR / "assets" / "app.js")


def test_resolve_static_file_rejects_symlink_escaping_root(tmp_path):
    root = tmp_path / "site"
    root.mkdir()
    (tmp_path / "fora.txt").write_text("x", encoding="utf-8")
    (root / "atalho.txt").symlink_to(tmp_path / "fora.txt")
    assert resolve_static_file(str(root), "atalho.txt") is None
