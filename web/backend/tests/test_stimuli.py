"""Estímulos (W09–W11): envio como rascunho, "Salvar na biblioteca" com um registro só da auditoria,
versão para o óculos em segundo plano, filtros, edição, arquivamento e exclusão."""
import os
from datetime import timedelta

import cv2
import numpy as np

from app.db import SessionLocal
from app.models import Stimulus, utcnow
from app.services import stimuli as stimuli_service
from app.services.storage import storage

from .accounts import API, admin, audit_entries, login, make_user, researcher
from .media_files import jpeg, png, video


def upload(client, name, content, mime="application/octet-stream"):
    return client.post(f"{API}/stimuli/uploads", files={"file": (name, content, mime)})


def save(client, *items):
    return client.post(f"{API}/stimuli", json={"items": list(items)})


def add(client, name, content, label=None, tags=(), description=None):
    """Envia e já salva na biblioteca; devolve o id."""
    draft = upload(client, name, content).json()
    r = save(client, {"id": draft["id"], "name": label or draft["suggested_name"], "tags": list(tags),
                      "description": description})
    assert r.status_code == 201, r.text
    return draft["id"]


def stored(stimulus_id) -> Stimulus:
    with SessionLocal() as db:
        return db.get(Stimulus, stimulus_id)


def test_upload_creates_a_draft_with_metadata_and_thumbnail(client):
    researcher(client)
    r = upload(client, "cachoeira-na-mata.jpg", jpeg(64, 40), "image/jpeg")
    assert r.status_code == 201, r.text
    draft = r.json()
    assert draft["suggested_name"] == "Cachoeira na mata"
    assert (draft["kind"], draft["format"], draft["width"], draft["height"]) == ("image", "jpg", 64, 40)
    assert draft["size_bytes"] == len(jpeg(64, 40))
    assert draft["duration_seconds"] is None

    thumb = client.get(draft["thumbnail_url"])
    assert thumb.status_code == 200 and thumb.headers["content-type"] == "image/jpeg"
    assert "immutable" in thumb.headers["cache-control"]

    r = upload(client, "trilha-no-bosque.mp4", video(seconds=2.0), "video/mp4")
    assert r.status_code == 201, r.text
    clip = r.json()
    assert (clip["kind"], clip["format"], clip["width"], clip["height"]) == ("video", "mp4", 320, 200)
    assert abs(clip["duration_seconds"] - 2.0) < 0.1

    # Rascunhos não aparecem na biblioteca.
    assert client.get(f"{API}/stimuli").json()["total"] == 0


def test_wrong_formats_are_refused(client):
    researcher(client)
    cases = [
        ("video-bruto.mov", video(container="mov"), 415, "formato não aceito. Envie o vídeo em MP4"),
        ("renomeado.mp4", video(container="mov"), 415, "formato não aceito. Envie o vídeo em MP4"),
        ("animacao.gif", b"GIF89a" + b"\0" * 64, 415, "formato não aceito. Envie a imagem em JPG ou PNG"),
        ("falsa.jpg", b"isto nao e uma imagem", 415, "formato não aceito. Envie a imagem em JPG ou PNG"),
        ("dados.csv", b"a;b\n1;2\n", 415, "formato não aceito. Envie imagens em JPG ou PNG e vídeos em MP4"),
        ("cortado.mp4", video()[:200], 400, "não foi possível ler o vídeo. Confira se o arquivo é um MP4 válido"),
    ]
    for name, content, status, detail in cases:
        r = upload(client, name, content)
        assert (r.status_code, r.json()["detail"]) == (status, detail), name
    # Nada ficou no disco.
    folder = os.path.join(storage.root, "stimuli")
    assert not os.path.isdir(folder) or os.listdir(folder) == []


def test_png_named_jpg_is_accepted_by_its_content(client):
    researcher(client)
    draft = upload(client, "foto.jpg", png(32, 32)).json()
    assert draft["format"] == "png"


