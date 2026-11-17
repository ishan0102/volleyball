# Volleyball

A local film room for phone recordings. Review a full match, label players and touches, and cut team or personal highlight reels with the original audio.

## Run

Install Python 3.11+, uv, Node.js 22+, and Bun. From the checkout:

```sh
./scripts/review "/path/to/match.mov"
```

With no path, the script opens the newest video in `~/Documents/personal/volleyball`. It installs the locked dependencies, builds the Next.js interface, and starts the Python video server on localhost. The first run for a match creates a seekable preview and proposes clips from motion and sound. Later runs reuse that work.

## Review

- Play or scrub to any frame. Click a player's shirt, choose or enter a name, and press **Save tag**. Enter also saves. Repeat on the same frame for another player. If the frame falls outside the clip library, saving creates a clip around it.
- Choose a clip to review its labels. Set its start or end to the playhead, edit the title, or keep it in the reel. Filter by player to see their clips, labeled touches, and graded outcomes.
- **Find appearances** compares clothing in two sample frames per candidate. Review each suggestion before saving it as a label. Counts come from the touches you label.
- Use **Export reel** for the current player or the whole team. Python renders kept clips from the original movie. Keep the source movie and the local `matches/` directory to reopen the edit.

### Scan the whole match

Pin each roster player in a clear frame, then run the full-match scan from the checkout. Pass the prepared directory inside `matches/`.

```sh
uv run --with 'openvino==2026.4.1' scan_players.py matches/<match-directory>
```

The first scan downloads Intel’s Open Model Zoo person-reidentification-retail-0288 weights, verifies their checksums, and caches local crops and embeddings. The scan samples once per second, combines whole-body similarity with shirt and shorts colors, and requires agreement across adjacent samples. It saves at most one representative appearance per player per 45-second window. A clear match adds an ungraded appearance tag. Weaker matches appear under **Review player matches**, where you can compare the two crops, watch the surrounding footage, choose a different player, or dismiss the match. Add another manual pin or confirm a review to give the next scan another reference. Repeated scans preserve decisions and reuse cached detections. Reels still use the clips you mark to keep.

### Appearance model

For clothing suggestions on a new checkout, install the OpenCV Zoo YOLOX weights:

```sh
curl -fL https://huggingface.co/opencv/object_detection_yolox/resolve/main/object_detection_yolox_2022nov.onnx -o models/yolox.onnx
```

The detector checks the model's SHA-256 before use. Match files, video exports, weights, and installed dependencies are ignored by Git. The model license is in `models/LICENSE`.

### Development

The frontend is a Next.js static export using shadcn/ui and Tailwind. Run `bun run typecheck` or `bun run build` inside `web/`. The Python server serves the compiled frontend, range requests for video scrubbing, and the annotation and export APIs. Stop the server with Ctrl+C.
