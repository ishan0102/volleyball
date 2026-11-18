import { Bookmark, Play, SearchX, X, Undo2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  clock,
  clipName,
  contactLabel,
  isRally,
  rallyDuration,
  clipDescription,
  type Clip,
} from "@/lib/film"

export function labeling(clip: Clip) {
  if (isRally(clip))
    return clip.analysis?.status === "reviewed"
      ? "Rally reviewed"
      : "AI-described rally"
  if (clip.analysis?.kind === "between_points") return "Between points"
  if (clip.detection) return contactLabel(clip)
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
  review,
  scanning,
}: {
  clips: Clip[]
  layout: "grid" | "list"
  choose: (clip: Clip) => void
  keep: (clip: Clip) => void
  busy: boolean
  reset: () => void
  player?: string
  scanning?: boolean
  review: (clip: Clip, status: "dismissed" | "automatic") => void
}) {
  if (!clips.length)
    return (
      <div className="empty-state">
        <SearchX size={28} />
        <h2>
          {scanning
            ? "Analyzing footage"
            : player
              ? "No matching touch clips"
              : "No clips match"}
        </h2>
        <p>
          {scanning
            ? "Analysis is running."
            : player
              ? "Clear filters or tag a touch in All clips."
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
              <span className="duration">
                {Math.round(rallyDuration(c))}s{isRally(c) ? " rally" : ""}
              </span>
            </div>
            <div className="clip-copy">
              <div className="clip-time">
                {clock(c.start)} – {clock(c.end)}
              </div>
              {isRally(c) && (
                <div className="rally-kicker">
                  Rally {c.analysis?.number}
                  {!c.analysis?.complete ? " · partial view" : ""}
                </div>
              )}
              <h2>{clipName(c)}</h2>
              {clipDescription(c) && (
                <p className="clip-description">{clipDescription(c)}</p>
              )}
              <div
                className={"label-state " + (!c.tags.length ? "untagged" : "")}
              >
                <span className="state-dot" />
                {labeling(c)}
              </div>
            </div>
          </button>
          {c.detection && (
            <button
              className="dismiss-touch"
              disabled={busy}
              aria-label={
                (c.detection.status === "dismissed"
                  ? "Restore touch"
                  : "Dismiss touch") +
                " at " +
                clock(c.detection.time)
              }
              onClick={() =>
                review(
                  c,
                  c.detection!.status === "dismissed"
                    ? "automatic"
                    : "dismissed",
                )
              }
            >
              {c.detection.status === "dismissed" ? (
                <Undo2 size={14} />
              ) : (
                <X size={14} />
              )}
              {c.detection.status === "dismissed" ? "Restore" : "Dismiss"}
            </button>
          )}
          {c.detection?.status !== "dismissed" && (
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
          )}
        </article>
      ))}
    </div>
  )
}
