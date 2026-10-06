"""Montagem do MP4 da gravação a partir dos frames JPEG que o óculos envia (services/ingestion.py).

Preferimos **H.264 (libx264, yuv420p)** via imageio-ffmpeg — que traz um binário de ffmpeg
embutido no wheel (pip-only, sem instalar nada no sistema) — porque é o que o `<video>` do
navegador toca de forma confiável, com o índice no começo (faststart) para tocar enquanto baixa.
Se o ffmpeg embutido não estiver disponível, caímos para o `VideoWriter` do OpenCV com `mp4v`
(que pode não tocar no Chrome; o codec usado fica no resultado). fps constante = meta.capture.fps,
frames em ordem de idx. Frame ausente ou ilegível fica de fora, e a lista dos que entraram volta
para quem chamou: o site acha o instante de cada frame do vídeo por ela.
"""
import logging
import os

import cv2

logger = logging.getLogger(__name__)


def _even(n: int) -> int:
    """yuv420p exige dimensões pares."""
    n = int(n)
    return n - (n % 2)


def _read_frames(frames_dir, ordered, width, height, written):
    """Gera frames BGR já no tamanho certo, pulando os ilegíveis; anota em `written` os que saíram."""
    for fr in ordered:
        name = os.path.basename(fr.get("file", ""))
        if not name:
            continue
        img = cv2.imread(os.path.join(frames_dir, name))
        if img is None:
            continue  # frame ausente/ilegível — pula e segue
        if img.shape[1] != width or img.shape[0] != height:
            img = cv2.resize(img, (width, height))
        written.append(fr)
        yield img


def _assemble_h264(frames_dir, ordered, width, height, fps, out_path) -> list:
    """H.264 via imageio-ffmpeg. Lança se o ffmpeg embutido não existir."""
    import imageio.v2 as imageio  # ImportError se imageio/imageio-ffmpeg não instalados

    writer = imageio.get_writer(
        out_path, format="FFMPEG", mode="I", fps=float(fps),
        codec="libx264", pixelformat="yuv420p",
        macro_block_size=None,  # não force resize p/ múltiplos de 16
        ffmpeg_log_level="error",
        output_params=["-movflags", "+faststart"],
    )
    written: list = []
    try:
        for img in _read_frames(frames_dir, ordered, width, height, written):
            writer.append_data(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))  # imageio espera RGB
    finally:
        writer.close()
    return written


def _assemble_mp4v(frames_dir, ordered, width, height, fps, out_path) -> list:
    """Fallback: OpenCV VideoWriter com mp4v."""
    writer = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), float(fps), (width, height))
    if not writer.isOpened():
        writer.release()
        return []
    written: list = []
    for img in _read_frames(frames_dir, ordered, width, height, written):
        writer.write(img)
    writer.release()
    return written


def assemble_mp4(frames_dir: str, frames: list, width: int, height: int,
                 fps: float, out_path: str) -> tuple[str | None, list]:
    """Retorna (codec_usado | None, frames que entraram no vídeo, na ordem). Tenta H.264, depois mp4v."""
    fps = float(fps) if fps and fps > 0 else 15.0
    width = _even(width or 1024)
    height = _even(height or 1024)
    ordered = sorted(frames, key=lambda f: f.get("idx", 0))

    try:
        written = _assemble_h264(frames_dir, ordered, width, height, fps, out_path)
        if written and os.path.isfile(out_path) and os.path.getsize(out_path) > 0:
            return "h264", written
    except Exception as e:  # cai para o fallback
        logger.warning("H.264 indisponível (%s); tentando mp4v pelo OpenCV", e)

    written = _assemble_mp4v(frames_dir, ordered, width, height, fps, out_path)
    if written and os.path.isfile(out_path) and os.path.getsize(out_path) > 0:
        return "mp4v", written

    return None, []
