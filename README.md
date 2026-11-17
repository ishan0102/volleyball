# Volleyball

A local film room for phone recordings. Review a full match, label players and touches, and cut team or personal highlight reels with the original audio.

## Run

Install Python 3.11+, uv, Node.js 22+, and Bun. From the checkout:

```sh
./scripts/review "/path/to/match.mov"
```

With no path, the script opens the newest video in `~/Documents/personal/volleyball`. It installs the locked dependencies and starts the Next.js app at [localhost:8731](http://localhost:8731), with hot reload. A Python service handles video and annotations on port 8732. The first run for a match creates a seekable preview and proposes clips from motion and sound. Later runs reuse that work.

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

### Find touches across the recording

Choose **Find touches** in the film room. The scan runs locally in the background, shows progress, and refreshes the library when finished. It covers the entire prepared recording, matches contacts to the roster using your existing player references, and includes detected clips in player pages and reels by default.

Use **Uncertain touches** to prioritize lower-confidence contact or identity matches. **Dismiss** removes a detection from normal browsing, player counts, and exports; **Undo** restores it immediately. The **Dismissed touches** filter keeps all decisions recoverable after a refresh. In the viewer, **Contact** jumps to the predicted contact, **Looks right** confirms it, and the existing tag editor changes the player or touch type. Rerunning the scan preserves edits, confirmations, and dismissals.

For a new recording, label the roster and run the player scan first. To run touch detection from a terminal:

```sh
uv run --locked scan_touches.py matches/<match-directory>
```

The first pass downloads checksum-pinned model weights. Completed minutes are cached; interrupted runs resume them. Three workers are the default; use `--workers 1` to reduce CPU use. `--threshold 0.5` is the default contact threshold. Lowering it admits more candidates, but independent ball-motion validation still applies. The scan is local and does not upload footage.

The detector uses the MIT-licensed [RAVEL-VB-013 contact model and VballNetFastV1 ball tracker](https://github.com/asigatchov/fast-volleyball-tracking-inference/tree/c3864156a4dfbd5af3f00f427ab0fc4bfe7af5b5). A temporal contact prediction must also have a moving ball near the predicted player in the independent tracker. Existing OpenVINO player embeddings and clothing references assign the identity. OpenVINO inference for the contact model must use full precision on this Mac; reduced precision suppresses player proposals. License: `models/RAVEL-LICENSE`.

Automatic events are labeled **Touch**, because the model detects contact but does not reliably distinguish serve, pass, set, attack, block, or dig. Confidence flags are ranking signals, not calibrated accuracy percentages. Occlusion, distant players, balls held between points, and similar clothing can still cause misses or false matches. Original manual touch labels and descriptions are preserved. Overlapping clips are merged when exporting a reel so the same footage is not repeated.

### Appearance model

For clothing suggestions on a new checkout, install the OpenCV Zoo YOLOX weights:

```sh
curl -fL https://huggingface.co/opencv/object_detection_yolox/resolve/main/object_detection_yolox_2022nov.onnx -o models/yolox.onnx
```

The detector checks the model's SHA-256 before use. Match files, video exports, weights, and installed dependencies are ignored by Git. The model license is in `models/LICENSE`.

### Development

Run `./scripts/review` for development. It starts `next dev` with Fast Refresh and the Python video API together; edits under `web/` appear without rebuilding or restarting. Next.js proxies media and annotation requests to the Python service, so the browser always uses `http://localhost:8731`. Both services bind only to the local computer. Ctrl+C stops them. Restart the script after editing Python code.

The frontend uses shadcn/ui and Tailwind. Run `bun run typecheck` or `bun run build` inside `web/` for validation. To run a production build, start `uv run volleyball.py` in one terminal and `bun run build && bun run start` inside `web/` in another.

### Play descriptions and player clips

Player filters, sidebar counts, and player reel exports include only clips with a labeled Touch, Serve, Pass, Set, Attack, Block, or Dig by that player. Appearance matches help identify people during review and do not qualify a clip for their reel. All clips remains the full library.

Clips have a short title (`note`) and an optional `description`. Summaries appear on cards, in the viewer, and in search. Edit clip details to describe what happened; keep uncertain outcomes explicit. Selecting a touch is required for new tags, with a separate Appearance only option for identity labels.
