"""Análise dos dados (services/analysis.py) e validação do JSON v2 (services/tracking.py), sem banco:
as métricas batem com o que o gerador do simulador produziu de propósito (app/synthetic.py)."""
import copy
import math

import numpy as np
import pytest

from app.services import analysis, tracking
from app.synthetic import Recording, VirtualClock, contain, play

PANEL = {"widthM": 2.4, "heightM": 1.35, "distanceM": 2.0}


def load_message(n=6, seconds=5.0, kind="image", record=False):
    return {
        "id": "sessao-teste", "record": record, "capture": {"width": 64, "height": 40, "fps": 10},
        "stimuli": [
            {"position": i, "stimulusId": f"estimulo-{i}", "name": f"Rosto {i:02d}", "kind": kind, "format": "jpg",
             "sha256": "0" * 64, "width": 1600, "height": 1000,
             "screenSeconds": seconds if kind == "image" else None, "mediaSeconds": seconds if kind == "video" else None}
            for i in range(1, n + 1)
        ],
    }


def run(steps, seed="teste", **message):
    clock = VirtualClock()
    recording = Recording(load_message(**message), lambda stim: "", None, seed=seed, clock=clock)
    play(recording, clock, steps)
    doc = recording.document({"id": "simulador", "name": "Quest Pro 01", "model": "Quest Pro"}, "teste")
    tracking.validate(doc, "sessao-teste")
    return doc, recording.truth()


def doc_with(gaze, events, stimuli=None, face=None, names=None):
    return {
        "version": 2,
        "meta": {"sessionId": "s", "panel": PANEL, "gazeHz": 72, "faceExpressions": names},
        "stimuli": stimuli if stimuli is not None else [
            {"position": 1, "stimulusId": "a", "kind": "image", "width": 1600, "height": 1000},
        ],
        "events": events, "gaze": gaze, "face": face, "frames": [],
    }


def fixation_samples(t0, duration, u, v, hz=72, noise=0.0, seed=1):
    rng = np.random.default_rng(seed)
    n = int(round(duration * hz))
    return [{"t": round(t0 + k / hz, 5), "valid": True, "onStim": True,
             "stimUv": [u + rng.normal(0, noise) if noise else u, v + rng.normal(0, noise) if noise else v]}
            for k in range(n)]


# ---- Com o gerador do simulador -------------------------------------------------------------------

@pytest.mark.parametrize("seed", ["a", "b", "neurosight"])
def test_metrics_match_what_the_simulator_generated(seed):
    doc, truth = run([(3.217, "next"), (40.0, "button_b")], seed=seed, n=6)
    result = analysis.analyze(doc)

    assert len(result.exposures) == len(truth["exposures"]) == 6
    assert result.samples == truth["samples"] and result.valid_samples == truth["validSamples"]
    true_fixations = found = off_duration = 0
    for exposure, expected in zip(result.exposures, truth["exposures"]):
        assert (exposure.position, exposure.stimulus_id) == (expected["position"], expected["stimulusId"])
        assert exposure.on == pytest.approx(expected["on"]) and exposure.off == pytest.approx(expected["off"])
        assert exposure.samples == expected["samples"] and exposure.valid_samples == expected["validSamples"]
        # Fixações cortadas no fim do estímulo com menos de 100 ms não contam; perto disso, pode faltar uma.
        long = [f for f in expected["fixations"] if f["duration"] >= 0.1]
        assert len(long) - 1 <= exposure.fixation_count <= len(long)
        true_fixations += len(long)
        found += exposure.fixation_count
        assert exposure.first_fixation_ms / 1000 == pytest.approx(
            expected["fixations"][0]["start"] - expected["on"], abs=0.03)
        # Cada fixação achada corresponde a uma gerada, no mesmo lugar e na mesma hora. A duração
        # pode sair menor quando o ruído corta o fim da fixação num pedaço de menos de 100 ms.
        for fix in exposure.fixations:
            match = min(long, key=lambda f: abs(f["start"] - fix.start))
            assert fix.start == pytest.approx(match["start"], abs=0.03)
            assert (fix.u, fix.v) == pytest.approx((match["u"], match["v"]), abs=0.005)
            assert fix.duration <= match["duration"] + 0.03
            off_duration += abs(fix.duration - match["duration"]) > 0.03
    assert found >= 0.97 * true_fixations
    assert off_duration <= 0.03 * found
    generated_mean = np.mean([f["duration"] for e in truth["exposures"] for f in e["fixations"] if f["duration"] >= 0.1])
    found_mean = np.mean([f.duration for e in result.exposures for f in e.fixations])
    assert found_mean == pytest.approx(generated_mean, abs=0.015)


