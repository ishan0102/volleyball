import { Bookmark, Play, SearchX } from "lucide-react"
import { Button } from "@/components/ui/button"
import { clock, clipName, type Clip } from "@/lib/film"

export function labeling(clip: Clip) {
  if (!clip.tags.length) return "No player tags"
  if (clip.tags.some((t) => t.skill !== "Appearance")) return "Touch labeled"
  if (clip.tags.some((t) => t.source !== "automatic")) return "Player confirmed"
  return "Auto-tagged"
}

export function ClipLibrary({
  clips,
  layout,
  choose,
  keep,
  busy,
  reset,
  player,
}: {
  clips: Clip[]
  layout: "grid" | "list"
  choose: (clip: Clip) => void
  keep: (clip: Clip) => void
  busy: boolean
  reset: () => void
  player?: string
}) {
  if (!clips.length)
    return (
      <div className="empty-state">
        <SearchX size={28} />
        <h2>{player ? "No matching touch clips" : "No clips match"}</h2>
        <p>
          {player
            ? "Only labeled ball contacts appear here. Review the footage in All clips to add a touch, or clear your filters."
            : "Try another player, label status, or search."}
        </p>
        <Button variant="outline" onClick={reset}>
          Clear filters
        </Button>
      </div>
    )
  return (
    <div className={"clip-collection " + layout}>
      {clips.map((c) => (
        <article className="clip-card" key={c.id}>
          <button
            className="clip-open"
            onClick={() => choose(c)}
            aria-label={"Watch " + clipName(c) + " at " + clock(c.start)}
          >
            <div className="clip-image">
              <img
                src={"/thumb/" + c.id + ".jpg?v=" + c.start + "-" + c.end}
                alt=""
                loading="lazy"
                width={480}
                height={270}
              />
              <span className="play-overlay">
                <Play size={24} fill="currentColor" />
              </span>
              <span className="duration">{Math.round(c.end - c.start)}s</span>
            </div>
            <div className="clip-copy">
              <div className="clip-time">
                {clock(c.start)} – {clock(c.end)}
              </div>
              <h2>{clipName(c)}</h2>
              {c.description && (
                <p className="clip-description">{c.description}</p>
              )}
              <div
                className={"label-state " + (!c.tags.length ? "untagged" : "")}
              >
                <span className="state-dot" />
                {labeling(c)}
              </div>
            </div>
          </button>
          <button
            className="keep-button"
            aria-label={
              (c.keep ? "Remove from" : "Keep in") +
              " reel at " +
              clock(c.start)
            }
            aria-pressed={c.keep}
            disabled={busy}
            onClick={() => keep(c)}
          >
            <Bookmark size={16} fill={c.keep ? "currentColor" : "none"} />
          </button>
        </article>
      ))}
    </div>
  )
}
