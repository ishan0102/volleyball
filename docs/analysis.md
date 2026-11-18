# Optional analysis

The app works without these pipelines. Treat their output as candidates to review against the footage.

## Player appearances and touch candidates

For clothing-based player suggestions, download the OpenCV Zoo YOLOX model:

```sh
curl -fL https://huggingface.co/opencv/object_detection_yolox/resolve/main/object_detection_yolox_2022nov.onnx -o models/yolox.onnx
```

The loader verifies its SHA-256. Pin each player in a clear frame, then scan the prepared directory printed by the review script:

```sh
uv run --locked scan_players.py matches/<match-directory>
uv run --locked scan_touches.py matches/<match-directory>
```

The appearance scan uses Open Model Zoo person-reidentification-retail-0288, clothing colors, and agreement across neighboring samples. Its weights are downloaded and checked automatically. Review uncertain identities under **Review players**. Manual corrections become references for later scans.

The touch scanner uses the [RAVEL models](https://github.com/asigatchov/fast-volleyball-tracking-inference/tree/c3864156a4dfbd5af3f00f427ab0fc4bfe7af5b5), ball tracking, and clothing references. Ball proximity alone does not prove contact. Its cached predictions remain candidates, even when the model is confident.

## Private GPU server

Configure an SSH alias named `devbox`, or pass `--host your-host` to the commands below. The remote machine needs Python 3, ffmpeg with the drawtext filter, and Ollama serving `qwen3-vl:8b-instruct` on `http://127.0.0.1:11435`. Local transfer uses `ssh`, `scp`, and `rsync`. The film-room buttons use the `devbox` alias.

On the GPU server, start a dedicated Ollama instance and install the model:

```sh
OLLAMA_HOST=127.0.0.1:11435 ollama serve
# In another terminal:
OLLAMA_HOST=127.0.0.1:11435 ollama pull qwen3-vl:8b-instruct
```

If an appropriate instance already runs there, reuse it. The scripts do not manage the server or download Ollama. They place workers and private match files in `~/.local/share/volleyball` on the remote host.

On macOS, optional Tailscale profile switching can be enabled with `VOLLEYBALL_TAILNET` or an ignored `config.local.json`:

```json
{"tailnet": "your-profile-name"}
```

Without that setting, the current network is used. When switching is enabled, the original profile is restored after transfer; inference continues remotely.

## Rally descriptions

```sh
./scripts/analyze-devbox start matches/<match-directory>
./scripts/analyze-devbox sync matches/<match-directory>
```

Use `--windows 0 1 2` with `start` for an initial sample. Thirty-second windows include overlapping context; results are cached by frames, prompt, schema, and model digest. Sync fetches drafts without changing the library.

Inspect cached results against the footage before publishing:

```sh
./scripts/analyze-devbox publish matches/<match-directory>
```

Publishing adds rally clips and fills generated or empty descriptions while preserving manual prose, player tags, and keep/dismiss decisions. AI descriptions do not verify individual touches.

## Contact verification

First add reviewed examples to the recording's ignored `match.json` under `contactBenchmark`. Include real contacts, wrong-player negatives, and expected action types. Times are seconds into the original recording; boxes are normalized `[x, y, width, height]`.

```json
{
  "contactBenchmark": [
    {"id": "known-serve", "name": "Player A", "time": 12.5, "box": [0.1, 0.3, 0.2, 0.5], "expected": "supported", "expectedSkills": ["Serve"]},
    {"id": "other-player", "name": "Player A", "time": 25.0, "box": [0.1, 0.3, 0.2, 0.5], "expected": "rejected"}
  ],
  "focusPlayer": "Player A",
  "identityHints": {"Player A": "Plain white shirt, black shorts, no knee pads."}
}
```

These are illustrative values; replace them with reviewed examples from your recording. Player reference photos come from your tags. `focusPlayer` optionally prioritizes one person's candidates; `identityHints` supplies clothing notes privately.

```sh
./scripts/analyze-devbox contacts matches/<match-directory>
./scripts/analyze-devbox sync-contacts matches/<match-directory>
```

**Verify touches** and **Sync checks** in the app run the same commands. Verification uses short 15-fps excerpts, an 8-fps crop around the candidate, full-court context, and labeled references. Failed calibration stops the run without publishing judgments. Successful checks can be synced incrementally, but all candidates remain visible regardless of the GPU verdict.

Results live in the ignored `verification/` directory. New recordings need their own calibration examples. The current model has failed wrong-player and pass-versus-serve examples; this remains a research workflow, not reliable automatic match analysis.