def test_each_appearance_is_an_exposure_and_the_neutral_screen_is_left_out():
    doc, truth = run([(2.0, "next"), (4.0, "neutral"), (6.0, "next"), (8.0, "previous"), (9.5, "goto"),
                      (11.0, "button_b")], n=3, seconds=None)
    # O "goto" sem posição é ignorado pelo óculos; Anterior volta para o 1.
    result = analysis.analyze(doc)
    assert [(e.seq, e.position, round(e.on, 3), round(e.off, 3)) for e in result.exposures] == [
        (1, 1, 2.0, 4.0), (2, 2, 6.0, 8.0), (3, 1, 8.0, 11.0),
    ]
    assert [e["samples"] for e in truth["exposures"]] == [e.samples for e in result.exposures]
    assert result.duration == 11.0


def test_interrupted_session_closes_the_last_exposure():
    doc, _ = run([(1.0, "next"), (3.5, "interrupted")], n=3)
    result = analysis.analyze(doc)
    assert [(e.position, e.off) for e in result.exposures] == [(1, 3.5)]
    # Sem o session_end (o app caiu), a exibição vai até a última coisa registrada.
    doc["events"] = [e for e in doc["events"] if e["type"] not in ("session_end", "stimulus_off")]
    result = analysis.analyze(doc)
    assert result.exposures[0].off == pytest.approx(doc["gaze"][-1]["t"])


def test_face_series_average_both_sides_in_100_ms_windows():
    doc, _ = run([(1.0, "next"), (6.0, "button_b")], n=1)
    result = analysis.analyze(doc)
    assert set(result.face_series) == {"INNER_BROW_RAISER", "LIP_CORNER_PULLER", "EYES_CLOSED"}
    assert len(result.face_series["EYES_CLOSED"]) == 60
    names = doc["meta"]["faceExpressions"]
    left, right = names.index("INNER_BROW_RAISER_L"), names.index("INNER_BROW_RAISER_R")
    window = [w for t, w in zip(doc["face"]["t"], doc["face"]["weights"]) if 2.0 <= t < 2.1]
    expected = np.mean([(w[left] + w[right]) / 2 for w in window])
    assert result.face_series["INNER_BROW_RAISER"][20] == pytest.approx(expected, abs=0.001)
    # A média de cada exibição tem as 70 expressões, na ordem do meta.
    assert len(result.exposures[0].face_means) == 70


def test_blinks_close_the_eyes_in_the_face_data():
    """No gerador, a piscada (olhar inválido) fecha os olhos no rastreamento facial do mesmo instante,
    mesmo com o relógio virtual do seed andando aos saltos."""
    doc, _ = run([(1.0, "next"), (30.0, "button_b")], n=6)
    closed = doc["meta"]["faceExpressions"].index("EYES_CLOSED_L")
    blinking = [w[closed] == 0.95 for w in doc["face"]["weights"]]
    expected = [not doc["gaze"][int(t * 72)]["valid"] for t in doc["face"]["t"]]
    assert blinking == expected and 0 < sum(blinking) < len(blinking) / 4
    # E aparece na série da W17 (picos de Olhos fechados).
    assert max(v for v in analysis.analyze(doc).face_series["EYES_CLOSED"] if v is not None) > 0.5


def test_without_face_tracking():
    clock = VirtualClock()
    recording = Recording(load_message(n=1), lambda stim: "", None, face=False, clock=clock)
    play(recording, clock, [(1.0, "next"), (3.0, "button_b")])
    doc = recording.document({}, "teste")
    tracking.validate(doc, "sessao-teste")
    result = analysis.analyze(doc)
    assert result.face_series is None and result.exposures[0].face_means is None


# ---- I-DT ---------------------------------------------------------------------------------------------

def test_idt_needs_100_ms_within_1_degree():
    events = [{"t": 0, "type": "stimulus_on", "position": 1, "stimulusId": "a"}, {"t": 3, "type": "session_end"}]
    gaze = fixation_samples(0.5, 0.15, 0.3, 0.3) + fixation_samples(1.0, 0.08, 0.7, 0.7)
    fixations = analysis.analyze(doc_with(gaze, events)).exposures[0].fixations
    assert len(fixations) == 1  # a de 80 ms não chega aos 100 ms
    # 11 amostras a 72 Hz: do primeiro ao último instante mais um período.
    assert fixations[0].start == 0.5 and fixations[0].duration == pytest.approx(11 / 72, abs=1e-4)
    assert (fixations[0].u, fixations[0].v) == pytest.approx((0.3, 0.3))


def test_one_noisy_sample_does_not_split_a_fixation():
    events = [{"t": 0, "type": "stimulus_on", "position": 1, "stimulusId": "a"}, {"t": 3, "type": "session_end"}]
    gaze = fixation_samples(0.5, 0.6, 0.4, 0.4)
    gaze[20]["stimUv"] = [0.43, 0.4]  # ~1,8° para o lado: quebra a janela, mas volta ao mesmo lugar
    result = analysis.analyze(doc_with(gaze, events)).exposures[0]
    assert result.fixation_count == 1
    assert result.fixations[0].duration == pytest.approx(43 / 72, abs=1e-4)
    no_merge = analysis.analyze(doc_with(gaze, events), analysis.Params(merge_deg=0)).exposures[0]
    assert no_merge.fixation_count == 2


