"""Run private visual analysis on devbox and fetch its cached results."""

import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import time

from media import ff, save

ROOT = Path(__file__).resolve().parent
REMOTE = ".local/share/volleyball"
MODEL = "qwen3-vl:8b-instruct"


def command(args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)


def ssh(host, script, **kwargs):
    return command(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, script], **kwargs
    )


@contextmanager
def connection(host):
    """Use the personal tailnet only for transfer; restore the original profile."""
    app = Path("/Applications/Tailscale.app/Contents/MacOS/Tailscale")
    original = None
    config_path = ROOT / "config.local.json"
    config = json.loads(config_path.read_text()) if config_path.exists() else {}
    tailnet = os.getenv("VOLLEYBALL_TAILNET", config.get("tailnet", ""))
    try:
        if app.exists() and tailnet:
            rows = command(
                [str(app), "switch", "--list"], capture_output=True
            ).stdout.splitlines()[1:]
            current = next(
                (r.split()[0] for r in rows if r.rstrip().endswith("*")), None
            )
            wanted = next(
                (r.split()[0] for r in rows if tailnet in r),
                None,
            )
            if current and wanted and current != wanted:
                original = current
                print(
                    "Connecting to your personal Tailscale profile for devbox transfer…",
                    flush=True,
                )
                command([str(app), "switch", wanted])
                time.sleep(3)
        for attempt in range(3):
            try:
                ssh(host, "true", timeout=15)
                break
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                if attempt == 2:
                    raise ConnectionError(
                        "Cannot reach devbox. Retry when it is online."
                    ) from None
                time.sleep(3)
        yield
    finally:
        if original:
            command([str(app), "switch", original])


