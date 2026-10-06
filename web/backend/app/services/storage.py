"""Armazenamento de mídia em disco, atrás de uma interface simples.

Tudo passa por aqui para que dê para trocar por S3/MinIO depois sem mexer nas rotas:
basta outra implementação com os mesmos métodos (e um url_for que devolva URL pré-assinada).
Layout:
  <media_root>/<id>/frames/*.jpg e video.mp4 (fluxo antigo, só leitura: o caminho do vídeo fica na linha)
  <media_root>/stimuli/<id>/original.<ext>, thumb.jpg e device.<ext>
  <media_root>/patients/<id>/<chave>.pdf  (TCLE)
  <media_root>/sessions/<id>/tracking.json e frames/*.jpg (o que o óculos envia depois do B) e
      recording.mp4 (montado dos frames na ingestão)
"""
import os
import shutil

from ..config import settings


class LocalDiskStorage:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)

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

    # ---- Sessões ----

    def session_dir(self, session_id: str) -> str:
        return os.path.join(self.root, "sessions", session_id)

    def session_tracking(self, session_id: str) -> str:
        return os.path.join(self.session_dir(session_id), "tracking.json")

    def session_frames_dir(self, session_id: str) -> str:
        return os.path.join(self.session_dir(session_id), "frames")

    def session_recording(self, session_id: str) -> str:
        return os.path.join(self.session_dir(session_id), "recording.mp4")

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
