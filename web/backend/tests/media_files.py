"""Arquivos de teste gerados na hora: imagens pelo OpenCV, vídeos pelo ffmpeg do imageio-ffmpeg
(fontes `lavfi`, sem depender de nada no disco) e o PDF mínimo do seed."""
import functools
import os
import subprocess
from pathlib import Path

import cv2
import numpy as np

from app.seed_media import minimal_pdf
from app.services.media import ffmpeg_exe

# Dentro da pasta temporária dos testes (o conftest apaga no fim), ao lado da pasta de mídia.
TMP = Path(os.environ["QUESTPRO_MEDIA_ROOT"]).parent / "arquivos"
TMP.mkdir(exist_ok=True)


def jpeg(width=64, height=40, shade=120) -> bytes:
    img = np.full((height, width, 3), shade, dtype=np.uint8)
    cv2.rectangle(img, (0, 0), (width // 2, height // 2), (40, 90, 200), -1)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return buf.tobytes()


def png(width=64, height=40, alpha=False) -> bytes:
    channels = 4 if alpha else 3
    img = np.full((height, width, channels), 200, dtype=np.uint8)
    if alpha:
        img[:, : width // 2, 3] = 0
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return buf.tobytes()


@functools.cache
def video(seconds=2.0, size="320x200", codec="libx264", pix_fmt="yuv420p", container="mp4", audio=True) -> bytes:
    """MP4 (ou MOV) sintético. `codec="mpeg4"` gera um vídeo que precisa ser convertido para o óculos."""
    out = TMP / f"v-{seconds}-{size}-{codec}-{pix_fmt}-{audio}.{container}"
    args = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"testsrc2=s={size}:d={seconds}:r=24"]
    if audio:
        args += ["-f", "lavfi", "-i", f"sine=d={seconds}", "-c:a", "aac", "-shortest"]
    args += ["-c:v", codec, "-pix_fmt", pix_fmt, "-f", container, str(out)]
    subprocess.run(args, check=True, capture_output=True)
    return out.read_bytes()


def pdf(text="Termo de consentimento") -> bytes:
    return minimal_pdf(text)


def top_level_boxes(data: bytes) -> list[str]:
    """Nomes dos boxes de primeiro nível de um MP4 (para conferir o faststart: moov antes do mdat)."""
    names, pos = [], 0
    while pos + 8 <= len(data):
        size = int.from_bytes(data[pos:pos + 4], "big")
        names.append(data[pos + 4:pos + 8].decode("latin-1"))
        if size == 1:
            size = int.from_bytes(data[pos + 8:pos + 16], "big")
        if size < 8:
            break
        pos += size
    return names
