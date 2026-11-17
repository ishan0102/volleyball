"""Detect volleyball contacts across a prepared recording, then identify the players."""

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import time
from uuid import NAMESPACE_URL, uuid5

import cv2
import numpy as np
from media import save, clip

ROOT = Path(__file__).resolve().parent
MODEL = ROOT / "models" / "ravel"
RELEASE = "c3864156a4dfbd5af3f00f427ab0fc4bfe7af5b5"
VERSION = "ravel013-f32-step2-v1"
HASHES = {
    "xml": "e1f92523fc5f13c134d58a13c3e986ce129facfe4a3bf1bd7c8d5b569220de23",
    "bin": "c9dc10f03bfc3ca4e34021e4cf57bbf631a4f9f3b67d825d17b9a1c6284baf42",
}
_model = None


def model_files():
    from urllib.request import urlopen

    MODEL.mkdir(parents=True, exist_ok=True)
    for ext, sha in HASHES.items():
        path = MODEL / f"model.{ext}"
        if not path.exists():
            url = f"https://raw.githubusercontent.com/asigatchov/fast-volleyball-tracking-inference/{RELEASE}/ov/RAVEL-VB-013-9f.{ext}"
            with urlopen(url, timeout=120) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != sha:
                raise ValueError("Touch model download failed checksum verification")
            tmp = path.with_suffix(".download")
            tmp.write_bytes(data)
            tmp.replace(path)
        if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise ValueError(f"Touch model is damaged: {path}")


def model():
    global _model
    if _model is None:
        import openvino as ov

        cv2.setNumThreads(1)
        # ARM's default f16 overflows the proposal head and returns zero players.
        _model = ov.Core().compile_model(
            str(MODEL / "model.xml"),
            "CPU",
            {"INFERENCE_NUM_THREADS": 3, "INFERENCE_PRECISION_HINT": "f32"},
        )
    return _model


def decode(outputs, timestamps):
    logits = outputs["logits"][0]
    probabilities = np.exp(logits - logits.max(axis=-1, keepdims=True))
    probabilities /= probabilities.sum(axis=-1, keepdims=True)
    contacts = np.exp(outputs["action_logits"][0, :, :, 0])
    result = []
    for i, t in enumerate(timestamps):
        scores = contacts[i] * (probabilities[i, :, 1] >= 0.4)
        q = int(np.argmax(scores))
        score = float(scores[q])
        if score < 0.20:
            continue
        cx, cy, w, h = outputs["boxes"][0, i, q]
        x1, y1 = np.clip([cx - w / 2, cy - h / 2], 0, 1)
        x2, y2 = np.clip([cx + w / 2, cy + h / 2], 0, 1)
        if x2 <= x1 or y2 - y1 < 0.035:
            continue
        grid = outputs["ball_grid"][0, i]
        yy, xx = np.unravel_index(grid[0].argmax(), grid[0].shape)
        ball = [
            (xx + float(grid[1, yy, xx])) / grid.shape[2],
            (yy + float(grid[2, yy, xx])) / grid.shape[1],
            float(grid[0, yy, xx]),
        ]
        result.append(
            dict(
                time=round(t, 3),
                score=round(score, 4),
                box=[float(x1), float(y1), float(x2 - x1), float(y2 - y1)],
                ball=ball,
            )
        )
    return result


