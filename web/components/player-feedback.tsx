import { ArrowUpRight } from "lucide-react"
import { clock, type Match } from "@/lib/film"

export function PlayerFeedback({
  match,
  player,
  watch,
}: {
  match: Match
  player: string
  watch: (clipId: string, time: number) => void
}) {
  const notes = match.coaching?.filter((n) => n.player === player) ?? []
  if (!notes.length) return null
  return (
    <section className="player-feedback" aria-label="Player feedback">
      <div className="feedback-heading">
        <h2>Your next practice</h2>
        <p>
          Specific observations from your footage. Each note links to its
          evidence.
        </p>
      </div>
      <div className="feedback-grid">
        {notes.map((note) => (
          <article key={note.id}>
            <small>
              {note.kind === "strength" ? "Keep doing" : "Try next time"} ·{" "}
              {note.evidence.length === 1
                ? "One observed example"
                : `${note.evidence.length} examples`}
            </small>
            <h3>{note.title}</h3>
            <p>{note.observation}</p>
            <p className="practice-cue">
              <strong>Practice cue</strong>
              {note.action}
            </p>
            {note.drill && <p className="practice-drill">{note.drill}</p>}
            <div className="feedback-evidence">
              {note.evidence.map((e) => (
                <button
                  key={e.clipId + e.time}
                  onClick={() => watch(e.clipId, e.time)}
                >
                  Watch · {clock(e.time)} <ArrowUpRight size={14} />
                </button>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}
