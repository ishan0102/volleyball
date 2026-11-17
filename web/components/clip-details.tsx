import { useState } from "react"
import { Pencil, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { clock, type Clip, type Tag } from "@/lib/film"

type Props = {
  clip: Clip
  busy: boolean
  playhead: () => number
  seek: (time: number) => void
  save: (c: Clip) => Promise<boolean>
  editTag: (tag: Tag) => void
}
export function ClipDetails({
  clip,
  busy,
  playhead,
  seek,
  save,
  editTag,
}: Props) {
  const [details, setDetails] = useState<Clip | null>(null)
  const [error, setError] = useState("")
  const tags = clip.tags
  function trim(side: "start" | "end") {
    if (!details) return
    const updated = { ...details, [side]: playhead() }
    if (
      updated.end - updated.start < 0.1 ||
      tags.some((t) => t.time < updated.start || t.time > updated.end)
    ) {
      setError("Keep both clip boundaries around the saved tags.")
      return
    }
    setError("")
    setDetails(updated)
  }
  return (
    <section className="details">
      <div className="section-title">
        <div>
          <small className="time">
            {clock(clip.start)} – {clock(clip.end)}
          </small>
          <h2>Clip details</h2>
        </div>
        <div className="buttons">
          <Button
            variant={clip.keep ? "secondary" : "outline"}
            size="sm"
            disabled={busy || !!details}
            onClick={() => save({ ...clip, keep: !clip.keep })}
          >
            {clip.keep ? "Kept in reel" : "Keep in reel"}
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Edit clip details"
            disabled={busy}
            onClick={() => {
              setDetails({ ...clip })
              setError("")
            }}
          >
            <Pencil />
          </Button>
        </div>
      </div>
      {!details &&
        (clip.description ? (
          <p className="play-description">{clip.description}</p>
        ) : (
          <p className="hint">
            No play description yet. Edit clip details to add what happened.
          </p>
        ))}
      {details && (
        <div className="clip-edit">
          <label>
            Clip title
            <Input
              value={details.note}
              maxLength={300}
              onChange={(e) => setDetails({ ...details, note: e.target.value })}
            />
          </label>
          <label>
            What happened
            <textarea
              className="description-input"
              value={details.description ?? ""}
              rows={5}
              maxLength={2000}
              placeholder="Describe the touch, what followed, and the outcome if visible."
              onChange={(e) =>
                setDetails({ ...details, description: e.target.value })
              }
            />
          </label>
          <div className="buttons">
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => trim("start")}
            >
              Start here · {clock(details.start)}
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => trim("end")}
            >
              End here · {clock(details.end)}
            </Button>
            <Button
              size="sm"
              disabled={busy}
              onClick={async () => {
                if (await save({ ...details, tags: clip.tags }))
                  setDetails(null)
              }}
            >
              Save clip
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setDetails(null)}>
              Cancel
            </Button>
          </div>
          {error && <p role="alert">{error}</p>}
        </div>
      )}
      <div className="tag-list">
        {!tags.length && (
          <p className="hint">
            No player tags yet. Pause the video and choose Tag player.
          </p>
        )}
        {tags.map((t, i) => (
          <div key={t.id || i} className="tag-row">
            <button
              className="tag-link"
              onClick={() => seek(t.time)}
              disabled={busy}
            >
              <span className="time">{clock(t.time)}</span>
              <strong>{t.name}</strong>
              <span>
                {t.skill}
                {t.source === "automatic" && " · auto"}
                {t.result !== "Ungraded" && " · " + t.result}
              </span>
            </button>
            <Button
              size="icon-xs"
              variant="ghost"
              aria-label={"Edit tag for " + t.name}
              disabled={busy || !!details}
              onClick={() => editTag(t)}
            >
              <Pencil />
            </Button>
            <Button
              size="icon-xs"
              variant="ghost"
              aria-label={"Remove tag for " + t.name}
              disabled={busy || !!details}
              onClick={() => {
                if (confirm("Remove this tag for " + t.name + "?"))
                  void save({ ...clip, tags: tags.filter((_, j) => j !== i) })
              }}
            >
              <Trash2 />
            </Button>
          </div>
        ))}
      </div>
    </section>
  )
}
