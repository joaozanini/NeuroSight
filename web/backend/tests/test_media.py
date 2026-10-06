"""Processamento de mídia dos estímulos: formato pelo conteúdo, leitura do vídeo, miniatura e a
versão para o óculos (até 2048 px; vídeo H.264 com faststart)."""
import cv2
import numpy as np
import pytest

from app.services import media, stimuli
from app.utils import format_bytes

from .media_files import TMP, jpeg, png, top_level_boxes, video

PROBE_ROTATED = """
Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'celular.mp4':
  Duration: 00:01:20.50, start: 0.000000, bitrate: 9000 kb/s
  Stream #0:0[0x1](und): Video: hevc (Main 10) (hvc1 / 0x31637668), yuv420p10le(tv, bt2020nc/bt2020/arib-std-b67), 1920x1080, 8000 kb/s, 29.97 fps, 30 tbr, 600 tbn (default)
      Side data:
        displaymatrix: rotation of -90.00 degrees
  Stream #0:1[0x2](und): Audio: aac (LC) (mp4a / 0x6134706D), 44100 Hz, stereo, fltp, 128 kb/s (default)
"""


def test_detect_format_uses_the_content():
    assert media.detect_format(jpeg()[:16]) == "jpg"
    assert media.detect_format(png()[:16]) == "png"
    assert media.detect_format(video()[:16]) == "mp4"
    assert media.detect_format(video(container="mov")[:16]) is None  # QuickTime, mesmo renomeado
    assert media.detect_format(b"GIF89a" + b"\0" * 10) is None
    assert media.detect_format(b"") is None


def test_parse_probe_reads_rotation_audio_and_pixel_format():
    info = media.parse_probe(PROBE_ROTATED)
    assert (info.width, info.height) == (1080, 1920)  # girado para retrato
    assert info.rotation == 270
    assert info.duration == pytest.approx(80.5)
    assert info.video_codec == "hevc" and info.pix_fmt == "yuv420p10le"
    assert info.has_audio and info.audio_codec == "aac"
    assert media.parse_probe("Input #0, mp3, from 'x.mp3':\n  Stream #0:0: Audio: mp3, 44100 Hz") is None


def test_probe_video_and_frame():
    path = TMP / "probe.mp4"
    path.write_bytes(video(seconds=2.0))
    info = media.probe_video(str(path))
    assert (info.width, info.height) == (320, 200)
    assert info.duration == pytest.approx(2.0, abs=0.1)
    assert info.has_audio is True
    frame = media.video_frame(str(path), media.thumbnail_time(info.duration))
    assert frame.shape == (200, 320, 3)


def test_unreadable_video_is_refused():
    path = TMP / "quebrado.mp4"
    path.write_bytes(video()[:64])
    with pytest.raises(media.MediaError, match="não foi possível ler o vídeo"):
        media.probe_video(str(path))


def test_thumbnail_covers_640x400_without_upscaling(tmp_path):
    out = tmp_path / "thumb.jpg"
    media.write_thumbnail(np.zeros((1080, 1920, 3), np.uint8), str(out))
    assert cv2.imread(str(out)).shape[:2] == (400, 711)
    media.write_thumbnail(np.zeros((40, 64, 3), np.uint8), str(out))
    assert cv2.imread(str(out)).shape[:2] == (40, 64)
    # PNG com transparência vira JPEG sobre fundo branco.
    transparent = np.zeros((10, 10, 4), np.uint8)
    media.write_thumbnail(transparent, str(out))
    assert cv2.imread(str(out)).mean() > 250


def test_image_device_version_is_at_most_2048_px(tmp_path):
    src = tmp_path / "original.jpg"
    src.write_bytes(jpeg(3000, 1500))
    version = media.image_device_version(str(src), "jpg", str(tmp_path))
    assert (version.width, version.height) == (2048, 1024)
    assert version.format == "jpg"
    assert len(version.sha256) == 64
    small = tmp_path / "pequena.png"
    small.write_bytes(png(64, 40, alpha=True))
    version = media.image_device_version(str(small), "png", str(tmp_path))
    assert (version.width, version.height) == (64, 40)
    assert cv2.imread(version.path, cv2.IMREAD_UNCHANGED).shape == (40, 64, 4)  # mantém a transparência


def test_huge_images_are_refused_before_decoding(tmp_path, monkeypatch):
    src = tmp_path / "grande.png"
    src.write_bytes(png(200, 100))
    monkeypatch.setattr(media, "MAX_IMAGE_PIXELS", 10_000)
    with pytest.raises(media.MediaError, match="grande demais") as error:
        media.load_image(str(src), "png")
    assert error.value.status_code == 413


@pytest.mark.parametrize("codec, pix_fmt", [("libx264", "yuv420p"), ("mpeg4", "yuv420p")])
def test_video_device_version_is_h264_with_faststart(tmp_path, codec, pix_fmt):
    src = tmp_path / "original.mp4"
    src.write_bytes(video(codec=codec, pix_fmt=pix_fmt))
    version = media.video_device_version(str(src), str(tmp_path))
    info = media.probe_video(version.path)
    assert info.video_codec == "h264" and info.pix_fmt == "yuv420p"
    assert info.has_audio is True
    assert (version.width, version.height) == (320, 200)
    boxes = top_level_boxes((tmp_path / "device.mp4").read_bytes())
    assert boxes.index("moov") < boxes.index("mdat")


def test_names_labels_and_sizes():
    assert stimuli.suggested_name("cachoeira-na-mata.jpg") == "Cachoeira na mata"
    assert stimuli.suggested_name("ROSTO_neutro__01.PNG") == "ROSTO neutro 01"
    assert stimuli.suggested_name("__-.png") == "Estímulo"
    assert stimuli.clean_tags([" Paisagem ", "paisagem", "", "Mar  aberto"]) == ["paisagem", "mar aberto"]
    assert stimuli.format_problem("video-bruto.mov", b"") == "formato não aceito. Envie o vídeo em MP4"
    assert stimuli.format_problem("animacao.gif", b"GIF89a") == "formato não aceito. Envie a imagem em JPG ou PNG"
    assert stimuli.format_problem("planilha.xlsx", b"PK") == "formato não aceito. Envie imagens em JPG ou PNG e vídeos em MP4"
    assert format_bytes(212 * 1024) == "212 KB"
    assert format_bytes(int(2.4 * 1024 * 1024)) == "2,4 MB"
    assert format_bytes(86 * 1024 * 1024) == "86 MB"
    assert format_bytes(900) == "900 B"
