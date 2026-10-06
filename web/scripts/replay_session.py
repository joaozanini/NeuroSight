#!/usr/bin/env python3
"""Reenvia uma pasta de sessão (gaze.json + frames/) para a API — o mesmo protocolo do device.

Serve para testar a ingestão end-to-end sem o óculos (e como uploader manual de sessões
puxadas via adb pull). Faz create -> frames (em lotes) -> complete e aguarda a montagem
do MP4 (o complete é assíncrono: status processing -> complete).

Exemplos:
  py -3.12 scripts/replay_session.py "C:/GitHub/NeuroSight/headset/Saved/GazeSessions/2026-06-17_22-10-54"
  py -3.12 scripts/replay_session.py ./synthetic --api http://SERVIDOR:8000/api/v1 --api-key MINHACHAVE
"""
import argparse
import os
import sys
import time

import requests


def main():
    ap = argparse.ArgumentParser(description="Reenvia uma sessão para a API (create/frames/complete).")
    ap.add_argument("session_dir", help="pasta com gaze.json e frames/")
    ap.add_argument("--api", default="http://localhost:8000/api/v1", help="base da API")
    ap.add_argument("--batch", type=int, default=50, help="frames por requisição")
    ap.add_argument("--api-key", default="", help="valor do header X-Api-Key (se o servidor exigir)")
    ap.add_argument("--no-wait", action="store_true", help="não aguarda a montagem do MP4")
    args = ap.parse_args()

    sd = args.session_dir
    jp = os.path.join(sd, "gaze.json")
    if not os.path.isfile(jp):
        sys.exit(f"gaze.json não encontrado em {sd}")

    auth = {"X-Api-Key": args.api_key} if args.api_key else {}

    # O X-Session-Id é o nome da pasta (igual ao que o device manda).
    sid = os.path.basename(os.path.normpath(sd))
    with open(jp, "rb") as f:
        raw = f.read()

    r = requests.post(f"{args.api}/sessions", data=raw,
                      headers={"X-Session-Id": sid, "Content-Type": "application/json", **auth})
    r.raise_for_status()
    info = r.json()
    server_id = info["id"]
    print("create:", info)

    frames_dir = os.path.join(sd, "frames")
    names = []
    if os.path.isdir(frames_dir):
        names = sorted(n for n in os.listdir(frames_dir) if n.lower().endswith(".jpg"))

    # Retomada: pula os que o servidor já tem.
    start = int(info.get("received_frames", 0) or 0)
    pending = names[start:]
    print(f"frames totais={len(names)}  já no servidor={start}  a enviar={len(pending)}")

    sent = 0
    for i in range(0, len(pending), args.batch):
        batch = pending[i:i + args.batch]
        files, handles = [], []
        for n in batch:
            fh = open(os.path.join(frames_dir, n), "rb")
            handles.append(fh)
            files.append(("frames", (n, fh, "image/jpeg")))
        try:
            rr = requests.post(f"{args.api}/sessions/{server_id}/frames", files=files, headers=auth)
            rr.raise_for_status()
        finally:
            for fh in handles:
                fh.close()
        sent += len(batch)
        print(f"  enviados {start + sent}/{len(names)} (servidor: {rr.json().get('received_frames')})")

    rc = requests.post(f"{args.api}/sessions/{server_id}/complete", headers=auth)
    ok = rc.headers.get("content-type", "").startswith("application/json")
    print("complete:", rc.status_code, rc.json() if ok else rc.text)
    rc.raise_for_status()

    if not args.no_wait:
        # A montagem roda em background: acompanha o status até complete/failed.
        for _ in range(120):
            time.sleep(2)
            d = requests.get(f"{args.api}/sessions/{server_id}", headers=auth).json()
            st = d.get("status")
            print(f"  status: {st}")
            if st in ("complete", "failed"):
                if st == "failed":
                    sys.exit(f"montagem FALHOU: {d.get('error_detail')}")
                print(f"video: codec={d.get('video_codec')}  url={args.api}/sessions/{server_id}/video")
                break
        else:
            sys.exit("timeout aguardando a montagem do MP4")

    print(f"\nDetalhe: {args.api}/sessions/{server_id}")


if __name__ == "__main__":
    main()
