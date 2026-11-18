# Volleyball

A local film room for turning phone footage into player clips and rally highlights. Built with Python, Next.js, TypeScript, shadcn/ui, and Tailwind CSS.

Browse a recording, tag players, trim a rally, and export a single clip or a highlight reel with the original audio. Recordings and match data stay on your machine. The optional GPU workflow sends excerpts only to a server you configure.

## Run

Requires macOS or Linux, Python 3.11+, [uv](https://docs.astral.sh/uv/), Node.js 22+, and [Bun](https://bun.sh/).

```sh
git clone https://github.com/ishan0102/volleyball.git
cd volleyball
./scripts/review "/path/to/match.mov"
```

Open [localhost:8731](http://localhost:8731). The script installs locked dependencies, prepares a seekable preview, and starts Next.js with hot reload alongside the Python video API. The first import takes longer; subsequent runs reuse the preview and annotations. Ctrl+C stops both services.

With no argument, the script uses the newest recording in `~/Documents/personal/volleyball`.

## Review and export

- **Tag players:** pause a clip, choose **Tag player**, click the player, and add their name and action. Use **Appearance only** for an identity reference without a ball contact.
- **Review clips:** search and filter by player, inspect suggested matches, correct tags, and dismiss or undo uncertain touch candidates.
- **Trim a rally:** open **Edit clip details**, set the start and end at the playhead, and save.
- **Export one clip:** open it → **Export clip** → **Download MP4**. This uses the saved boundaries without changing your reel selection.
- **Make a reel:** bookmark clips, choose a player or the team collection, then **Export reel**. Overlapping clips are merged so the same footage is not repeated.

Player libraries include labeled contacts and automatic candidates. Appearance-only tags do not qualify. Candidates stay visible until explicitly dismissed; they are not verified statistics.

## What works, and what is experimental

The film room, manual tagging, clip trimming, review controls, and exports are ready for personal use. Rallies can have descriptions, timestamped moments, and evidence-linked practice notes. **Best** and **Longest** sort the rallies already in the library.

Automatic player matching, touch detection, rally descriptions, and coaching are experiments. Phone footage, overlapping players, and similar clothing make contact attribution difficult. The tested vision models still confuse players and actions. GPU checks must pass reviewed examples before their judgments can be imported; they never overwrite manual identities or dismiss clips. Automatic coaching across a whole match is unfinished.

See [analysis setup](docs/analysis.md) for optional local CV models and private GPU processing. None of these are needed to review and export clips manually.

## Private data

`matches/` contains previews, player annotations, reference crops, analysis results, and exports. It is ignored by Git, along with recordings, image files, downloaded model weights, `.env` files, and `config.local.json`. No match footage or player dataset is included in this repository.

Both services bind to the local computer. There are no OpenAI API calls or paid analysis requests. Using the optional GPU commands transfers video excerpts and player references to your configured SSH host; it is not required for the local film room. A custom library outside `matches/` is your responsibility to keep out of version control.

## Development

```sh
uv sync --locked
uv run --locked python -m unittest discover -s tests -q
bun install --cwd web --frozen-lockfile
bun run --cwd web typecheck
bun run --cwd web build
```

Use `./scripts/review` for development. Frontend edits hot reload; restart after Python changes. The browser uses port 8731 and Next.js proxies media and annotation requests to the local API on port 8732.

## License

Project code is [MIT licensed](LICENSE). Third-party models retain their own licenses: [OpenCV/Open Model Zoo](models/LICENSE) and [RAVEL](models/RAVEL-LICENSE). Model weights are downloaded separately.
