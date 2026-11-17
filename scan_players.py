"""Tag representative player appearances throughout a prepared match."""

import argparse
from collections import defaultdict
import fcntl
import hashlib
import json
import math
from multiprocessing import get_context
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import cv2
import numpy as np

from media import save
from players import people
from tags import save_tag

MODEL = "person-reidentification-retail-0288"
MODEL_BASE = f"https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1/{MODEL}/FP16/{MODEL}"
HASHES = {
    "xml": "0d5021c772e603dce69d9ef2e326ecf0a43234cc8b4c5bb5e8aa566f090bdb51",
    "bin": "08e24c2f1dd976ff8e1f667b93db2950ac8db8da09e163e1ca6463b82d1dbc42",
}


def read(path):
    return json.loads(path.read_text())


def references(state):
    return [
        t for c in state["clips"] for t in c["tags"] if t.get("source") != "automatic"
    ]


def extract(batch):
    folder, cache, times = batch
    pending = [(t, cache / "detections" / f"{round(t * 1000):09}.json") for t in times]
    pending = [(t, p) for t, p in pending if not p.exists()]
    if not pending:
        return
    video = cv2.VideoCapture(str(folder / "preview.mp4"))
    try:
        for t, path in pending:
            video.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = video.read()
            if not ok:
                raise ValueError(f"Cannot decode preview at {t:.3f}s")
            h, w = frame.shape[:2]
            rows = people(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            for i, row in enumerate(rows):
                x, y, bw, bh = row["box"]
                crop = frame[
                    int(y * h) : int((y + bh) * h), int(x * w) : int((x + bw) * w)
                ]
                row["file"] = f"{path.stem}-{i}.jpg"
                scaled = cv2.resize(crop, (72, 144), interpolation=cv2.INTER_AREA)
                if not cv2.imwrite(
                    str(cache / "crops" / row["file"]),
                    scaled,
                    [cv2.IMWRITE_JPEG_QUALITY, 87],
                ):
                    raise OSError("Cannot cache player crop")
            save(path, rows)
    finally:
        video.release()


def compile_model(directory):
    from urllib.request import urlopen
    import openvino as ov

    directory.mkdir(parents=True, exist_ok=True)
    for ext, digest in HASHES.items():
        path = directory / f"model.{ext}"
        if not path.exists():
            with urlopen(f"{MODEL_BASE}.{ext}", timeout=60) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError("Downloaded appearance model failed its checksum")
            path.write_bytes(data)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Appearance model failed checksum: {path}")
    core = ov.Core()
    model = core.read_model(directory / "model.xml")
    return core.compile_model(model, "CPU", {"INFERENCE_NUM_THREADS": 3})


def embeddings(cache, rows):
    model = None
    # Cache one matrix per minute. Rebuild a minute if new manual pins add crops.
    blocks = defaultdict(list)
    for r in rows:
        blocks[int(r["file"].split("-")[0]) // 60000].append(r)
    for minute, group in blocks.items():
        keys = [r["file"] for r in group]
        path = cache / f"features-{minute}.npz"
        vectors = None
        if path.exists():
            with np.load(path) as stored:
                if stored["keys"].tolist() == keys:
                    vectors = stored["vectors"]
        if vectors is None:
            if model is None:
                model = compile_model(cache)
            values = []
            for key in keys:
                img = cv2.imread(str(cache / "crops" / key))
                blob = cv2.dnn.blobFromImage(img, size=(128, 256))
                v = model(blob)[0].ravel().copy()
                values.append(v / max(np.linalg.norm(v), 1e-8))
            vectors = np.array(values)
            np.savez(path, keys=keys, vectors=vectors)
        for r, v in zip(group, vectors):
            r["feature"] = v


def reference_crops(frames, tags):
    refs = defaultdict(list)
    for t in tags:
        choices = []
        for r in frames[round(t["time"] * 1000)]:
            x, y, w, h = r["box"]
            px, py = (t["x"] - x) / w, (t["y"] - y) / h
            if 0 <= px <= 1 and 0 <= py <= 1:
                choices.append((math.hypot(px - 0.5, 0.65 * (py - 0.38)), r))
        if choices:
            choices.sort(key=lambda pair: pair[0])
            if len(choices) == 1 or choices[1][0] - choices[0][0] > 0.10:
                refs[t["name"]].append(choices[0][1])
    return refs


def candidates(frames, refs):
    names = sorted(refs)
    gallery = [r for name in names for r in refs[name]]
    boundaries = np.cumsum([0] + [len(refs[n]) for n in names])
    lookup = np.array([r["feature"] for r in gallery])
    palette = np.array([r["colors"] for r in gallery], dtype=np.float32)
    for ms, rows in frames.items():
        if ms % 1000 or not rows:
            continue
        sim = np.array([r["feature"] for r in rows]) @ lookup.T
        colors = np.array([r["colors"] for r in rows], dtype=np.float32)
        # Clothing helps distinguish otherwise similar silhouettes.
        diff = np.abs(colors[:, None, :] - palette).mean(axis=2)
        sim -= 0.001 * np.minimum(diff, 100)
        scores = np.maximum.reduceat(sim, boundaries[:-1], axis=1)
        for i, r in enumerate(rows):
            rank = np.argsort(scores[i])[::-1]
            n = rank[0]
            score = scores[i, n]
            runner = scores[i, rank[1]] if len(names) > 1 else 0
            rival = max((s for j, s in enumerate(scores[:, n]) if j != i), default=0)
            margin = score - max(runner, rival)
            if score < 0.59 or margin < 0.012 or r["box"][3] < 0.075:
                continue
            ref = boundaries[n] + np.argmax(sim[i, boundaries[n] : boundaries[n + 1]])
            yield dict(
                time=ms // 1000,
                name=names[n],
                box=r["box"],
                file=r["file"],
                reference=gallery[ref]["file"],
                score=float(score),
                margin=float(margin),
            )


def nearby(a, b):
    x, y, w, h = a["box"]
    bx, by, bw, bh = b["box"]
    return (
        math.hypot(x + w / 2 - bx - bw / 2, (y + h / 2 - by - bh / 2) * 0.56)
        < max(0.045, 0.48 * w)
        and 0.65 < h / bh < 1.55
    )


def representative_hits(frames, refs, state):
    by_name = defaultdict(dict)
    for hit in candidates(frames, refs):
        by_name[hit["name"]][hit["time"]] = hit
    for name, series in by_name.items():
        windows = defaultdict(list)
        for t, hit in series.items():
            neighbors = [
                series[s]
                for s in (t - 1, t + 1)
                if s in series and nearby(hit, series[s])
            ]
            if not neighbors:
                continue
            support = max(neighbors, key=lambda r: r["score"] + r["margin"])
            score = min(hit["score"], support["score"])
            margin = min(hit["margin"], support["margin"])
            if score < 0.63 or margin < 0.025:
                continue
            hit.update(strength=score, separation=margin)
            hit["automatic"] = (
                score >= 0.68 and margin >= 0.055 and hit["box"][3] >= 0.14
            )
            windows[t // 45].append(hit)
        for window, hits in windows.items():
            if any(
                t["name"] == name and int(t["time"]) // 45 == window
                for t in references(state)
            ):
                continue
            yield max(
                hits,
                key=lambda r: (r["automatic"], r["strength"] + 0.35 * r["separation"]),
            )


def add_appearance(state, event, name, source):
    x, y, w, h = event["box"]
    nearby_clips = [
        c for c in state["clips"] if c["start"] <= event["time"] <= c["end"]
    ]
    target = min(
        nearby_clips,
        key=lambda c: abs((c["start"] + c["end"]) / 2 - event["time"]),
        default=None,
    )
    return save_tag(
        state,
        {
            "clipId": target["id"] if target else None,
            "tag": dict(
                id=event["id"],
                time=event["time"],
                x=x + 0.5 * w,
                y=y + 0.38 * h,
                name=name,
                skill="Appearance",
                result="Ungraded",
                source=source,
            ),
        },
    )


def make_events(folder, hits):
    events = []
    for h in sorted(hits, key=lambda h: (h["time"], h["name"])):
        identifier = uuid5(
            NAMESPACE_URL, f"volleyball/{folder.name}/{h['name']}/{h['time'] // 45}"
        ).hex
        events.append(dict(id=identifier, **h))
    return events


def apply_events(folder, events, tags):
    path = folder / "match.json"
    with (folder / ".edit.lock").open("a") as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        state = read(path)
        if references(state) != tags:
            raise ValueError(
                "Manual labels changed during scan. Rerun to use the new labels."
            )
        scan = state.setdefault("appearances", {})
        before = json.dumps(scan, sort_keys=True)
        current = {e["id"] for e in events}
        for key in list(scan):
            if scan[key]["status"] == "pending" and key not in current:
                del scan[key]
        for e in events:
            if e["id"] in scan and scan[e["id"]]["status"] != "pending":
                continue
            e["status"] = "automatic" if e["automatic"] else "pending"
            if e["automatic"]:
                add_appearance(state, e, e["name"], "automatic")
            scan[e["id"]] = e
        if json.dumps(scan, sort_keys=True) != before:
            state["revision"] += 1
            save(path, state)


def decide(state, data):
    event = state["appearances"][data["id"]]
    if event["status"] != "pending":
        if (data["name"] is None and event["status"] == "rejected") or (
            event["status"] == "reviewed" and event["reviewedName"] == data["name"]
        ):
            return
        raise ValueError("This match was already decided. Refresh the queue.")
    if data.get("file") != event["file"]:
        raise ValueError(
            "This suggestion changed during a new scan. Refresh the queue."
        )
    if data["name"] is None:
        event["status"] = "rejected"
    else:
        name = data["name"].strip()
        if name not in {t["name"] for c in state["clips"] for t in c["tags"]}:
            raise ValueError("Choose a roster player")
        existing_clips = {c["id"] for c in state["clips"]}
        clip_id = add_appearance(state, event, name, "reviewed")
        if clip_id not in existing_clips:
            event["createdClipId"] = clip_id
        event.update(status="reviewed", reviewedName=name)
    state["revision"] += 1


def undo_review(state, data):
    event = state["appearances"][data["id"]]
    if event["status"] == "pending":
        return
    if data["revision"] != state["revision"]:
        raise ValueError("The match changed. Refresh before undoing.")
    if event["status"] not in ("reviewed", "rejected"):
        raise ValueError("Only a review decision can be undone.")
    if event["status"] == "reviewed":
        for item in state["clips"]:
            item["tags"] = [t for t in item["tags"] if t.get("id") != event["id"]]
    created_clip = event.pop("createdClipId", None)
    state["clips"] = [
        c
        for c in state["clips"]
        if c["id"] != created_clip
        or c["tags"]
        or c["keep"]
        or c["note"]
        or c.get("description")
    ]
    event["status"] = "pending"
    event.pop("reviewedName", None)
    state["revision"] += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="Prepared match directory")
    parser.add_argument(
        "--cache", type=Path, help="Override the scan cache for an offline audit"
    )
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    folder = args.folder.resolve()
    cache = args.cache or folder / "appearance-scan"
    if not args.dry_run and cache.resolve() != (folder / "appearance-scan").resolve():
        parser.error("Use the default match cache to publish review photos.")
    for sub in ("detections", "crops"):
        (cache / sub).mkdir(parents=True, exist_ok=True)
    with (cache / ".scan.lock").open("a") as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        scan(folder, cache, args.workers, args.dry_run)


def scan(folder, cache, workers, dry_run):
    state = read(folder / "match.json")
    tags = references(state)
    if not tags:
        raise ValueError("Pin at least one reference player first.")
    seconds = set(range(math.ceil(state["duration"])))
    times = sorted(seconds | {t["time"] for t in tags})
    batches = [(folder, cache, times[i : i + 60]) for i in range(0, len(times), 60)]
    with get_context("spawn").Pool(workers) as pool:
        list(pool.imap_unordered(extract, batches))
    frames = {
        round(t * 1000): read(cache / "detections" / f"{round(t * 1000):09}.json")
        for t in times
    }
    rows = [r for batch in frames.values() for r in batch]
    embeddings(cache, rows)
    refs = reference_crops(frames, tags)
    if not refs:
        raise ValueError("No player pins landed on clear detections.")
    events = make_events(folder, representative_hits(frames, refs, state))
    save(cache / "results.json", events)
    print(
        f"{len(seconds)} seconds scanned, {len(rows)} detections, {len(refs)} matched reference players."
    )
    for name in sorted({t["name"] for t in tags}):
        picks = [e for e in events if e["name"] == name]
        print(
            name,
            sum(e["automatic"] for e in picks),
            "automatic,",
            sum(not e["automatic"] for e in picks),
            "for review",
        )
    if not dry_run:
        apply_events(folder, events, tags)


if __name__ == "__main__":
    main()
