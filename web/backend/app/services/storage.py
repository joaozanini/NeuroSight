"""Armazenamento de mídia em disco, atrás de uma interface simples.

Tudo passa por aqui para que dê para trocar por S3/MinIO depois sem mexer nas rotas:
basta outra implementação com os mesmos métodos (e um url_for que devolva URL pré-assinada).
Layout: <media_root>/<session_id>/frames/000001.jpg  +  <media_root>/<session_id>/video.mp4
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


storage = LocalDiskStorage(settings.media_root)
