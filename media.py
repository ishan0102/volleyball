"""Local match analysis and reel export."""

import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg
import numpy as np

FF = imageio_ffmpeg.get_ffmpeg_exe()


def ff(args):
    return subprocess.check_output(
        [FF, "-nostdin", "-loglevel", "error", "-y", *map(str, args)]
    )


def inspect(source):
    info = subprocess.run(
        [FF, "-hide_banner", "-i", str(source)], capture_output=True, text=True
    ).stderr
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", info)
    if not m or "Video:" not in info:
        raise ValueError("Could not read a video track and duration.")
    return (
        int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]),
        "Audio:" in info,
        "arib-std-b67" in info or "smpte2084" in info,
    )


def display_filter(width, hdr):
    filters = [f"scale='min({width},iw)':-2"]
    if hdr:
        filters += [
            "zscale=t=linear:npl=100",
            "format=gbrpf32le",
            "zscale=p=bt709",
            "tonemap=tonemap=mobius",
            "zscale=t=bt709:m=bt709:r=tv",
        ]
    return ",".join(filters + ["format=yuv420p"])


def save(path, obj):
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as tmp:
        json.dump(obj, tmp, indent=2, allow_nan=False)
    Path(tmp.name).replace(path)


def make_preview(src, folder, hdr):
    target = folder / "preview.mp4"
    if target.exists():
        return
    tmp = folder / "preview.partial.mp4"
    ff(
        [
            "-i",
            src,
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-vf",
            "fps=15," + display_filter(960, hdr),
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "24",
            "-g",
            "30",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-map_metadata",
            "-1",
            "-movflags",
            "+faststart",
            tmp,
        ]
    )
    tmp.replace(target)


def normalize(series):
    lo, hi = np.percentile(series, [10, 90])
    return np.clip((series - lo) / max(hi - lo, 1e-6), 0, 2)


def candidates(src, duration, audio):
    # Keyframes keep the hour-long scan inexpensive; sample the court below the ceiling.
    data = ff(
        [
            "-skip_frame",
            "nokey",
            "-i",
            src,
            "-map",
            "0:v:0",
            "-an",
            "-vf",
            "fps=1,scale=144:80,format=gray",
            "-f",
            "rawvideo",
            "-",
        ]
    )
    frames = np.frombuffer(data, np.uint8).reshape(-1, 80, 144).astype(np.int16)
    if len(frames) < 3:
        short = clip(0, min(duration, 12), 0)
        short["keep"] = True
        return [short]
    delta = np.abs(np.diff(frames[:, 28:76, 5:139], axis=0))
    motion = (delta > 12).mean(axis=(1, 2))
    # Camera bumps and sudden cuts change almost the whole image at once.
    motion[motion > 0.48] = 0
    score = normalize(motion)
    # Downrank people walking right past the lens and persistent views of a wall.
    reference = np.median(frames[:: max(1, len(frames) // 100)], axis=0)
    deviation = (np.abs(frames[1:] - reference) > 38).mean(axis=(1, 2))
    blocked = np.clip((deviation - 0.12) / 0.24, 0, 1)
    if audio:
        pcm = ff(
            ["-i", src, "-map", "0:a:0", "-ac", "1", "-ar", "4000", "-f", "s16le", "-"]
        )
        signal = np.frombuffer(pcm, "<i2")
        chunks = (
            signal[: len(signal) // 4000 * 4000].reshape(-1, 4000).astype(np.float32)
        )
        if len(chunks):
            rms = np.sqrt(np.mean(chunks**2, axis=1))
            audio_score = np.zeros_like(score)
            count = min(len(score), len(rms))
            audio_score[:count] = normalize(rms)[:count]
            score += 0.55 * audio_score
    score *= 1 - 0.88 * blocked
    span = min(11, len(score))
    smooth = np.convolve(score, np.ones(span) / span, mode="valid")
    # A few options from each part of the match, separated from each other.
    picks = []
    for group in np.array_split(
        np.arange(len(smooth)), max(1, min(12, int(duration // 130)))
    ):
        if not len(group):
            continue
        for t in group[np.argsort(smooth[group])[::-1]]:
            if all(abs(int(t) - s) >= 22 for s in picks):
                picks.append(int(t))
                if sum(i in range(group[0], group[-1] + 1) for i in picks) >= 3:
                    break
    result = [
        clip(max(0, t - 2), min(duration, t + span + 2), float(smooth[t]))
        for t in sorted(picks)
    ]
    for item in sorted(result, key=lambda c: -c["score"])[:6]:
        item["keep"] = True
    return result


def clip(start, end, score=0):
    return dict(
        id=f"c{int(start * 1000)}",
        start=start,
        end=end,
        score=score,
        keep=False,
        tags=[],
        note="",
    )


def reel_clips(state, player=""):
    return [
        c
        for c in state["clips"]
        if c["keep"]
        and (
            not player
            or any(
                t["name"] == player
                and t.get("skill") in {"Serve", "Pass", "Set", "Attack", "Block", "Dig"}
                for t in c["tags"]
            )
        )
    ]


def export(state, player, target):
    cuts = reel_clips(state, player)
    if not cuts:
        raise ValueError("Keep at least one clip for this reel.")
    with tempfile.TemporaryDirectory(dir=target.parent) as tmp:
        folder = Path(tmp)
        listing = []
        for i, c in enumerate(sorted(cuts, key=lambda c: c["start"])):
            name = f"{i:04}.mp4"
            ff(
                [
                    "-ss",
                    c["start"],
                    "-i",
                    state["source"],
                    "-t",
                    c["end"] - c["start"],
                    "-map",
                    "0:v:0",
                    "-map",
                    "0:a:0?",
                    "-vf",
                    display_filter(1920, state["hdr"]),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "20",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "160k",
                    "-map_metadata",
                    "-1",
                    folder / name,
                ]
            )
            listing.append(f"file '{name}'")
        (folder / "list").write_text("\n".join(listing))
        ff(
            [
                "-f",
                "concat",
                "-safe",
                "1",
                "-i",
                folder / "list",
                "-c",
                "copy",
                "-map_metadata",
                "-1",
                "-movflags",
                "+faststart",
                folder / "reel.mp4",
            ]
        )
        (folder / "reel.mp4").replace(target)
    return len(cuts)


def prepare(source, root):
    src = Path(source).resolve(strict=True)
    fingerprint = f"{src}|{src.stat().st_size}|{src.stat().st_mtime_ns}"
    folder = root / (
        src.stem + "-" + hashlib.sha256(fingerprint.encode()).hexdigest()[:8]
    )
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "match.json"
    if not path.exists():
        duration, audio, hdr = inspect(src)
        print("Finding highlight candidates…", flush=True)
        save(
            path,
            dict(
                source=str(src),
                duration=duration,
                hdr=hdr,
                revision=0,
                clips=candidates(src, duration, audio),
            ),
        )
    return folder
