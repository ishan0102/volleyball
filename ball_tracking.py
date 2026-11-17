"""Independent temporal ball tracking used to validate candidate contacts.

VballNetFastV1 input/heatmap decoding follows the MIT-licensed upstream model
contract; attribution and pinned source are in models/RAVEL-LICENSE and README.
"""

import hashlib
import json
from pathlib import Path
from urllib.request import urlopen
import cv2
import numpy as np
from media import save

SHA = "a37d2f082c1821c31da10b4d3356788ed8ec0e1ba1c7d4fcbaf69f76925b0ff8"
RELEASE = "c3864156a4dfbd5af3f00f427ab0fc4bfe7af5b5"


def track(folder, progress=None):
    import openvino as ov

    path = Path(__file__).parent / "models" / "ravel" / "ball.onnx"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://raw.githubusercontent.com/asigatchov/fast-volleyball-tracking-inference/{RELEASE}/models/VballNetFastV1_seq9_grayscale_233_h288_w512.onnx"
        with urlopen(url, timeout=120) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != SHA:
            raise ValueError("Ball model download checksum mismatch")
        path.write_bytes(data)
    if hashlib.sha256(path.read_bytes()).hexdigest() != SHA:
        raise ValueError("Ball model checksum mismatch")
    preview = folder / "preview.mp4"
    st = preview.stat()
    fingerprint = f"{SHA}/{st.st_size}/{st.st_mtime_ns}"
    target = folder / "touch-scan" / "ball.json"
    if target.exists():
        cached = json.loads(target.read_text())
        if cached["fingerprint"] == fingerprint:
            return cached["rows"]
    net = ov.Core().compile_model(
        str(path),
        "CPU",
        {"INFERENCE_NUM_THREADS": 2, "INFERENCE_PRECISION_HINT": "f32"},
    )
    video = cv2.VideoCapture(str(preview))
    fps = video.get(cv2.CAP_PROP_FPS)
    frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    rows = []
    batch = []
    indices = []

    def flush():
        if not batch:
            return
        maps = net(np.stack(batch + [batch[-1]] * (9 - len(batch)))[None])[0][0]
        for idx, hm in zip(indices, maps):
            # Centroid around the strongest heatmap peak, not an arbitrary pixel.
            y, x = np.unravel_index(hm.argmax(), hm.shape)
            score = float(hm[y, x])
            if score < 0.30:
                continue
            x0, x1 = max(0, x - 4), min(512, x + 5)
            y0, y1 = max(0, y - 4), min(288, y + 5)
            patch = hm[y0:y1, x0:x1]
            weights = np.where(patch > score * 0.65, patch, 0)
            yy, xx = np.mgrid[y0:y1, x0:x1]
            den = weights.sum()
            rows.append(
                [
                    round(idx / fps, 3),
                    round(float((weights * xx).sum() / den / 512), 5),
                    round(float((weights * yy).sum() / den / 288), 5),
                    round(score, 4),
                ]
            )
        batch.clear()
        indices.clear()

    try:
        for idx in range(frames):
            ok, frame = video.read()
            if not ok:
                raise ValueError(f"Ball tracking decode stopped at {idx / fps:.2f}s")
            batch.append(
                cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (512, 288)).astype(
                    np.float32
                )
                / 255
            )
            indices.append(idx)
            if len(batch) == 9:
                flush()
            if idx and idx % round(fps * 60) == 0 and progress:
                progress(idx / fps)
        flush()
    finally:
        video.release()
    save(target, dict(fingerprint=fingerprint, rows=rows))
    return rows


def verify(events, balls):
    """Require a moving, independently tracked ball near the predicted actor."""
    points = np.asarray(balls)
    if not len(points):
        return []
    result = []
    for e in events:
        t = e["time"]
        x, y, w, h = e["box"]
        near = points[(points[:, 0] >= t - 0.3) & (points[:, 0] <= t + 0.3)]
        window = points[(points[:, 0] >= t - 0.65) & (points[:, 0] <= t + 0.65)]
        if len(near) < 3 or len(window) < 5:
            continue
        # Allow extended arms above/beside the torso; include low defensive contacts.
        dx = np.maximum.reduce(
            [x - 0.035 - near[:, 1], near[:, 1] - (x + w + 0.035), np.zeros(len(near))]
        )
        dy = (
            np.maximum.reduce(
                [
                    y - h * 0.3 - near[:, 2],
                    near[:, 2] - (y + h * 0.9),
                    np.zeros(len(near)),
                ]
            )
            * 0.5625
        )
        distances = np.hypot(dx, dy)
        close = near[distances < 0.025]
        if len(close) < 2 or close[:, 3].max() < 0.45:
            continue
        strong = window[window[:, 3] >= 0.4]
        if len(strong) < 4:
            continue
        # Suppress static objects, heads, and a held ball. Ignore isolated jumps.
        dt = np.diff(strong[:, 0])
        d = np.linalg.norm(np.diff(strong[:, 1:3] * [1, 0.5625], axis=0), axis=1)
        valid = (dt > 0) & (dt < 0.18) & (d < 0.12) & (d > 0.002)
        travel = float(d[valid].sum())
        if travel < 0.05 or valid.sum() < 3:
            continue
        e = dict(
            e, ballScore=round(float(close[:, 3].max()), 4), ballTravel=round(travel, 4)
        )
        result.append(e)
    return result
