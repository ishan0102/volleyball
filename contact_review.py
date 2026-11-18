"""Review short contact sequences on a private GPU; keep every user decision intact."""

import argparse
import base64
import fcntl
import hashlib
import json
from pathlib import Path
import re
import time
from uuid import uuid4

from vision import Vision, frames, save, obj, TEXT, NUMBER

VERSION = "contact-review-v5"
SCHEMA = obj(
    identity={"type": "string", "enum": ["same_player", "different_player", "unclear"]},
    contact={"type": "string", "enum": ["yes", "no", "unclear"]},
    time={"anyOf": [NUMBER, {"type": "null"}]},
    skill={
        "type": "string",
        "enum": [
            "Serve",
            "Pass",
            "Set",
            "Attack",
            "Block",
            "Dig",
            "Touch",
            "None",
            "Unclear",
        ],
    },
    title=dict(TEXT, maxLength=100),
    evidence=dict(TEXT, maxLength=350),
)
PROMPT = """You are reviewing a short volleyball sequence for a coach.
Image 1: labeled reference photos of the claimed player. Image 2: full-court context at the proposed contact time; a yellow box, if present, marks the detector's proposed player. Remaining images: consecutive video frames at 8 fps, cropped around the boxed player and stamped with recording seconds. Judge the player in the center of this crop. Other players in the full-court context image are not the target.

Does the claimed player make a volleyball contact in this sequence? Follow that player and the ball across the frames. A clear serve swing followed by the ball travelling away, or a receiving platform followed by the ball rising away, can support contact even if the exact hand-ball instant falls BETWEEN sampled frames. Do not require hand and ball to occupy the same pixel in one frame. The contact time can be approximate.

Match identity from the owner's clothing reference and visible body details; facial recognition is unnecessary. Ishan is the plain-white-shirt player in black shorts, without knee pads. The white Patagonia shirt with knee pads is Gialon. A detector box/name can be wrong: compare it to the reference.

Use contact=yes when the before/after action supports a strike or redirection by this player. Use no when they are clearly uninvolved, someone else plays the ball, or they only hold/toss/catch it between points. Use unclear when the sequence cannot distinguish these cases. Ball proximity alone is insufficient. Do not invent actions outside the sequence.

Reference images identify clothing ONLY; their pose is not evidence of an action in this sequence. Return one JSON result with a short descriptive title and one sentence of concrete visual evidence. Avoid praise such as powerful or excellent. Use skill=Touch if the contact type is unclear. identity=same_player means the acting player matches the supplied reference; different_player means another person acts; unclear means you cannot identify the actor. Do not infer identity from ethnicity.
"""


