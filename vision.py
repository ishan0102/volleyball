"""Cached visual analysis through an owner's local Ollama server."""

import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.request import Request, urlopen


MODEL = "qwen3-vl:8b-instruct"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as f:
        json.dump(value, f, indent=2, allow_nan=False)
    Path(f.name).replace(path)


def frames(video, start, end, fps=2, offset=0, crop=None):
    """Use consecutive frames with visible recording timestamps, not a collage."""
    with tempfile.TemporaryDirectory() as tmp:
        # ffmpeg's pts offset labels the original recording time after seeking.
        filters = f"fps={fps},scale=960:-2,drawtext=text='%{{pts\\:flt\\:{start + offset}}}s':x=8:y=8:fontsize=24:fontcolor=white:box=1:boxcolor=black"
        if crop:
            x, y, w, h = crop
            filters = f"crop=iw*{w}:ih*{h}:iw*{x}:ih*{y}," + filters.replace(
                "scale=960:-2", "scale=640:640:force_original_aspect_ratio=decrease"
            )
        subprocess.run(
            [
                os.getenv("FFMPEG", "ffmpeg"),
                "-nostdin",
                "-loglevel",
                "error",
                "-ss",
                str(start),
                "-i",
                str(video),
                "-t",
                str(end - start),
                "-vf",
                filters,
                "-q:v",
                "5",
                str(Path(tmp) / "%05d.jpg"),
            ],
            check=True,
            capture_output=True,
            timeout=180,
        )
        paths = sorted(Path(tmp).glob("*.jpg"))
        if len(paths) < max(1, int((end - start) * fps) - 2):
            raise ValueError(f"Incomplete video decode at {start}s")
        return [base64.b64encode(p.read_bytes()).decode() for p in paths]


class Vision:
    def __init__(self, folder, url="http://127.0.0.1:11435", model=MODEL):
        self.cache = folder / "analysis"
        self.cache.mkdir(exist_ok=True)
        self.url = url.rstrip("/")
        self.model = model
        with urlopen(self.url + "/api/tags", timeout=15) as response:
            models = json.load(response)["models"]
        found = next((m for m in models if m["name"] == model), None)
        if not found:
            raise ValueError(f"Local model {model} is not installed")
        self.digest = found["digest"]

    def ask(self, key, prompt, images, schema, max_output=4000):
        payload = dict(
            model=self.model,
            stream=False,
            think=False,
            keep_alive="5m",
            format=schema,
            messages=[dict(role="user", content=prompt, images=images)],
            options=dict(
                temperature=0.3, num_predict=max_output, num_ctx=65536, seed=42
            ),
        )
        raw = json.dumps(payload).encode()
        fingerprint = hashlib.sha256(self.digest.encode() + raw).hexdigest()
        target = self.cache / (key + ".json")
        if target.exists():
            cached = json.loads(target.read_text())
            if cached["fingerprint"] == fingerprint:
                return cached["result"]
        request = Request(
            self.url + "/api/chat",
            data=raw,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=600) as response:
            data = json.load(response)
        if not data.get("done") or data.get("done_reason") != "stop":
            raise ValueError("Incomplete visual analysis; no labels were applied")
        result = json.loads(data["message"]["content"])
        save(
            target,
            dict(
                fingerprint=fingerprint,
                result=result,
                model=self.model,
                digest=self.digest,
                seconds=data.get("total_duration", 0) / 1e9,
                input_tokens=data.get("prompt_eval_count"),
                output_tokens=data.get("eval_count"),
            ),
        )
        return result


def obj(**properties):
    return dict(
        type="object",
        properties=properties,
        required=list(properties),
        additionalProperties=False,
    )


def array(item):
    return dict(type="array", items=item)


TEXT = {"type": "string"}
NUMBER = {"type": "number"}
BOOL = {"type": "boolean"}
