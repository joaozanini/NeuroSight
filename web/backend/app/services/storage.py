"""Armazenamento de mídia em disco, atrás de uma interface simples.

Tudo passa por aqui para que dê para trocar por S3/MinIO depois sem mexer nas rotas:
basta outra implementação com os mesmos métodos (e um url_for que devolva URL pré-assinada).
Layout:
  <media_root>/<session_id>/frames/000001.jpg  +  <media_root>/<session_id>/video.mp4  (fluxo antigo)
  <media_root>/stimuli/<id>/original.<ext>, thumb.jpg e device.<ext>
  <media_root>/patients/<id>/<chave>.pdf  (TCLE)
"""
import os
import shutil

from ..config import settings


class LocalDiskStorage:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)

    def session_dir(self, sid: str) -> str:
        return os.path.join(self.root, sid)

    def frames_dir(self, sid: str) -> str:
        return os.path.join(self.session_dir(sid), "frames")

    def ensure_frames_dir(self, sid: str) -> str:
        d = self.frames_dir(sid)
        os.makedirs(d, exist_ok=True)
        return d

    def frame_path(self, sid: str, name: str) -> str:
        return os.path.join(self.frames_dir(sid), name)

    def video_path(self, sid: str) -> str:
        return os.path.join(self.session_dir(sid), "video.mp4")

    def count_frames(self, sid: str) -> int:
        d = self.frames_dir(sid)
        if not os.path.isdir(d):
            return 0
        return sum(1 for n in os.listdir(d) if n.lower().endswith(".jpg"))

    def delete_session(self, sid: str) -> None:
        d = self.session_dir(sid)
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)

    # ---- Estímulos ----

    def stimulus_dir(self, stimulus_id: str) -> str:
        return os.path.join(self.root, "stimuli", stimulus_id)

    def stimulus_original(self, stimulus_id: str, fmt: str) -> str:
        return os.path.join(self.stimulus_dir(stimulus_id), f"original.{fmt}")

    def stimulus_thumbnail(self, stimulus_id: str) -> str:
        return os.path.join(self.stimulus_dir(stimulus_id), "thumb.jpg")

    def stimulus_device(self, stimulus_id: str, fmt: str) -> str:
        return os.path.join(self.stimulus_dir(stimulus_id), f"device.{fmt}")

    def delete_stimulus(self, stimulus_id: str) -> None:
        shutil.rmtree(self.stimulus_dir(stimulus_id), ignore_errors=True)

    # ---- Pacientes ----

    def patient_dir(self, patient_id: str) -> str:
        return os.path.join(self.root, "patients", patient_id)

    def path_of(self, key: str) -> str:
        """Caminho absoluto de uma chave relativa à pasta de mídia (ex.: patients/<id>/<x>.pdf)."""
        return os.path.join(self.root, key)

    def key_of(self, path: str) -> str:
        return os.path.relpath(path, self.root).replace(os.sep, "/")

    def delete_file(self, key: str | None) -> None:
        if key:
            try:
                os.remove(self.path_of(key))
            except FileNotFoundError:
                pass


storage = LocalDiskStorage(settings.media_root)
