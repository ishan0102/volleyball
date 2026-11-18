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
        <h2>Next practice</h2>
      </div>
      <div className="feedback-grid">
        {notes.map((note) => (
          <article key={note.id}>
            <small>{note.kind === "strength" ? "Keep" : "Work on"}</small>
            <h3>{note.title}</h3>
            <p>{note.observation}</p>
            <p className="practice-cue">{note.action}</p>
            {note.drill && (
              <details className="practice-drill">
                <summary>Drill</summary>
                <p>{note.drill}</p>
              </details>
            )}
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