def test_save_to_library_audits_once_and_builds_device_versions(client):
    uid = researcher(client)
    big = upload(client, "montanhas.jpg", jpeg(3000, 1600)).json()
    face = upload(client, "rosto.png", png(64, 40)).json()
    clip = upload(client, "ondas.mp4", video(codec="mpeg4")).json()
    r = save(
        client,
        {"id": big["id"], "name": "Montanhas ao amanhecer", "description": "Cordilheira.", "tags": ["Paisagem", "natureza"]},
        {"id": face["id"], "name": "Rosto neutro 01", "tags": ["rosto"]},
        {"id": clip["id"], "name": "Ondas na praia", "tags": ["paisagem", "mar"]},
    )
    assert r.status_code == 201, r.text
    assert [c["name"] for c in r.json()] == ["Montanhas ao amanhecer", "Rosto neutro 01", "Ondas na praia"]

    [entry] = audit_entries(entity_type="stimulus")
    assert entry.action == "create" and entry.user_id == uid
    assert entry.entity_label == "2 imagens e 1 vídeo enviados à biblioteca"
    assert entry.entity_id is None
    assert [(c["label"], c["after"]) for c in entry.changes] == [
        ("Montanhas ao amanhecer", "Imagem, montanhas.jpg, etiquetas: paisagem, natureza"),
        ("Rosto neutro 01", "Imagem, rosto.png, etiquetas: rosto"),
        ("Ondas na praia", "Vídeo, ondas.mp4, etiquetas: paisagem, mar"),
    ]

    # O TestClient só responde depois das tarefas em segundo plano: as versões já estão prontas.
    s = stored(big["id"])
    assert (s.status, s.device_status, s.device_width, s.device_height) == ("active", "ready", 2048, 1092)
    assert os.path.isfile(storage.stimulus_device(s.id, "jpg"))
    v = stored(clip["id"])
    assert v.device_status == "ready" and v.device_format == "mp4" and len(v.device_sha256) == 64

    detail = client.get(f"{API}/stimuli/{big['id']}").json()
    assert detail["tags"] == ["paisagem", "natureza"]
    assert detail["description"] == "Cordilheira."
    assert detail["created_by_name"] == "Ana Souza"
    assert detail["device_status"] == "ready"
    assert detail["sessions_count"] == 0 and detail["can_delete"] is True
    original = client.get(detail["file_url"])
    assert original.content == jpeg(3000, 1600) and original.headers["content-type"] == "image/jpeg"


def test_single_save_links_the_audit_to_the_stimulus(client):
    researcher(client)
    sid = add(client, "rosto.jpg", jpeg(), label="Rosto alegre 02")
    [entry] = audit_entries(entity_type="stimulus")
    assert (entry.entity_label, entry.entity_id) == ("Rosto alegre 02", sid)


def test_drafts_belong_to_who_uploaded(client):
    researcher(client)
    draft = upload(client, "rosto.jpg", jpeg()).json()
    make_user("Bruno Castro", "bruno.castro@exemplo.com", "researcher")
    login(client, "bruno.castro@exemplo.com")
    assert client.get(f"{API}/stimuli/{draft['id']}").status_code == 404
    assert client.get(draft["thumbnail_url"]).status_code == 404
    assert save(client, {"id": draft["id"], "name": "Meu"}).status_code == 409
    assert client.delete(f"{API}/stimuli/uploads/{draft['id']}").status_code == 404


def test_discard_and_purge_drafts(client):
    researcher(client)
    draft = upload(client, "rosto.jpg", jpeg()).json()
    assert client.delete(f"{API}/stimuli/uploads/{draft['id']}").status_code == 204
    assert stored(draft["id"]) is None
    assert not os.path.exists(storage.stimulus_dir(draft["id"]))

    old = upload(client, "antigo.jpg", jpeg()).json()
    with SessionLocal() as db:
        db.get(Stimulus, old["id"]).created_at = utcnow() - timedelta(hours=30)
        db.commit()
        assert stimuli_service.purge_stale_drafts(db) == 1
    assert stored(old["id"]) is None and not os.path.exists(storage.stimulus_dir(old["id"]))


