"""Merge visual rally analysis while preserving human edits and review decisions."""

import argparse
import copy
import fcntl
import json
import math
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from media import clip, save


def touch_supported(item):
    detection = item.get("detection")
    if not detection:
        return True
    if detection["status"] == "dismissed":
        return False
    return (
        detection["status"] == "confirmed" or detection.get("validation") == "supported"
    )


def combine_rallies(rows):
    result = []
    for row in sorted(rows, key=lambda r: r["start"]):
        r = copy.deepcopy(row)
        previous = result[-1] if result else None
        overlap = (
            min(r["end"], previous["end"]) - max(r["start"], previous["start"])
            if previous
            else 0
        )
        if previous and overlap > min(3, (r["end"] - r["start"]) * 0.5):
            # Windows overlap, but never join two episodes merely because they're close.
            previous["start"] = min(previous["start"], r["start"])
            previous["end"] = max(previous["end"], r["end"])
            previous["start_visible"] |= r["start_visible"]
            previous["end_visible"] |= r["end_visible"]
            if r["excitement"] > previous["excitement"]:
                for key in ("title", "description", "highlight_reason", "excitement"):
                    previous[key] = r[key]
            for moment in r["moments"]:
                if all(
                    abs(moment["time"] - m["time"]) > 1 for m in previous["moments"]
                ):
                    previous["moments"].append(moment)
            previous["moments"].sort(key=lambda m: m["time"])
        else:
            result.append(r)
    return result


def apply_analysis(state, analysis, match_id):
    baseline = analysis.get("baseline", {})
    by_id = {c["id"]: c for c in state["clips"]}
    labels = {c["id"]: c for block in analysis["results"] for c in block["clips"]}
    changed = 0
    for identifier, label in labels.items():
        item = by_id.get(identifier)
        if not item:
            continue
        original = baseline.get(identifier, {})
        generated = dict(
            kind=label["category"],
            title=label["title"],
            description=label["description"],
            claim=label["claimed_touch"],
            evidence=label["evidence"],
            model=analysis["model"],
            version=analysis["version"],
            status="automatic",
        )
        if item.get("analysis") != generated:
            item["analysis"] = generated
            changed += 1
        # Only replace empty or known machine-written text. User prose always wins.
        for key, value in (
            ("note", label["title"]),
            ("description", label["description"]),
        ):
            current = item.get(key, "")
            if current != original.get(key, current):
                continue
            is_generated = (
                not current
                or (key == "note" and current.endswith(" · detected touch"))
                or (
                    key == "description"
                    and current.startswith("Ball contact detected at ")
                )
            )
            if is_generated:
                item[key] = value
        # First-pass frame descriptions are not sufficient to prove exact contact/identity.
        # Keep every old detection recoverable, but out of touch counts and automatic reels.
        if item.get("detection") and "validation" not in item["detection"]:
            item["detection"]["validation"] = "unverified"
    rows = combine_rallies(
        [r for block in analysis["results"] for r in block["rallies"]]
    )
    for number, r in enumerate(rows, 1):
        if not 0 <= r["start"] < r["end"] <= state["duration"]:
            raise ValueError("Rally outside recording")
        # The source span and stable ID are retained on a cached rerun.
        identifier = uuid5(
            NAMESPACE_URL, f"rally/{match_id}/{analysis['version']}/{round(r['start'])}"
        ).hex
        if identifier in by_id:
            continue
        # Existing full-rally clips retain their human edits, keep decisions and IDs.
        existing = next(
            (
                c
                for c in state["clips"]
                if c.get("analysis", {}).get("liveStart") is not None
                and min(c["analysis"]["liveEnd"], r["end"])
                - max(c["analysis"]["liveStart"], r["start"])
                > 0.7
                * min(
                    c["analysis"]["liveEnd"] - c["analysis"]["liveStart"],
                    r["end"] - r["start"],
                )
            ),
            None,
        )
        if existing:
            continue
        item = clip(max(0, r["start"] - 1), min(state["duration"], r["end"] + 1))
        item.update(
            id=identifier,
            note=r["title"],
            description=r["description"],
            keep=False,
            analysis=dict(
                kind="rally",
                number=number,
                title=r["title"],
                description=r["description"],
                liveStart=r["start"],
                liveEnd=r["end"],
                complete=r["start_visible"] and r["end_visible"],
                highlightScore=r["excitement"],
                highlightReason=r["highlight_reason"],
                moments=r["moments"],
                model=analysis["model"],
                version=analysis["version"],
                status="automatic",
            ),
        )
        state["clips"].append(item)
        changed += 1
    if changed:
        state["revision"] += 1
    state["analysis"] = dict(
        model=analysis["model"],
        version=analysis["version"],
        windows=analysis.get("windows", analysis.get("minutes", [])),
        labeled=len(labels),
        rallies=len(rows),
        totalWindows=math.ceil(state["duration"] / analysis.get("windowSeconds", 60)),
    )
    return dict(labeled=len(labels), rallies=len(rows), changed=changed)


def publish(folder, source):
    data = json.loads(source.read_text())
    with (folder / ".edit.lock").open("a") as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        state = json.loads((folder / "match.json").read_text())
        backup = folder / "analysis" / "before-visual-analysis.json"
        if not backup.exists():
            backup.parent.mkdir(exist_ok=True)
            save(backup, state)
        result = apply_analysis(state, data, folder.name)
        save(folder / "match.json", state)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    print(json.dumps(publish(args.folder, args.results)))
