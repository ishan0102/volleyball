"""Persist a single player label without replacing another reviewer's edits."""

import math
import re
from uuid import uuid4

from media import clip

SKILLS = ["Appearance", "Serve", "Pass", "Set", "Attack", "Block", "Dig"]
RESULTS = ["Ungraded", "Positive", "In play", "Error"]


def numeric(value, low, high):
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError("Value outside the match range.")
    return value


def validated_tag(tag, start, end):
    name = tag["name"].strip()
    if not 0 < len(name) <= 60:
        raise ValueError("Enter a player name of up to 60 characters.")
    if tag["skill"] not in SKILLS or tag["result"] not in RESULTS:
        raise ValueError("Unknown touch or outcome.")
    label = dict(
        name=name,
        skill=tag["skill"],
        result=tag["result"],
        time=numeric(tag["time"], start, end),
        x=numeric(tag["x"], 0, 1),
        y=numeric(tag["y"], 0, 1),
    )
    if tag.get("source") in ("automatic", "reviewed"):
        label["source"] = tag["source"]
    if "id" in tag:
        if not re.fullmatch(r"[0-9a-f-]{32,36}", tag["id"]):
            raise ValueError("Invalid tag identifier.")
        label["id"] = tag["id"]
    return label


def save_tag(state, data):
    label = validated_tag(data["tag"], 0, state["duration"])
    if "id" not in label:
        raise ValueError("A new tag needs an identifier.")
    for item in state["clips"]:
        if any(t.get("id") == label["id"] for t in item["tags"]):
            return item["id"]
    target = next((c for c in state["clips"] if c["id"] == data["clipId"]), None)
    if data["clipId"] is not None and target is None:
        raise ValueError("The clip has changed. Select it again.")
    if target is None:
        t = label["time"]
        target = clip(max(0, t - 4), min(state["duration"], t + 6))
        target["id"] = uuid4().hex
        state["clips"].append(target)
    numeric(label["time"], target["start"], target["end"])
    target["tags"].append(label)
    state["revision"] += 1
    return target["id"]