def test_filters_counts_and_tags(client):
    researcher(client)
    add(client, "montanhas.jpg", jpeg(), "Montanhas ao amanhecer", ["paisagem", "natureza"])
    add(client, "rosto.png", png(), "Rosto neutro 01", ["rosto", "neutro"])
    add(client, "ondas.mp4", video(), "Ondas na praia", ["paisagem", "mar"])

    page = client.get(f"{API}/stimuli").json()
    assert page["counts"] == {"total": 3, "images": 2, "videos": 1}
    assert [s["name"] for s in page["items"]] == ["Ondas na praia", "Rosto neutro 01", "Montanhas ao amanhecer"]
    clip = page["items"][0]
    assert clip["kind"] == "video" and abs(clip["duration_seconds"] - 2.0) < 0.1
    assert clip["tags"] == ["paisagem", "mar"]

    def names(**params):
        return [s["name"] for s in client.get(f"{API}/stimuli", params=params).json()["items"]]

    assert names(kind="image") == ["Rosto neutro 01", "Montanhas ao amanhecer"]
    assert names(kind="video") == ["Ondas na praia"]
    assert names(tag="Paisagem") == ["Ondas na praia", "Montanhas ao amanhecer"]
    assert names(tag="paisagem", kind="image") == ["Montanhas ao amanhecer"]
    assert names(q="rosto") == ["Rosto neutro 01"]
    assert names(q="natur") == ["Montanhas ao amanhecer"]  # pela etiqueta
    assert names(q="%") == []
    assert client.get(f"{API}/stimuli/tags").json() == ["mar", "natureza", "neutro", "paisagem", "rosto"]


def test_edit_name_description_and_tags(client):
    researcher(client)
    sid = add(client, "montanhas.jpg", jpeg(), "Montanhas", ["paisagem"])
    r = client.patch(f"{API}/stimuli/{sid}", json={
        "name": "Montanhas ao amanhecer", "description": "Cordilheira com o sol nascendo.", "tags": ["paisagem", "natureza"],
    })
    assert r.status_code == 200, r.text
    assert r.json()["tags"] == ["paisagem", "natureza"]
    [entry] = audit_entries(action="update", entity_type="stimulus")
    assert entry.entity_label == "Montanhas ao amanhecer"
    assert {c["field"]: (c["before"], c["after"]) for c in entry.changes} == {
        "name": ("Montanhas", "Montanhas ao amanhecer"),
        "description": (None, "Cordilheira com o sol nascendo."),
        "tags": ("paisagem", "paisagem, natureza"),
    }
    # Só o que veio muda; sem mudança, sem registro.
    r = client.patch(f"{API}/stimuli/{sid}", json={"tags": ["paisagem", "natureza"]})
    assert r.json()["description"] == "Cordilheira com o sol nascendo."
    assert len(audit_entries(action="update", entity_type="stimulus")) == 1
    assert client.patch(f"{API}/stimuli/{sid}", json={"name": "  "}).status_code == 422
    assert client.patch(f"{API}/stimuli/{sid}", json={"tags": [f"t{i}" for i in range(21)]}).status_code == 422


def test_archive_and_delete_need_the_archive_permission(client):
    researcher(client)
    sid = add(client, "rosto.jpg", jpeg(), "Rosto neutro 01")
    assert client.put(f"{API}/stimuli/{sid}/status", json={"status": "archived"}).status_code == 403
    assert client.delete(f"{API}/stimuli/{sid}").status_code == 403


def test_archive_hides_from_the_library(client):
    admin(client)
    sid = add(client, "rosto.jpg", jpeg(), "Rosto neutro 01", ["rosto"])
    keep = add(client, "lago.jpg", jpeg(), "Lago e floresta", ["paisagem"])
    r = client.put(f"{API}/stimuli/{sid}/status", json={"status": "archived"})
    assert r.status_code == 200 and r.json()["status"] == "archived"

    page = client.get(f"{API}/stimuli").json()
    assert [s["id"] for s in page["items"]] == [keep]
    assert page["counts"]["total"] == 1
    assert client.get(f"{API}/stimuli/tags").json() == ["paisagem"]
    page = client.get(f"{API}/stimuli", params={"include_archived": True}).json()
    assert [(s["id"], s["status"]) for s in page["items"]] == [(keep, "active"), (sid, "archived")]
    assert client.get(f"{API}/stimuli/tags", params={"include_archived": True}).json() == ["paisagem", "rosto"]

    client.put(f"{API}/stimuli/{sid}/status", json={"status": "active"})
    entries = audit_entries(action="update", entity_type="stimulus")
    assert [(e.changes[0]["before"], e.changes[0]["after"]) for e in entries] == [
        ("Na biblioteca", "Arquivado"), ("Arquivado", "Na biblioteca"),
    ]


