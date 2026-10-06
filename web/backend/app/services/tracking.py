"""Validação do JSON v2 que o óculos envia depois do B (docs/protocolo-oculos.md, seção 4).

Confere o que a análise usa, com o caminho do problema na mensagem ("gaze[12]: t precisa ser um
número"), para o óculos (e quem o desenvolve) saber o que corrigir: a rota responde 422 com ela.
Campos desconhecidos e tipos de evento desconhecidos são aceitos e ignorados, como no resto do
protocolo. Listas vazias valem (sessão sem estímulos exibidos, sem gravação).
"""
import math
import re
from typing import Any

import numpy as np

END_REASONS = ("button_b", "interrupted")
FRAME_NAME = re.compile(r"^\d{1,8}\.jpg$")


class TrackingError(ValueError):
    """O JSON não segue o contrato v2."""


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _positive(value: Any) -> bool:
    return _number(value) and value > 0


def _uv(value: Any) -> bool:
    return value is None or (isinstance(value, list) and len(value) == 2 and all(_number(x) for x in value))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TrackingError(message)


def validate(doc: Any, session_id: str) -> None:
    """Levanta TrackingError com a primeira coisa fora do contrato."""
    _require(isinstance(doc, dict) and doc.get("version") == 2, "o JSON não segue o contrato v2 (version 2)")
    meta = doc.get("meta")
    _require(isinstance(meta, dict), "o JSON não segue o contrato v2 (falta o meta)")
    _require(meta.get("sessionId") == session_id, "o meta.sessionId não é o desta sessão")
    _meta(meta)
    names = meta.get("faceExpressions")

    stimuli = doc.get("stimuli")
    _require(isinstance(stimuli, list), "stimuli precisa ser uma lista")
    for i, stim in enumerate(stimuli):
        where = f"stimuli[{i}]"
        _require(isinstance(stim, dict), f"{where} precisa ser um objeto")
        _require(isinstance(stim.get("position"), int) and stim["position"] >= 1, f"{where}: position inválida")
        _require(isinstance(stim.get("stimulusId"), str), f"{where}: falta o stimulusId")
        _require(stim.get("kind") in ("image", "video"), f"{where}: kind precisa ser image ou video")
        for key in ("width", "height"):
            valid = stim.get(key) is None or (isinstance(stim[key], int) and stim[key] >= 0)
            _require(valid, f"{where}: {key} inválido")

    events = doc.get("events")
    _require(isinstance(events, list), "events precisa ser uma lista")
    for i, event in enumerate(events):
        where = f"events[{i}]"
        _require(isinstance(event, dict) and isinstance(event.get("type"), str), f"{where} precisa ter o type")
        _require(_number(event.get("t")) and event["t"] >= 0, f"{where}: t precisa ser um número")
        if event["type"] in ("stimulus_on", "stimulus_off"):
            _require(isinstance(event.get("position"), int), f"{where}: falta a position")

    gaze = doc.get("gaze")
    _require(isinstance(gaze, list), "gaze precisa ser uma lista")
    for i, sample in enumerate(gaze):
        where = f"gaze[{i}]"
        _require(isinstance(sample, dict), f"{where} precisa ser um objeto")
        _require(_number(sample.get("t")), f"{where}: t precisa ser um número")
        _require(isinstance(sample.get("valid"), bool), f"{where}: valid precisa ser true ou false")
        _require(isinstance(sample.get("onStim", False), bool), f"{where}: onStim precisa ser true ou false")
        _require(_uv(sample.get("stimUv")), f"{where}: stimUv precisa ser [u, v] ou null")
        _require(_uv(sample.get("frameUv")), f"{where}: frameUv precisa ser [u, v] ou null")

    face = doc.get("face")
    if face is not None:
        _require(isinstance(face, dict), "face precisa ser um objeto ou null")
        _require(isinstance(names, list), "face veio sem o meta.faceExpressions")
        times, weights = face.get("t"), face.get("weights")
        _require(isinstance(times, list) and isinstance(weights, list) and len(times) == len(weights),
                 "face.t e face.weights precisam ser listas do mesmo tamanho")
        _require(all(_number(t) for t in times), "face.t precisa ter só números")
        if weights:
            try:
                matrix = np.asarray(weights, dtype=float)
            except (TypeError, ValueError):
                raise TrackingError(f"face.weights: cada linha precisa ter {len(names)} números")
            _require(matrix.ndim == 2 and matrix.shape[1] == len(names),
                     f"face.weights: cada linha precisa ter {len(names)} números")
            _require(bool(np.isfinite(matrix).all()), "face.weights precisa ter só números")

    frames = doc.get("frames")
    _require(isinstance(frames, list), "frames precisa ser uma lista")
    for i, frame in enumerate(frames):
        where = f"frames[{i}]"
        _require(isinstance(frame, dict), f"{where} precisa ser um objeto")
        _require(isinstance(frame.get("idx"), int), f"{where}: idx precisa ser um inteiro")
        _require(_number(frame.get("t")), f"{where}: t precisa ser um número")
        _require(isinstance(frame.get("file"), str) and FRAME_NAME.match(frame["file"]) is not None,
                 f"{where}: file precisa ser NNNNNN.jpg")
    if frames:
        _require(isinstance(meta.get("capture"), dict), "frames veio sem o meta.capture")


def _meta(meta: dict) -> None:
    panel = meta.get("panel")
    _require(isinstance(panel, dict) and all(_positive(panel.get(k)) for k in ("widthM", "heightM", "distanceM")),
             "meta.panel precisa de widthM, heightM e distanceM positivos")
    capture = meta.get("capture")
    if capture is not None:
        _require(isinstance(capture, dict), "meta.capture precisa ser um objeto ou null")
        _require(isinstance(capture.get("width"), int) and capture["width"] > 1
                 and isinstance(capture.get("height"), int) and capture["height"] > 1,
                 "meta.capture precisa de width e height")
        _require(_positive(capture.get("fps")), "meta.capture.fps precisa ser positivo")
    _require(meta.get("gazeHz") is None or _positive(meta["gazeHz"]), "meta.gazeHz precisa ser positivo")
    names = meta.get("faceExpressions")
    _require(names is None or (isinstance(names, list) and all(isinstance(n, str) for n in names)),
             "meta.faceExpressions precisa ser uma lista de nomes ou null")
    _require(meta.get("endReason") in (None, *END_REASONS), "meta.endReason precisa ser button_b ou interrupted")
