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
- To export one rally, open it, choose **Export clip**, then **Download MP4**. This uses its saved start/end points and original audio, without changing the reel selection.
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

### Rallies and descriptions on devbox

**Rallies** opens the reviewed rally collection. **Best**, **Longest**, and **Match order** sort the available rallies; this is not yet an exhaustive ranking of the entire match. Each rally has a description, live-play duration, review status, and clickable play-by-play moments. Partial rally boundaries are marked for review.

The experimental GPU pipeline runs privately on your devbox through its existing Ollama service on port 11435. It uses `qwen3-vl:8b-instruct` (install it on that service first), a compressed copy of the recording, and your labeled roster. No OpenAI API calls or paid analysis are used. The CLI temporarily switches to your personal Tailscale profile for transfer, then restores the original profile. Inference continues independently on the devbox.

```sh
./scripts/analyze-devbox start matches/<match-directory>
./scripts/analyze-devbox sync matches/<match-directory>
```

The CLI provides the rally-analysis workflow. Thirty-second windows include overlapping context. Each window is cached by its frames, prompt, schema and model digest. Interrupted runs can resume. `--windows 7 19 61` runs a small calibration sample before a full recording. Start/sync logs and structured results live in the match's ignored `analysis/` directory.

Sync fetches **drafts** without changing your clips. Inspect results against the original footage, especially player identity, serve strikes versus tosses, and rally endings. The initial Gemma and Qwen thinking-model trials did not meet this standard. See `tests/fixtures/video-audit.json` for the visual benchmark. A successful API response is not proof that a label is correct.

After checking the draft quality, publish the results explicitly:

```sh
./scripts/analyze-devbox publish matches/<match-directory>
```

Publishing preserves manual prose, player tags, keep/dismiss decisions and edits made during a scan. It adds rally clips and fills machine-generated or empty descriptions. Cached reruns do not duplicate rallies. Generated descriptions remain labeled as AI descriptions; they do **not** verify individual touches.

### Player touches and coaching

Automatic touch candidates appear on player pages and in kept reels by default. They are labeled **Unverified touch** until checked. Explicit dismissals stay hidden; Undo restores them. Appearance-only tags still do not count as player clips.

**Verify touches** packages short, 15-fps excerpts from the original preview and sends them to your private devbox. The model examines an 8-fps sequence cropped around the candidate, full-court context, and your labeled player reference, beginning with known positive and negative examples. If calibration fails, no candidate judgments are published. Successful checks run for all candidates, with Ishan first. **Sync checks** imports partial results without changing your player tags, keep decisions, confirmations or dismissals. GPU judgments appear as likely, uncertain or unlikely; all candidates remain visible for you to correct.

```sh
./scripts/analyze-devbox contacts matches/<match-directory>
./scripts/analyze-devbox sync-contacts matches/<match-directory>
```

The November 14 recording includes four visually reviewed calibration examples. For another recording, add equivalent `contactBenchmark` examples (contact and no-contact) to its match data before running verification. Calibration checks both contact attribution and action type. The current Qwen model has failed wrong-player and pass-versus-serve checks; full-match GPU verification remains experimental. The check is cached per model, prompt and frames. Unknown identities remain uncertain. Model judgments are not verified match statistics. Results and progress live under the match’s ignored `verification/` directory.

The experimental contact scan can still be run with `uv run --locked scan_touches.py matches/<match-directory>`. It uses the MIT-licensed [RAVEL models](https://github.com/asigatchov/fast-volleyball-tracking-inference/tree/c3864156a4dfbd5af3f00f427ab0fc4bfe7af5b5), ball tracking and clothing references. Ball proximity alone does not prove contact, and identity similarity is not a calibrated probability. Model weights and minute results are cached locally. This scan is a candidate generator, not a source of verified statistics.

**Next practice** on a player page contains evidence-linked feedback. Each note includes an observation, a concrete practice cue, an optional drill and clickable supporting clips. Feedback stays specific to the observed play. The current notes were visually reviewed; automatic coaching across the whole match is still unfinished.

The coaching goal is to identify repeatable strengths and improvement opportunities from actual play: serve recovery, ready position, footwork, passing platform, approach and net timing, and decisions where the camera provides enough context. Feedback must explain what was visible and what to try next. Match-wide patterns need multiple examples; outcomes hidden by the camera, unsupported touch counts and invented performance grades are excluded.

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
