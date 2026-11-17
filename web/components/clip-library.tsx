import { Check, Download, ScanSearch } from "lucide-react"
import { Button } from "@/components/ui/button"
import { NativeSelect } from "@/components/ui/native-select"
import { clock, clipName, type Clip, type Suggestion } from "@/lib/film"

type Props = {
  clips: Clip[]
  active: string
  names: string[]
  player: string
  busy: boolean
  choose: (c: Clip) => void
  filter: (s: string) => void
  search: () => void
  searching: boolean
  hits: Suggestion[]
  inspect: (s: Suggestion) => void
  exportReel: () => void
  exporting: boolean
  download: string
}
export function ClipLibrary(p: Props) {
  const clips = p.clips
    .filter((c) => !p.player || c.tags.some((t) => t.name === p.player))
    .toSorted((a, b) => a.start - b.start)
  const kept = clips.filter((c) => c.keep)
  const touches = clips.flatMap((c) =>
    c.tags.filter((t) => t.name === p.player && t.skill !== "Appearance"),
  )
  const graded = touches.filter((t) => t.result !== "Ungraded")
  const counts = new Map<string, number>()
  for (const t of touches) counts.set(t.skill, (counts.get(t.skill) || 0) + 1)
  return (
    <aside>
      <section className="rail">
        <div className="rail-head">
          <div className="section-title">
            <h2>Clip library</h2>
            <span className="count">{clips.length}</span>
          </div>
          <NativeSelect
            aria-label="Filter by player"
            disabled={p.busy}
            value={p.player}
            onChange={(e) => p.filter(e.target.value)}
          >
            <option value="">All players</option>
            {p.names.map((n) => (
              <option key={n}>{n}</option>
            ))}
          </NativeSelect>
        </div>
        <div className="queue">
          {clips.map((c) => (
            <button
              type="button"
              key={c.id}
              className="clip-row"
              disabled={p.busy}
              aria-current={p.active === c.id}
              onClick={() => p.choose(c)}
            >
              <img
                src={"/thumb/" + c.id + ".jpg?v=" + c.start + "-" + c.end}
                alt=""
                loading="lazy"
              />
              <span>
                <strong>{clipName(c)}</strong>
                <small>
                  {clock(c.start)} – {clock(c.end)}
                </small>
              </span>
              {c.keep && <Check aria-label="Kept in reel" size={16} />}
            </button>
          ))}
        </div>
      </section>
      <section className="reel">
        <h2>{p.player ? p.player + "’s reel" : "Team reel"}</h2>
        <p>
          {kept.length} kept ·{" "}
          {Math.round(kept.reduce((n, c) => n + c.end - c.start, 0))}s
        </p>
        {p.player && (
          <>
            <p>
              {[...counts]
                .map(([skill, n]) => n + " " + skill.toLowerCase())
                .join(" · ") || "No touches labeled"}
              {graded.length > 0 &&
                " · " +
                  graded.filter((t) => t.result === "Positive").length +
                  "/" +
                  graded.length +
                  " graded positive"}
            </p>
            <Button
              variant="outline"
              disabled={p.busy || p.searching}
              onClick={p.search}
            >
              <ScanSearch />
              {p.searching ? "Finding appearances…" : "Find appearances"}
            </Button>
            {p.hits.length > 0 && (
              <div className="chips suggestions">
                {p.hits.map((h) => (
                  <Button
                    size="xs"
                    variant="secondary"
                    disabled={p.busy}
                    onClick={() => p.inspect(h)}
                    key={h.id}
                  >
                    {clock(h.time)}
                  </Button>
                ))}
              </div>
            )}
          </>
        )}
        <div className="buttons">
          <Button
            variant="secondary"
            disabled={p.busy || p.exporting || !kept.length}
            onClick={p.exportReel}
          >
            <Download />
            {p.exporting ? "Rendering…" : "Export reel"}
          </Button>
          {p.download && (
            <a className="download" href={p.download} download>
              Download MP4
            </a>
          )}
        </div>
      </section>
    </aside>
  )
}