def infer_minute(args):
    folder, minute, duration, fingerprint = args
    cache = folder / "touch-scan" / "frames"
    target = cache / f"{minute:03}.json"
    if target.exists():
        stored = json.loads(target.read_text())
        if stored.get("fingerprint") == fingerprint:
            return stored["rows"]
    video = cv2.VideoCapture(str(folder / "preview.mp4"))
    fps = video.get(cv2.CAP_PROP_FPS)
    if not fps > 0:
        raise ValueError("Cannot read preview frame rate")
    start = max(0, minute * 60 - 0.6)
    end = min(duration, (minute + 1) * 60 + 0.6)
    first, last = round(start * fps), math.ceil(end * fps)
    video.set(cv2.CAP_PROP_POS_FRAMES, first)
    batch, times, rows = [], [], []
    net = model()

    def flush():
        if not batch:
            return
        padded = batch + [batch[-1]] * (9 - len(batch))
        raw = net(np.stack(padded)[None])
        outputs = {k.any_name: v for k, v in raw.items()}
        rows.extend(decode(outputs, times))
        batch.clear()
        times.clear()

    try:
        for frame_no in range(first, last):
            if not video.grab():
                raise ValueError(f"Preview decode stopped at {frame_no / fps:.2f}s")
            if (frame_no - first) % 2:
                continue
            ok, frame = video.retrieve()
            if not ok:
                raise ValueError("Cannot decode preview frame")
            rgb = cv2.cvtColor(
                cv2.resize(frame, (640, 360), interpolation=cv2.INTER_AREA),
                cv2.COLOR_BGR2RGB,
            )
            batch.append(
                np.ascontiguousarray(rgb.transpose(2, 0, 1), dtype=np.float32) / 255
            )
            times.append(frame_no / fps)
            if len(batch) == 9:
                flush()
        flush()
    finally:
        video.release()
    # Each minute owns its central interval; overlap supplies temporal context only.
    rows = [r for r in rows if minute * 60 <= r["time"] < (minute + 1) * 60]
    save(target, dict(fingerprint=fingerprint, rows=rows))
    return rows


def peaks(rows, threshold=0.5):
    """Keep temporal peaks, not one event per visible person or video frame."""
    selected = []
    rows = sorted(rows, key=lambda r: r["time"])
    for row in sorted(rows, key=lambda r: r["score"], reverse=True):
        if row["score"] < threshold:
            break
        if any(abs(row["time"] - r["time"]) < 0.8 for r in selected):
            continue
        support = [
            r
            for r in rows
            if abs(r["time"] - row["time"]) <= 0.16 and r["score"] >= threshold * 0.65
        ]
        if len(support) < 2:
            continue
        selected.append(dict(row, support=len(support)))
    return sorted(selected, key=lambda r: r["time"])