def test_delete_removes_files_and_is_audited(client):
    admin(client)
    sid = add(client, "rosto.jpg", jpeg(), "Rosto neutro 01", ["rosto"])
    assert client.delete(f"{API}/stimuli/{sid}").status_code == 204
    assert stored(sid) is None
    assert not os.path.exists(storage.stimulus_dir(sid))
    assert client.get(f"{API}/stimuli/{sid}").status_code == 404
    [entry] = audit_entries(action="delete")
    assert (entry.entity_type, entry.entity_label, entry.entity_id) == ("stimulus", "Rosto neutro 01", sid)
    assert {c["field"]: c["before"] for c in entry.changes}["file"] == "rosto.jpg"


def test_upload_needs_permission_and_respects_the_size_limit(client, monkeypatch):
    researcher(client)
    from app.config import settings

    monkeypatch.setattr(settings, "max_stimulus_mb", 0)
    r = upload(client, "rosto.jpg", jpeg())
    assert r.status_code == 413
    assert r.json()["detail"] == "o arquivo passa do limite de 0 MB"
    monkeypatch.undo()

    with SessionLocal() as db:
        from app.models import RolePermission

        db.query(RolePermission).filter_by(role="researcher", permission="stimuli.edit").delete()
        db.commit()
    assert upload(client, "rosto.jpg", jpeg()).status_code == 403
    assert client.get(f"{API}/stimuli").status_code == 200  # ver a biblioteca exige só o login


def test_exif_rotation_is_applied_to_dimensions(client):
    """Um JPEG de celular deitado (orientação 6 no EXIF) aparece em pé: 40 × 64."""
    researcher(client)
    ok, buf = cv2.imencode(".jpg", np.full((40, 64, 3), 100, np.uint8))
    data = buf.tobytes()
    exif = (b"Exif\x00\x00" + b"MM\x00\x2a\x00\x00\x00\x08" + b"\x00\x01"
            + b"\x01\x12\x00\x03\x00\x00\x00\x01\x00\x06\x00\x00" + b"\x00\x00\x00\x00")
    app1 = b"\xff\xe1" + (len(exif) + 2).to_bytes(2, "big") + exif
    rotated = data[:2] + app1 + data[2:]
    draft = upload(client, "celular.jpg", rotated).json()
    assert (draft["width"], draft["height"]) == (40, 64)


def test_purge_is_safe_when_two_workers_clean_at_once(client):
    researcher(client)
    stale = upload(client, "antigo.jpg", jpeg()).json()
    fresh = upload(client, "novo.jpg", jpeg()).json()
    saved = add(client, "salvo.jpg", jpeg(), "Salvo")
    with SessionLocal() as db:
        for sid in (stale["id"], saved):
            db.get(Stimulus, sid).created_at = utcnow() - timedelta(hours=30)
        db.commit()
    with SessionLocal() as first, SessionLocal() as second:
        assert stimuli_service.purge_stale_drafts(first) == 1
        assert stimuli_service.purge_stale_drafts(second) == 0
    assert stored(stale["id"]) is None and not os.path.exists(storage.stimulus_dir(stale["id"]))
    # O rascunho recente e o estímulo antigo já salvo ficam.
    assert stored(fresh["id"]).status == "draft" and os.path.isdir(storage.stimulus_dir(fresh["id"]))
    assert stored(saved).status == "active" and os.path.isdir(storage.stimulus_dir(saved))


def test_resume_pending_builds_what_was_left_behind(client, monkeypatch):
    researcher(client)
    sid = add(client, "rosto.jpg", jpeg(), "Rosto neutro 01")
    with SessionLocal() as db:
        s = db.get(Stimulus, sid)
        s.device_status, s.device_sha256 = "processing", None  # a API caiu no meio
        db.commit()
    os.remove(storage.stimulus_device(sid, "jpg"))

    thread = stimuli_service.resume_pending()
    thread.join(timeout=30)
    s = stored(sid)
    assert s.device_status == "ready" and len(s.device_sha256) == 64
    assert os.path.isfile(storage.stimulus_device(sid, "jpg"))
    assert stimuli_service.resume_pending() is None  # nada mais pendente

    def broken(db):
        raise RuntimeError("banco fora do ar")

    monkeypatch.setattr(stimuli_service, "purge_stale_drafts", broken)
    assert stimuli_service.resume_pending() is None  # não impede a API de subir
