"""Find similar sportswear across candidate clips. Each suggestion requires a label."""

from functools import lru_cache
import hashlib
import json
from pathlib import Path
import threading

import cv2
import numpy as np

from media import ff, save

MODEL = Path(__file__).parent / "models" / "yolox.onnx"
MODEL_SHA = "c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063"
LOCK = threading.Lock()


@lru_cache(1)
def detector():
    if (
        not MODEL.exists()
        or hashlib.sha256(MODEL.read_bytes()).hexdigest() != MODEL_SHA
    ):
        raise ValueError("The local YOLOX model is missing or damaged. See README.md.")
    cv2.setNumThreads(2)
    return cv2.dnn.readNetFromONNX(str(MODEL))


def describe(rgb, box):
    x, y, w, h = box
    # Torso and shorts colors vary less through a rally than arm and leg positions.
    colors = []
    for upper, lower in [(0.23, 0.47), (0.50, 0.67)]:
        patch = rgb[
            int(y + h * upper) : int(y + h * lower) + 1,
            int(x + w * 0.30) : int(x + w * 0.7) + 1,
        ]
        if not patch.size:
            return None
        colors.extend(np.percentile(patch, [25, 50, 75], axis=(0, 1)).ravel().tolist())
    return colors


def people(frame):
    height, width = frame.shape[:2]
    ratio = 640 / max(width, height)
    scaled = cv2.resize(frame, (round(width * ratio), round(height * ratio)))
    canvas = np.full((640, 640, 3), 114, np.uint8)
    canvas[: scaled.shape[0], : scaled.shape[1]] = scaled
    net = detector()
    net.setInput(cv2.dnn.blobFromImage(canvas))
    out = net.forward()[0]
    strides = np.repeat([8, 16, 32], [6400, 1600, 400])
    grid = np.concatenate(
        [np.indices((n, n))[::-1].reshape(2, -1).T for n in (80, 40, 20)]
    )
    scores = out[:, 4] * out[:, 5]
    valid = scores > 0.32
    centers = (out[valid, :2] + grid[valid]) * strides[valid, None]
    sizes = np.exp(out[valid, 2:4]) * strides[valid, None]
    boxes = np.column_stack((centers - sizes / 2, sizes)) / ratio
    indices = cv2.dnn.NMSBoxes(boxes.tolist(), scores[valid].tolist(), 0.32, 0.5)
    result = []
    for i in np.asarray(indices).flatten():
        x, y, w, h = boxes[i]
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(width, x + w), min(height, y + h)
        if x2 - x1 < 6 or y2 - y1 < 15:
            continue
        bounds = (x1, y1, x2 - x1, y2 - y1)
        features = describe(frame, bounds)
        if features:
            result.append(
                {
                    "box": [
                        x1 / width,
                        y1 / height,
                        (x2 - x1) / width,
                        (y2 - y1) / height,
                    ],
                    "colors": features,
                }
            )
    return result


def observations(folder, t):
    cache = folder / "players-v1"
    cache.mkdir(exist_ok=True)
    key = f"{t:.3f}"
    path = cache / (key + ".json")
    if path.exists():
        return json.loads(path.read_text())
    image = ff(
        [
            "-ss",
            key,
            "-i",
            folder / "preview.mp4",
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-c:v",
            "mjpeg",
            "-",
        ]
    )
    bgr = cv2.imdecode(np.frombuffer(image, np.uint8), cv2.IMREAD_COLOR)
    if bgr is None:
        return []
    boxes = people(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    save(path, boxes)
    return boxes


def suggest(folder, state, name):
    with LOCK:
        refs = []
        for clip in state["clips"]:
            for tag in clip["tags"]:
                if tag["name"] != name:
                    continue
                choices = []
                for p in observations(folder, tag["time"]):
                    x, y, w, h = p["box"]
                    if x <= tag["x"] <= x + w and y <= tag["y"] <= y + h:
                        choices.append((w * h, p))
                if choices:
                    refs.append(min(choices, key=lambda c: c[0])[1]["colors"])
        if not refs:
            raise ValueError(
                "Tag the center of this player’s shirt in a clear frame, save the clip, and try again."
            )
        refs = np.array(refs)
        hits = []
        for clip in state["clips"]:
            if any(t["name"] == name for t in clip["tags"]):
                continue
            choices = []
            for fraction in (0.3, 0.65):
                time = clip["start"] + (clip["end"] - clip["start"]) * fraction
                for p in observations(folder, time):
                    distance = np.mean(np.abs(refs - p["colors"]), axis=1).min()
                    x, y, w, h = p["box"]
                    if distance < 32:
                        choices.append(
                            (
                                distance,
                                dict(
                                    id=clip["id"],
                                    time=time,
                                    x=x + w * 0.5,
                                    y=y + h * 0.37,
                                ),
                            )
                        )
            if choices:
                hits.append(min(choices, key=lambda c: c[0]))
        return [p for _, p in sorted(hits, key=lambda c: c[0])[:10]]