class Identity:
    def __init__(self, folder, state):
        from scan_players import reference_crops, compile_model

        self.folder = folder
        cache = folder / "appearance-scan"
        vectors = {}
        for path in cache.glob("features-*.npz"):
            with np.load(path) as data:
                vectors.update(zip(data["keys"].tolist(), data["vectors"]))
        self.vectors = vectors
        self.cache = cache
        frames = {}
        # Only explicit/manual or user-reviewed pins are trusted reference identities.
        tags = [
            t
            for c in state["clips"]
            for t in c["tags"]
            if t.get("source") != "automatic"
        ]
        for t in tags:
            ms = round(t["time"] * 1000)
            path = cache / "detections" / f"{ms:09}.json"
            frames[ms] = []
            if path.exists():
                for r in json.loads(path.read_text()):
                    if r["file"] in vectors:
                        frames[ms].append(dict(r, feature=vectors[r["file"]]))
        refs = reference_crops(frames, tags)
        if not refs:
            raise ValueError(
                "Run the player scan after labeling the roster, then scan touches."
            )
        self.names = sorted(refs)
        gallery = [r for n in self.names for r in refs[n]]
        self.boundaries = np.cumsum([0] + [len(refs[n]) for n in self.names])
        self.features = np.array([r["feature"] for r in gallery])
        self.colors = np.array([r["colors"] for r in gallery])
        self.net = compile_model(cache)

    def identify(self, frame, box, time=None):
        from players import describe

        h, w = frame.shape[:2]
        x, y, bw, bh = box
        # RAVEL body boxes can omit the head. Reuse the existing full-person
        # detector/embedding at the nearest second so crops match the gallery.
        if time is not None:
            choices = []
            for second in range(max(0, math.floor(time) - 2), math.ceil(time) + 3):
                path = self.cache / "detections" / f"{second * 1000:09}.json"
                if not path.exists():
                    continue
                for r in json.loads(path.read_text()):
                    if r["file"] not in self.vectors:
                        continue
                    rx, ry, rw, rh = r["box"]
                    area = max(0, min(x + bw, rx + rw) - max(x, rx)) * max(
                        0, min(y + bh, ry + rh) - max(y, ry)
                    )
                    overlap = area / max(bw * bh + rw * rh - area, 1e-8)
                    if overlap >= 0.30:
                        ranked = self.rank(self.vectors[r["file"]], r["colors"])
                        quality = (
                            0.55 * ranked[1]
                            + 0.45 * overlap
                            - 0.04 * abs(second - time)
                        )
                        choices.append((quality, overlap, ranked))
            if choices:
                _, overlap, ranked = max(choices, key=lambda c: c[0])
                return ranked
        crop = frame[
            max(0, int(y * h)) : min(h, int((y + bh) * h)),
            max(0, int(x * w)) : min(w, int((x + bw) * w)),
        ]
        if not crop.size:
            return "Unknown player", 0.0, 0.0
        # Match the cached gallery's crop resize before the re-ID model input resize.
        crop = cv2.resize(crop, (72, 144), interpolation=cv2.INTER_AREA)
        vector = (
            self.net(cv2.dnn.blobFromImage(crop, size=(128, 256)))[0].ravel().copy()
        )
        vector /= max(np.linalg.norm(vector), 1e-8)
        colors = describe(
            cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), (x * w, y * h, bw * w, bh * h)
        )
        return self.rank(vector, colors)

    def rank(self, vector, colors):
        similarity = self.features @ vector
        if colors:
            similarity -= 0.001 * np.minimum(
                np.abs(self.colors - colors).mean(axis=1), 100
            )
        scores = np.maximum.reduceat(similarity, self.boundaries[:-1])
        rank = np.argsort(scores)[::-1]
        score = float(scores[rank[0]])
        margin = score - float(scores[rank[1]]) if len(rank) > 1 else score
        return (
            (self.names[rank[0]] if score >= 0.52 else "Unknown player"),
            score,
            margin,
        )


def name_events(folder, state, events):
    identity = Identity(folder, state)
    video = cv2.VideoCapture(str(folder / "preview.mp4"))
    try:
        for event in events:
            video.set(cv2.CAP_PROP_POS_MSEC, event["time"] * 1000)
            ok, frame = video.read()
            if not ok:
                raise ValueError("Cannot identify player at contact")
            name, score, margin = identity.identify(frame, event["box"], event["time"])
            event.update(
                name=name,
                identityScore=round(score, 4),
                identityMargin=round(margin, 4),
                uncertain=event["score"] < 0.75
                or score < 0.67
                or margin < 0.06
                or event.get("ballScore", 1) < 0.6,
            )
    finally:
        video.release()
    return events


def apply_events(state, events, match_id):
    """Merge a rerun without overwriting edits, dismissals, or existing labeled contacts."""
    added = 0
    for event in events:
        t = event["time"]
        # Reruns and threshold changes may move a peak slightly. Keep the original decision.
        if any(
            abs(c["detection"]["time"] - t) < 0.8
            for c in state["clips"]
            if c.get("detection")
        ):
            continue
        if any(
            tag.get("skill") not in (None, "Appearance")
            and tag["name"] == event["name"]
            and abs(tag["time"] - t) < 1.6
            for c in state["clips"]
            for tag in c["tags"]
        ):
            continue
        identifier = uuid5(
            NAMESPACE_URL, f"touch/{match_id}/{VERSION}/{round(t * 10)}"
        ).hex
        x, y, w, h = event["box"]
        item = clip(max(0, t - 3), min(state["duration"], t + 4))
        item.update(
            id=identifier,
            keep=True,
            note=f"{event['name']} · detected touch",
            description=f"Ball contact detected at {int(t // 60)}:{int(t % 60):02d}. The clip includes the approach and the next few seconds of play.",
            detection=dict(event, status="automatic", model=VERSION),
            tags=[
                dict(
                    id=identifier,
                    name=event["name"],
                    skill="Touch",
                    result="Ungraded",
                    time=t,
                    x=x + w / 2,
                    y=y + h * 0.38,
                    source="automatic",
                )
            ],
        )
        state["clips"].append(item)
        added += 1
    if added:
        state["revision"] += 1
    return added