def roster(folder, state):
    import cv2
    import numpy as np
    from scan_players import reference_crops, references

    tags = references(state)
    frames = {}
    for t in tags:
        ms = round(t["time"] * 1000)
        path = folder / "appearance-scan" / "detections" / f"{ms:09}.json"
        frames[ms] = json.loads(path.read_text()) if path.exists() else []
    refs = reference_crops(frames, tags)
    neutral = reference_crops(
        frames, [t for t in tags if t.get("skill") == "Appearance"]
    )
    target = folder / "analysis" / "roster"
    target.mkdir(parents=True, exist_ok=True)
    images = []
    for name, rows in sorted(refs.items()):
        rows = neutral.get(name) or rows
        picks = []
        for r in sorted(rows, key=lambda r: r["box"][2] * r["box"][3], reverse=True):
            if all(
                abs(int(r["file"].split("-")[0]) - int(q["file"].split("-")[0])) > 5000
                for q in picks
            ):
                picks.append(r)
            if len(picks) == 2:
                break
        canvas = np.full((230, 200, 3), 245, np.uint8)
        cv2.putText(
            canvas, name, (6, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (25, 25, 25), 2
        )
        for i, r in enumerate(picks):
            crop = cv2.imread(str(folder / "appearance-scan" / "crops" / r["file"]))
            canvas[35:225, i * 100 : (i + 1) * 100] = cv2.resize(crop, (100, 190))
        # Names are image labels only; identifiers in filenames are sanitized.
        safe = re.sub(r"[^a-zA-Z0-9_-]", "-", name)
        cv2.imwrite(str(target / (safe + ".jpg")), canvas)
        images.append(canvas)
    if not images:
        raise ValueError(
            "Label the roster and run the player scan before video analysis"
        )
    while len(images) % 5:
        images.append(np.full_like(images[0], 245))
    sheet = np.vstack([np.hstack(images[i : i + 5]) for i in range(0, len(images), 5)])
    path = folder / "analysis" / "roster.jpg"
    cv2.imwrite(str(path), sheet)
    return path


def run(folder, action, host="devbox", model=MODEL, windows=None):
    folder = folder.resolve()
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", folder.name) or not re.fullmatch(
        r"[a-zA-Z0-9_][a-zA-Z0-9_.@-]*", host
    ):
        raise ValueError("Invalid match or SSH host")
    cache = folder / "analysis"
    cache.mkdir(exist_ok=True)
    remote_match = f"{REMOTE}/matches/{folder.name}"
    with (cache / ".transfer.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if action == "start":
            save(
                cache / "transfer.json",
                dict(
                    state="running", phase="Preparing video for devbox", pid=os.getpid()
                ),
            )
            movie = cache / "analysis.mp4"
            if not movie.exists():
                tmp = cache / "analysis.partial.mp4"
                ff(
                    [
                        "-i",
                        folder / "preview.mp4",
                        "-vf",
                        "fps=2",
                        "-an",
                        "-c:v",
                        "libx264",
                        "-preset",
                        "fast",
                        "-crf",
                        "29",
                        "-g",
                        "4",
                        "-movflags",
                        "+faststart",
                        tmp,
                    ]
                )
                tmp.replace(movie)
            state = json.loads((folder / "match.json").read_text())
            references = roster(folder, state)
            with connection(host):
                ssh(host, f"mkdir -p {remote_match}", timeout=20)
                command(
                    [
                        "scp",
                        str(ROOT / "vision.py"),
                        str(ROOT / "analyze_match.py"),
                        f"{host}:{REMOTE}/",
                    ],
                    timeout=60,
                )
                command(
                    [
                        "rsync",
                        "-a",
                        "--partial",
                        str(movie),
                        f"{host}:{remote_match}/analysis.mp4",
                    ],
                    timeout=2400,
                )
                command(
                    [
                        "scp",
                        "-r",
                        str(references),
                        str(folder / "match.json"),
                        f"{host}:{remote_match}/",
                    ],
                    timeout=90,
                )
                extra = " --windows " + " ".join(map(str, windows)) if windows else ""
                worker = f"python3 -u {REMOTE}/analyze_match.py {remote_match} --model {shlex.quote(model)}{extra}"
                # The worker's flock prevents parallel scans of the same match.
                ssh(
                    host,
                    f"nohup {worker} > {remote_match}/analysis.log 2>&1 < /dev/null &",
                    timeout=20,
                )
            save(
                cache / "transfer.json", dict(state="complete", phase="Sent to devbox")
            )
            save(
                cache / "status.json",
                dict(
                    state="running",
                    phase="Analyzing on devbox · sync to check progress",
                    updated=time.time(),
                    model=model,
                ),
            )
            print(
                "Devbox analysis started. Run the sync command to fetch progress and results."
            )
        else:
            save(
                cache / "transfer.json",
                dict(
                    state="running", phase="Fetching devbox analysis", pid=os.getpid()
                ),
            )
            with connection(host):
                command(
                    [
                        "rsync",
                        "-a",
                        f"{host}:{remote_match}/analysis/",
                        str(cache / "remote") + "/",
                    ],
                    timeout=180,
                )
            save(
                cache / "transfer.json",
                dict(state="complete", phase="Fetched devbox analysis"),
            )
            status_path = cache / "remote" / "status.json"
            if status_path.exists():
                status = json.loads(status_path.read_text())
                if status.get("state") == "complete":
                    status.update(
                        state="needs_review",
                        phase="Draft analysis fetched. Review its accuracy before publishing.",
                    )
                save(cache / "status.json", status)
            results = cache / "remote" / "results.json"
            if action == "publish":
                if not results.exists():
                    print("The devbox is still analyzing. Progress has been updated.")
                    return
                from rallies import publish

                status = (
                    json.loads(status_path.read_text()) if status_path.exists() else {}
                )
                if status.get("state") != "complete":
                    raise ValueError(
                        "The current analysis run has not completed; refusing stale results"
                    )
                print(json.dumps(publish(folder, results)))
                save(cache / "status.json", status)
            elif results.exists():
                print("Analysis fetched. Review the cached results before publishing.")
            print((cache / "status.json").read_text())


def run_contacts(folder, action, host="devbox", model=MODEL):
    from contact_review import prepare, publish

    folder = folder.resolve()
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", folder.name) or not re.fullmatch(
        r"[a-zA-Z0-9_][a-zA-Z0-9_.@-]*", host
    ):
        raise ValueError("Invalid match or SSH host")
    cache = folder / "analysis"
    cache.mkdir(exist_ok=True)
    remote_match = f"{REMOTE}/matches/{folder.name}"
    with (cache / ".transfer.lock").open("a") as gate:
        fcntl.flock(gate, fcntl.LOCK_EX | fcntl.LOCK_NB)
        save(
            cache / "transfer.json",
            dict(
                state="running",
                phase="Preparing contact clips"
                if action == "contacts"
                else "Fetching GPU checks",
            ),
        )
        if action == "contacts":
            source = prepare(folder)
            with connection(host):
                ssh(host, f"mkdir -p {remote_match}/verification/input", timeout=20)
                command(
                    [
                        "scp",
                        str(ROOT / "vision.py"),
                        str(ROOT / "contact_review.py"),
                        f"{host}:{REMOTE}/",
                    ],
                    timeout=60,
                )
                command(
                    [
                        "rsync",
                        "-a",
                        "--partial",
                        str(source) + "/",
                        f"{host}:{remote_match}/verification/input/",
                    ],
                    timeout=1800,
                )
                worker = f"python3 -u {REMOTE}/contact_review.py scan {remote_match} --model {shlex.quote(model)}"
                ssh(
                    host,
                    f"nohup {worker} >> {remote_match}/verification/run.log 2>&1 < /dev/null &",
                    timeout=20,
                )
            save(
                cache / "status.json",
                dict(
                    state="running",
                    phase="Checking contacts on devbox",
                    unit="clips",
                    completed=0,
                    total=len(
                        json.loads((source / "manifest.json").read_text())["rows"]
                    ),
                ),
            )
        else:
            local = folder / "verification" / "remote"
            local.mkdir(parents=True, exist_ok=True)
            with connection(host):
                command(
                    [
                        "rsync",
                        "-a",
                        "--include=/status.json",
                        "--include=/results.json",
                        "--include=/calibration.json",
                        "--exclude=*",
                        f"{host}:{remote_match}/verification/",
                        str(local) + "/",
                    ],
                    timeout=120,
                )
            status = local / "status.json"
            if not status.exists():
                raise ValueError("No GPU check status yet. Start verification first.")
            current = json.loads(status.read_text())
            results = local / "results.json"
            if (
                current.get("state") != "failed"
                and results.exists()
                and current.get("runId") == json.loads(results.read_text()).get("runId")
            ):
                print(f"Updated {publish(folder, results)} candidate reviews")
            save(cache / "status.json", current)
        save(cache / "transfer.json", dict(state="complete", phase="Transfer complete"))
        print((cache / "status.json").read_text())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["start", "sync", "publish", "contacts", "sync-contacts"]
    )
    parser.add_argument("folder", type=Path)
    parser.add_argument("--host", default="devbox")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--windows", nargs="+", type=int)
    args = parser.parse_args()
    try:
        if args.action in ("contacts", "sync-contacts"):
            run_contacts(args.folder, args.action, args.host, args.model)
        else:
            run(args.folder, args.action, args.host, args.model, args.windows)
    except Exception as error:
        cache = args.folder.resolve() / "analysis"
        cache.mkdir(exist_ok=True)
        save(cache / "status.json", dict(state="failed", phase=str(error)))
        save(cache / "transfer.json", dict(state="failed", phase=str(error)))
        raise