def test_blink_separates_fixations_and_counts_as_invalid():
    events = [{"t": 0, "type": "stimulus_on", "position": 1, "stimulusId": "a"}, {"t": 2, "type": "session_end"}]
    first = fixation_samples(0.0, 0.3, 0.5, 0.5)
    blink = [{"t": round(0.3 + k / 72, 5), "valid": False, "onStim": False, "stimUv": None} for k in range(11)]
    second = fixation_samples(0.3 + 11 / 72, 0.3, 0.5, 0.5)
    exposure = analysis.analyze(doc_with(first + blink + second, events)).exposures[0]
    assert exposure.fixation_count == 2  # a piscada (150 ms) é maior que os 75 ms de junção
    assert exposure.valid_samples == exposure.samples - 11
    assert exposure.valid_fraction == pytest.approx((exposure.samples - 11) / exposure.samples, abs=1e-4)


def test_degrees_follow_the_panel_geometry():
    # 1600 × 1000 num painel 16:9 de 2,4 × 1,35 m: o estímulo ocupa 2,16 × 1,35 m.
    size = analysis.stimulus_size_m({"width": 1600, "height": 1000}, PANEL)
    assert size == pytest.approx((2.16, 1.35))
    x, y, w, h = contain(1600, 1000)
    assert (w * 2.4, h * 1.35) == pytest.approx(size)
    az, el = analysis.to_degrees(np.array([0.5, 1.0]), np.array([0.5, 0.5]), size, 2.0)
    assert az[0] == 0 and az[1] == pytest.approx(math.degrees(math.atan(1.08 / 2.0)))


def test_heat_counts_samples_on_the_stimulus():
    events = [{"t": 0, "type": "stimulus_on", "position": 1, "stimulusId": "a"}, {"t": 2, "type": "session_end"}]
    gaze = fixation_samples(0.0, 0.5, 0.2, 0.8) + [{"t": 0.6, "valid": True, "onStim": False, "stimUv": None}]
    heat = analysis.analyze(doc_with(gaze, events)).exposures[0].heat
    # 36 amostras na célula (16, 64) da grade de 80 × 80, guardada pelo centro.
    assert heat == [[round(16.5 / 80, 4), round(64.5 / 80, 4), 36]]


def test_frame_gaze_uses_the_nearest_valid_sample():
    doc, _ = run([(1.0, "next"), (3.0, "button_b")], n=1, record=False)
    gaze = analysis.Gaze([
        {"t": 0.0, "valid": True, "frameUv": [0.1, 0.2]},
        {"t": 0.5, "valid": False, "frameUv": None},
        {"t": 1.0, "valid": True, "frameUv": [0.3, 0.4]},
    ])
    frames = [{"t": 0.01}, {"t": 0.5}, {"t": 0.7}, {"t": 0.99}]
    assert analysis.frame_gaze(gaze, frames) == [[0.1, 0.2], None, None, [0.3, 0.4]]


# ---- Validação do contrato -------------------------------------------------------------------------

def test_validation_points_to_the_problem():
    doc, _ = run([(1.0, "next"), (2.0, "button_b")], n=1)
    tracking.validate(doc, "sessao-teste")

    def problem(change):
        broken = copy.deepcopy(doc)
        change(broken)
        with pytest.raises(tracking.TrackingError) as error:
            tracking.validate(broken, "sessao-teste")
        return str(error.value)

    assert problem(lambda d: d.update(version=1)) == "o JSON não segue o contrato v2 (version 2)"
    assert problem(lambda d: d["meta"].update(sessionId="outra")) == "o meta.sessionId não é o desta sessão"
    assert problem(lambda d: d["meta"]["panel"].pop("distanceM")).startswith("meta.panel precisa")
    assert problem(lambda d: d["gaze"][12].update(t="1")) == "gaze[12]: t precisa ser um número"
    assert problem(lambda d: d["gaze"][3].update(stimUv=[0.5])) == "gaze[3]: stimUv precisa ser [u, v] ou null"
    assert problem(lambda d: d["events"][3].pop("position")) == "events[3]: falta a position"
    assert problem(lambda d: d["face"]["weights"][5].pop()) == "face.weights: cada linha precisa ter 70 números"
    assert problem(lambda d: d["meta"].update(faceExpressions=None)) == "face veio sem o meta.faceExpressions"
    assert problem(lambda d: d["frames"].append({"idx": 1, "t": 0.1, "file": "../x.jpg"})) == \
        "frames[0]: file precisa ser NNNNNN.jpg"
    assert problem(lambda d: d["meta"].update(endReason="queda")) == "meta.endReason precisa ser button_b ou interrupted"
    # Tipos de evento e campos desconhecidos passam (o protocolo cresce sem quebrar a outra ponta).
    doc["events"].append({"t": 1.5, "type": "algo_novo"})
    doc["meta"]["campoNovo"] = True
    tracking.validate(doc, "sessao-teste")