def decide(state, data):
    if data["revision"] != state["revision"]:
        raise ValueError("The match changed. Refresh before reviewing this touch.")
    item = next((c for c in state["clips"] if c["id"] == data["id"]), None)
    if not item or not item.get("detection"):
        raise ValueError("Unknown detected touch")
    status = data["status"]
    if status not in ("automatic", "confirmed", "dismissed"):
        raise ValueError("Unknown touch review status")
    item["detection"]["status"] = status
    state["revision"] += 1
    return item["id"]


def status(folder, **values):
    save(
        folder / "touch-scan" / "status.json",
        dict(pid=os.getpid(), updated=time.time(), **values),
    )


def scan(folder, workers=3, threshold=0.5):
    folder = folder.resolve()
    cache = folder / "touch-scan"
    (cache / "frames").mkdir(parents=True, exist_ok=True)
    with (cache / ".scan.lock").open("a") as gate:
        try:
            fcntl.flock(gate, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("A touch scan is already running for this match")
        try:
            state = json.loads((folder / "match.json").read_text())
            duration = state["duration"]
            total = math.ceil(duration / 60)
            status(
                folder,
                state="running",
                phase="Loading contact model",
                completed=0,
                total=total,
            )
            if not any((folder / "appearance-scan").glob("features-*.npz")):
                raise ValueError(
                    "Label the roster and run the player scan first; see README."
                )
            model_files()
            preview = (folder / "preview.mp4").stat()
            fingerprint = f"{VERSION}/{preview.st_size}/{preview.st_mtime_ns}"
            from ball_tracking import track, verify

            balls = track(
                folder,
                lambda seconds: status(
                    folder,
                    state="running",
                    phase="Tracking the ball",
                    completed=int(seconds / 60),
                    total=total,
                ),
            )
            rows = []
            with ProcessPoolExecutor(max_workers=workers) as pool:
                jobs = [
                    pool.submit(infer_minute, (folder, m, duration, fingerprint))
                    for m in range(total)
                ]
                for done, future in enumerate(as_completed(jobs), 1):
                    rows.extend(future.result())
                    status(
                        folder,
                        state="running",
                        phase="Finding ball contacts",
                        completed=done,
                        total=total,
                    )
                    print(f"Contact scan: {done}/{total} minutes", flush=True)
            events = verify(peaks(rows, threshold), balls)
            status(
                folder,
                state="running",
                phase="Matching player identities",
                completed=total,
                total=total,
            )
            # Read again to incorporate any newly reviewed player references.
            state = json.loads((folder / "match.json").read_text())
            events = name_events(folder, state, events)
            save(cache / "events.json", events)
            with (folder / ".edit.lock").open("a") as edit:
                fcntl.flock(edit, fcntl.LOCK_EX)
                state = json.loads((folder / "match.json").read_text())
                added = apply_events(state, events, folder.name)
                save(folder / "match.json", state)
            counts = dict(Counter(e["name"] for e in events))
            status(
                folder,
                state="complete",
                phase="Complete",
                completed=total,
                total=total,
                added=added,
                detected=len(events),
                players=counts,
                threshold=threshold,
            )
            print(
                json.dumps(dict(added=added, detected=len(events), players=counts)),
                flush=True,
            )
        except Exception as error:
            status(folder, state="failed", phase=str(error))
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8 or not 0.2 <= args.threshold <= 1:
        parser.error("Use 1–8 workers and a threshold between 0.2 and 1")
    scan(args.folder, args.workers, args.threshold)