def signature(item):
    d = item.get("detection", {})
    data = dict(
        time=d.get("time"), name=d.get("name"), box=d.get("box"), tags=item["tags"]
    )
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def prepare(folder, player=None, limit=None):
    """Package 15-fps source excerpts, rather than the sparse rally-analysis video."""
    import cv2
    from media import ff
    from devbox import roster

    state = json.loads((folder / "match.json").read_text())
    roster(folder, state)
    target = folder / "verification" / "input"
    target.mkdir(parents=True, exist_ok=True)
    items = [
        c for c in state["clips"] if c.get("detection", {}).get("status") == "automatic"
    ]
    if player:
        items = [c for c in items if c["detection"]["name"] == player]
    items.sort(
        key=lambda c: (c["detection"]["name"] != "Ishan", c["detection"]["time"])
    )
    if limit:
        items = items[:limit]
    rows = []
    for c in items:
        d = c["detection"]
        rows.append(
            dict(
                id=c["id"],
                name=d["name"],
                time=d["time"],
                box=d["box"],
                signature=signature(c),
            )
        )
    controls = [
        dict(
            id="control-no-touch",
            name="Ishan",
            time=225.0,
            box=[0.1104, 0.6336, 0.0444, 0.2171],
            expected="rejected",
        ),
        dict(
            id="control-serve",
            expectedSkills=["Serve"],
            name="Ishan",
            time=594.0,
            box=[0.1295, 0.2904, 0.1953, 0.6641],
            expected="supported",
        ),
        dict(
            id="control-pass",
            expectedSkills=["Pass", "Dig"],
            name="Ishan",
            time=676.0,
            box=[0.3709, 0.4840, 0.0881, 0.4174],
            expected="supported",
        ),
        dict(
            id="control-other-server",
            name="Ishan",
            time=357.267,
            box=[0.29704684, 0.6282028, 0.05136079, 0.20656228],
            expected="rejected",
        ),
    ]
    if state.get("contactBenchmark"):
        controls = state["contactBenchmark"]
    elif folder.name != "2026-11-14-e2dba0f7":
        raise ValueError(
            "Add reviewed contactBenchmark examples for this recording before verification"
        )
    for done, row in enumerate(controls + rows):
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", row["id"]):
            raise ValueError("Invalid clip identifier")
        row["start"], row["end"] = (
            max(0, row["time"] - 1.5),
            min(state["duration"], row["time"] + 1.5),
        )
        ref = (
            folder
            / "analysis"
            / "roster"
            / (re.sub(r"[^a-zA-Z0-9_-]", "-", row["name"]) + ".jpg")
        )
        if ref.exists():
            (target / ref.name).write_bytes(ref.read_bytes())
            row["reference"] = ref.name
        video = target / (row["id"] + ".mp4")
        stamp = video.with_suffix(".json")
        source = folder / "preview.mp4"
        fingerprint = f"{source.stat().st_size}/{source.stat().st_mtime_ns}/{row['start']}/{row['end']}/15fps-crf28"
        if (
            not video.exists()
            or not stamp.exists()
            or json.loads(stamp.read_text()).get("fingerprint") != fingerprint
        ):
            tmp = target / (row["id"] + ".partial.mp4")
            ff(
                [
                    "-ss",
                    row["start"],
                    "-i",
                    source,
                    "-t",
                    row["end"] - row["start"],
                    "-an",
                    "-vf",
                    "fps=15",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "fast",
                    "-crf",
                    "28",
                    "-movflags",
                    "+faststart",
                    tmp,
                ]
            )
            tmp.replace(video)
            save(stamp, dict(fingerprint=fingerprint))
        cap = cv2.VideoCapture(str(video))
        cap.set(cv2.CAP_PROP_POS_MSEC, (row["time"] - row["start"]) * 1000)
        ok, img = cap.read()
        cap.release()
        if not ok:
            raise ValueError(f"Cannot decode {row['id']}")
        if row["box"]:
            x, y, w, h = row["box"]
            height, width = img.shape[:2]
            cv2.rectangle(
                img,
                (int(x * width), int(y * height)),
                (int((x + w) * width), int((y + h) * height)),
                (0, 220, 255),
                2,
            )
        cv2.putText(
            img,
            f"Candidate at {row['time']:.2f}s",
            (10, 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )
        cv2.imwrite(
            str(target / (row["id"] + ".jpg")), img, [cv2.IMWRITE_JPEG_QUALITY, 65]
        )
        if done % 20 == 0:
            save(
                folder / "analysis" / "transfer.json",
                dict(
                    state="running",
                    phase="Preparing contact clips",
                    completed=done,
                    total=len(rows) + len(controls),
                    unit="clips",
                ),
            )
            print(
                f"Prepared {done}/{len(rows) + len(controls)} contact excerpts",
                flush=True,
            )
    save(target / "manifest.json", dict(version=VERSION, rows=rows, controls=controls))
    return target


def verdict(result, row):
    if result["identity"] == "different_player" or result["contact"] == "no":
        return "rejected"
    if (
        result["identity"] == "same_player"
        and result["contact"] == "yes"
        and isinstance(result["time"], (int, float))
        and row["start"] <= result["time"] <= row["end"]
    ):
        return "supported"
    return "unverified"


def region(box):
    if not box:
        return None
    x, y, w, h = box
    rw, rh = min(1, max(w * 3, h * 0.5625 * 1.2)), min(1, h * 2)
    left = max(0, min(1 - rw, x + w / 2 - rw / 2))
    top = max(0, min(1 - rh, y + h / 2 - rh / 2))
    return [left, top, rw, rh]


def calibration_passed(controls):
    # Both positive and negative examples are required; contact type matters too.
    return {c.get("expected") for c in controls} == {"supported", "rejected"} and all(
        c.get("verdict") == c.get("expected")
        and (not c.get("expectedSkills") or c.get("skill") in c["expectedSkills"])
        for c in controls
    )


def scan(folder, model="qwen3-vl:8b-instruct", limit=None, calibrate=False):
    source = folder / "verification" / "input"
    manifest = json.loads((source / "manifest.json").read_text())
    target = folder / "verification"
    with (target / ".scan.lock").open("a") as gate:
        fcntl.flock(gate, fcntl.LOCK_EX | fcntl.LOCK_NB)

        def check(row):
            images = []
            if row.get("reference"):
                images.append(
                    base64.b64encode((source / row["reference"]).read_bytes()).decode()
                )
            images.append(
                base64.b64encode((source / (row["id"] + ".jpg")).read_bytes()).decode()
            )
            images += frames(
                source / (row["id"] + ".mp4"),
                0,
                row["end"] - row["start"],
                8,
                offset=row["start"],
                crop=region(row.get("box")),
            )
            prompt = (
                PROMPT
                + f"\nClaimed player: {row['name']}. Candidate time: {row['time']}. Sequence: {row['start']}–{row['end']}. Reference supplied: {bool(row.get('reference'))}. If there is no reference, identity must be unclear."
            )
            result = client.ask(
                f"contact-{row['id']}-{VERSION}",
                prompt,
                images,
                SCHEMA,
                max_output=1200,
            )
            if not row.get("reference"):
                result["identity"] = "unclear"
            if not result["title"].strip() or not result["evidence"].strip():
                raise ValueError("Empty contact review")
            return dict(
                id=row["id"],
                signature=row.get("signature"),
                model=model,
                digest=client.digest,
                version=VERSION,
                verdict=verdict(result, row),
                **result,
            )

        run_id = uuid4().hex

        def status(**values):
            save(
                target / "status.json",
                dict(
                    updated=time.time(),
                    unit="clips",
                    runId=run_id,
                    model=model,
                    **values,
                ),
            )

        try:
            status(
                state="running",
                phase="Checking known plays",
                completed=0,
                total=len(manifest["controls"]),
            )
            client = Vision(folder, model=model)
            controls = []
            for row in manifest["controls"]:
                result = check(row)
                result["expected"] = row["expected"]
                result["expectedSkills"] = row.get("expectedSkills", [])
                controls.append(result)
                status(
                    state="running",
                    phase="Checking known plays",
                    completed=len(controls),
                    total=len(manifest["controls"]),
                )
                save(target / "calibration.json", controls)
                print(json.dumps(result), flush=True)
            passed = calibration_passed(controls)
            if not passed:
                raise ValueError(
                    "GPU calibration needs review; candidates remain visible"
                )
            if calibrate:
                status(
                    state="complete",
                    phase="Calibration passed",
                    completed=len(controls),
                    total=len(controls),
                )
                return
            rows = manifest["rows"][:limit] if limit else manifest["rows"]
            results = []
            for row in rows:
                status(
                    state="running",
                    phase="Checking player contacts",
                    completed=len(results),
                    total=len(rows),
                )
                result = check(row)
                results.append(result)
                save(
                    target / "results.json",
                    dict(
                        model=model,
                        version=VERSION,
                        runId=run_id,
                        calibration=controls,
                        results=results,
                    ),
                )
                print(
                    f"{len(results)}/{len(rows)} {row['name']} {row['time']}: {result['verdict']}",
                    flush=True,
                )
            status(
                state="complete",
                phase="Contact checks complete",
                completed=len(results),
                total=len(rows),
            )
        except Exception as error:
            status(state="failed", phase=str(error))
            raise


def apply_results(state, data):
    lookup = {c["id"]: c for c in state["clips"]}
    changed = 0
    for result in data["results"]:
        item = lookup.get(result["id"])
        if (
            not item
            or item.get("detection", {}).get("status") != "automatic"
            or signature(item) != result["signature"]
        ):
            continue
        detection = item["detection"]
        if detection.get("review") == result:
            continue
        previous = detection.get("review", {})
        detection["review"] = result
        detection["validation"] = result["verdict"]
        # Results annotate candidates; only the owner confirms/dismisses or changes identity.
        if item.get("note", "").endswith(" · detected touch") or item.get(
            "note"
        ) == previous.get("title"):
            item["note"] = result["title"]
        if item.get("description", "").startswith(
            "Ball contact detected at "
        ) or item.get("description") == previous.get("evidence"):
            item["description"] = result["evidence"]
        changed += 1
    if changed:
        state["revision"] += 1
    return changed


def publish(folder, source):
    from media import save as save_match

    data = json.loads(source.read_text())
    if data.get("version") != VERSION:
        raise ValueError(
            "These GPU results use an older verification method; run checks again"
        )
    if not calibration_passed(data.get("calibration", [])):
        raise ValueError("GPU calibration failed; candidate labels are unchanged")
    with (folder / ".edit.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads((folder / "match.json").read_text())
        backup = folder / "verification" / "before-contact-review.json"
        if not backup.exists():
            save(backup, state)
        changed = apply_results(state, data)
        save_match(folder / "match.json", state)
    return changed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "scan"])
    parser.add_argument("folder", type=Path)
    parser.add_argument("--model", default="qwen3-vl:8b-instruct")
    parser.add_argument("--player")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--calibrate", action="store_true")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.folder, args.player, args.limit)
    else:
        scan(args.folder, args.model, args.limit, args.calibrate)
