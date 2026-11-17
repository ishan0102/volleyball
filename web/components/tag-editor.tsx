import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { NativeSelect } from "@/components/ui/native-select"
import { clock, type Draft, type Match } from "@/lib/film"

type Props = {
  draft: Draft
  match: Match
  names: string[]
  busy: boolean
  change: (d: Draft) => void
  save: () => void
  cancel: () => void
}

export function TagEditor({
  draft,
  match,
  names,
  busy,
  change,
  save,
  cancel,
}: Props) {
  return (
    <form
      className="editor"
      onSubmit={(e) => {
        e.preventDefault()
        if (!busy && draft.name.trim() && draft.skill) save()
      }}
    >
      <div className="section-title">
        <h2>Tag player</h2>
        <span className="time">{clock(draft.time)}</span>
      </div>
      <fieldset disabled={busy}>
        <div className="fields">
          <label>
            Player
            <Input
              autoFocus
              maxLength={60}
              placeholder="Player name"
              value={draft.name}
              onChange={(e) => change({ ...draft, name: e.target.value })}
            />
          </label>
          <label>
            Touch
            <NativeSelect
              value={draft.skill}
              onChange={(e) => change({ ...draft, skill: e.target.value })}
            >
              <option value="" disabled>
                Choose a touch…
              </option>
              {match.skills.map((s) => (
                <option key={s} value={s}>
                  {s === "Appearance" ? "Appearance only (no touch)" : s}
                </option>
              ))}
            </NativeSelect>
          </label>
          <label>
            Outcome
            <NativeSelect
              value={draft.result}
              onChange={(e) => change({ ...draft, result: e.target.value })}
            >
              {match.results.map((s) => (
                <option key={s} value={s}>
                  {s === "Appearance" ? "Appearance only (no touch)" : s}
                </option>
              ))}
            </NativeSelect>
          </label>
        </div>
        <div className="tag-actions">
          <div className="chips">
            {names.map((n) => (
              <Button
                size="xs"
                variant={draft.name === n ? "secondary" : "outline"}
                key={n}
                type="button"
                onClick={() => change({ ...draft, name: n })}
              >
                {n}
              </Button>
            ))}
          </div>
          <div className="buttons">
            <Button variant="ghost" type="button" onClick={cancel}>
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!draft.name.trim() || !draft.skill || busy}
            >
              {busy ? "Saving…" : "Save tag"}
            </Button>
          </div>
        </div>
      </fieldset>
    </form>
  )
}
