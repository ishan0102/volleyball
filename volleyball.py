"""Run with uv run volleyball.py MATCH.mov"""

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import fcntl
from pathlib import Path
import re
import threading
from urllib.parse import unquote
from uuid import uuid4

from media import ff, clip, export, make_preview, prepare, save


from tags import numeric, validated_tag, save_tag, SKILLS, RESULTS


def update(state, data):
    if data["revision"] != state["revision"]:
        raise ValueError("Another tab saved changes. Refresh before editing.")
    start = numeric(data["start"], 0, state["duration"])
    end = numeric(data["end"], start + 0.1, state["duration"])
    item = next((c for c in state["clips"] if c["id"] == data["id"]), None)
    if item is None and data["id"] != "new":
        raise ValueError("Unknown clip.")
    tags = [validated_tag(tag, start, end) for tag in data["tags"]]
    if item is None:
        item = clip(start, end)
        item["id"] = uuid4().hex
        state["clips"].append(item)
    item.update(
        start=start,
        end=end,
        tags=tags,
        note=str(data["note"])[:300],
        description=str(data.get("description", item.get("description", "")))[:2000],
        keep=bool(data["keep"]),
    )
    state["revision"] += 1
    return item["id"]


def serve(folder, port, open_browser=False):
    manifest = folder / "match.json"
    lock = threading.Lock()

    def view(state):
        return {
            **{k: v for k, v in state.items() if k != "source"},
            "title": Path(state["source"]).stem,
            "match_id": folder.name,
            "skills": SKILLS,
            "results": RESULTS,
        }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, obj, status=200):
            body = json.dumps(obj).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def file(self, path, mime):
            size = path.stat().st_size
            begin, end = 0, size - 1
            header = self.headers.get("Range")
            if header:
                m = re.fullmatch(r"bytes=(\d+)-(\d*)", header)
                if not m or int(m[1]) >= size:
                    self.send_error(416)
                    return
                begin = int(m[1])
                end = min(end, int(m[2])) if m[2] else end
                if end < begin:
                    self.send_error(416)
                    return
            self.send_response(206 if header else 200)
            self.send_header("Content-Type", mime)
            self.send_header("Accept-Ranges", "bytes")
            if header:
                self.send_header("Content-Range", f"bytes {begin}-{end}/{size}")
            self.send_header("Content-Length", str(end - begin + 1))
            if path.parent.name == "exports":
                self.send_header(
                    "Content-Disposition", f'attachment; filename="{path.name}"'
                )
            self.end_headers()
            try:
                with path.open("rb") as stream:
                    stream.seek(begin)
                    left = end - begin + 1
                    while left:
                        block = stream.read(min(262144, left))
                        if not block:
                            break
                        self.wfile.write(block)
                        left -= len(block)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            if self.headers.get("Host", "") not in (
                f"127.0.0.1:{self.server.server_port}",
                f"localhost:{self.server.server_port}",
            ):
                return self.reply({"error": "Local requests only."}, 403)
            route = unquote(self.path.split("?")[0])
            if route in ("/", "/review", "/review/"):
                self.send_response(302)
                self.send_header("Location", "http://localhost:8731" + route)
                self.end_headers()
                return
            crop = re.fullmatch(r"/scan-crop/([0-9]{9,}-[0-9]+\.jpg)", route)
            if crop:
                path = folder / "appearance-scan" / "crops" / crop[1]
                if path.is_file():
                    return self.file(path, "image/jpeg")
                return self.send_error(404)
            if route == "/preview.mp4":
                return self.file(folder / "preview.mp4", "video/mp4")
            thumb = re.fullmatch(r"/thumb/([a-zA-Z0-9_-]+)\.jpg", route)
            if thumb:
                state = json.loads(manifest.read_text())
                item = next((c for c in state["clips"] if c["id"] == thumb[1]), None)
                if item:
                    cache = folder / "thumbs"
                    cache.mkdir(exist_ok=True)
                    midpoint = (item["start"] + item["end"]) / 2
                    target = cache / f"{item['id']}-{midpoint:.2f}-480.jpg"
                    if not target.exists():
                        try:
                            image = ff(
                                [
                                    "-ss",
                                    midpoint,
                                    "-i",
                                    folder / "preview.mp4",
                                    "-frames:v",
                                    "1",
                                    "-vf",
                                    "scale=480:-2",
                                    "-f",
                                    "image2pipe",
                                    "-c:v",
                                    "mjpeg",
                                    "-",
                                ]
                            )
                            tmp = cache / uuid4().hex
                            tmp.write_bytes(image)
                            tmp.replace(target)
                        except Exception:
                            self.send_error(500)
                            return
                    return self.file(target, "image/jpeg")
            if route == "/match":
                state = json.loads(manifest.read_text())
                return self.reply(view(state))
            if re.fullmatch(r"/exports/[a-zA-Z0-9_-]+\.mp4", route):
                path = folder / route[1:]
                if path.is_file():
                    return self.file(path, "video/mp4")
            self.send_error(404)

        def do_POST(self):
            try:
                origin = self.headers.get("Origin")
                host = self.headers.get("Host", "")
                if host not in (
                    f"localhost:{self.server.server_port}",
                    f"127.0.0.1:{self.server.server_port}",
                ) or (
                    origin
                    and origin
                    not in (
                        f"http://{host}",
                        "http://localhost:8731",
                        "http://127.0.0.1:8731",
                    )
                ):
                    return self.reply({"error": "Local requests only."}, 403)
                if self.headers.get_content_type() != "application/json":
                    return self.reply({"error": "Expected JSON."}, 415)
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 256000:
                    raise ValueError("Invalid request size.")
                data = json.loads(self.rfile.read(size))
                if self.path in ("/save", "/tag", "/review-appearance", "/undo-review"):
                    with lock, (folder / ".edit.lock").open("a") as gate:
                        fcntl.flock(gate, fcntl.LOCK_EX)
                        state = json.loads(manifest.read_text())
                        if self.path == "/review-appearance":
                            from scan_players import decide

                            decide(state, data)
                            key = data["id"]
                        elif self.path == "/undo-review":
                            from scan_players import undo_review

                            undo_review(state, data)
                            key = data["id"]
                        elif self.path == "/tag":
                            key = save_tag(state, data)
                        else:
                            key = update(state, data)
                        save(manifest, state)
                    return self.reply({"id": key, "match": view(state)})
                if self.path == "/suggest":
                    from players import suggest

                    state = json.loads(manifest.read_text())
                    return self.reply(
                        {"hits": suggest(folder, state, str(data["player"]))}
                    )
                if self.path == "/export":
                    state = json.loads(manifest.read_text())
                    player = str(data.get("player", "")).strip()
                    slug = (
                        re.sub(r"[^a-zA-Z0-9_-]+", "-", player).strip("-")[:40]
                        or "team"
                    )
                    name = f"{slug}-r{state['revision']}-{hashlib.sha256(player.encode()).hexdigest()[:6]}.mp4"
                    target = folder / "exports" / name
                    target.parent.mkdir(exist_ok=True)
                    if not target.exists():
                        export(state, player, target)
                    return self.reply({"url": "/exports/" + name})
                self.send_error(404)
            except (ValueError, KeyError, TypeError, OSError, RuntimeError) as err:
                self.reply({"error": str(err)}, 400)
            except Exception:
                self.reply(
                    {
                        "error": "Video export failed. Check the source movie and available disk space."
                    },
                    500,
                )

    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as err:
        import errno

        if err.errno != errno.EADDRINUSE:
            raise
        raise RuntimeError(
            f"Port {port} is already in use. Stop the existing film room before starting another match."
        ) from err
    print(f"Video API: http://localhost:{server.server_port} • {folder}", flush=True)
    if open_browser:
        import webbrowser

        webbrowser.open("http://localhost:8731")
    server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Prepare a match and open its local film room."
    )
    parser.add_argument("movie", type=Path, nargs="?")
    parser.add_argument(
        "--open", action="store_true", help="Open the film room in your browser"
    )
    parser.add_argument(
        "--library", type=Path, default=Path(__file__).resolve().parent / "matches"
    )
    parser.add_argument("--port", type=int, default=8732)
    args = parser.parse_args()
    if args.movie is None:
        inbox = Path.home() / "Documents" / "personal" / "volleyball"
        movies = [
            p
            for p in inbox.glob("*")
            if p.is_file()
            and p.suffix.lower() in {".mov", ".mp4", ".m4v"}
            and p.stat().st_size
        ]
        if not movies:
            parser.error(
                "Pass a movie path or add a recording to ~/Documents/personal/volleyball"
            )
        args.movie = max(movies, key=lambda p: p.stat().st_mtime_ns)

    args.library.mkdir(parents=True, exist_ok=True)
    with (args.library / ".prepare.lock").open("a") as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        folder = prepare(args.movie, args.library)
        state = json.loads((folder / "match.json").read_text())
        make_preview(args.movie, folder, state["hdr"])
    serve(folder, args.port, args.open)
