# Volleyball

A local film room for phone recordings. Review a full match, label players and touches, and cut team or personal highlight reels with the original audio.

## Run

Install Python 3.11+, uv, Node.js 22+, and Bun. From the checkout:

```sh
./scripts/review "/path/to/match.mov"
```

With no path, the script opens the newest video in `~/Documents/personal/volleyball`. It installs the locked dependencies, builds the Next.js interface, and starts the Python video server on localhost. The first run for a match creates a seekable preview and proposes clips from motion and sound. Later runs reuse that work.

## Review

- Browse clips by player, search by name, touch, or time, and use label-status filters to find untagged footage. Choose a grid or list and sort by match order, newest, or duration. Filters and the open clip are saved in the URL.
- Open a clip to watch it. Use previous/next, the clip timeline, and **Replay clip** to review a moment. **Full recording** allows playback beyond the clip.
- Pause and choose **Tag player**, then click the player’s shirt and save their name, touch, and outcome. Existing tags can be edited from the clip details. Unsaved tags survive a refresh.
- Keep clips with the bookmark button, browse **Reel**, and use **Export reel** to render the selected player’s kept clips or the team reel from the original movie.
- **Review matches** shows the full frame, the original player reference, and a proposed match. Confirm or change the name, dismiss, skip, or undo the last decision. Keyboard shortcuts are shown beside their actions.
- The interface follows the [personal design guidelines](https://linear.app/ishan0102/document/personal-design-guidelines-2a1e6acfd1be).

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

### Play descriptions and player clips

Player filters, sidebar counts, and player reel exports include only clips with a labeled Serve, Pass, Set, Attack, Block, or Dig by that player. Appearance matches help identify people during review and do not qualify a clip for their reel. All clips remains the full library.

Clips have a short title (`note`) and an optional `description`. Summaries appear on cards, in the viewer, and in search. Edit clip details to describe what happened; keep uncertain outcomes explicit. Selecting a touch is required for new tags, with a separate Appearance only option for identity labels.
