"use client"

import { useEffect, useRef, useState } from "react"
import { Check, RotateCcw, SkipForward, Undo2, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { NativeSelect } from "@/components/ui/native-select"
import { FilmShell } from "@/components/film-shell"
import { api, clock, type Appearance, type Match } from "@/lib/film"

function ContextVideo({ hit }: { hit: Appearance }) {
  const video = useRef<HTMLVideoElement>(null)
  const [time, setTime] = useState(hit.time)
  const [x, y, w, h] = hit.box
  return (
    <div className="review-context">
      <div className="context-video">
        <video
          ref={video}
          controls
          playsInline
          preload="metadata"
          src="/preview.mp4"
          onLoadedMetadata={(e) => {
            e.currentTarget.currentTime = hit.time
          }}
          onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
        />
        {Math.abs(time - hit.time) < 0.35 && (
          <span
            aria-label="Proposed player"
            className="player-box"
            style={{
              left: x * 100 + "%",
              top: y * 100 + "%",
              width: w * 100 + "%",
              height: h * 100 + "%",
            }}
          />
        )}
      </div>
      <div className="video-tools">
        <p className="time">Proposed appearance at {clock(hit.time)}</p>
        <div className="buttons">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              if (video.current) {
                video.current.pause()
                video.current.currentTime = hit.time
              }
            }}
          >
            Show tagged frame
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              if (video.current) {
                video.current.currentTime = Math.max(0, hit.time - 3)
                void video.current.play().catch(() => {})
              }
            }}
          >
            <RotateCcw />
            Play context
          </Button>
        </div>
      </div>
      <p className="hint">
        Compare the player with your saved reference. The outline marks the
        proposed appearance at {clock(hit.time)}.
      </p>
    </div>
  )
}

export default function ReviewPlayers() {
  const [match, setMatch] = useState<Match | null>(null)
  const [filter, setFilter] = useState("")
  const [replacement, setReplacement] = useState("")
  const [index, setIndex] = useState(0)
  const [error, setError] = useState("")
  const [notice, setNotice] = useState("")
  const [busy, setBusy] = useState(false)
  const [last, setLast] = useState<string | null>(null)
  const lock = useRef(false)
  useEffect(() => {
    setFilter(new URLSearchParams(location.search).get("player") || "")
    api<Match>("/match")
      .then(setMatch)
      .catch((e) => setError(e.message))
  }, [])
  const events = Object.values(match?.appearances ?? {})
  const reviewable = events.filter(
    (e) => e.status !== "automatic" && (!filter || e.name === filter),
  )
  const queue = reviewable.filter((e) => e.status === "pending")
  const hit = queue[index % (queue.length || 1)]
  const complete = reviewable.length - queue.length
  const roster = [
    ...new Set(match?.clips.flatMap((c) => c.tags.map((t) => t.name))),
  ].sort()
  async function decide(name: string | null) {
    if (!hit || lock.current) return
    lock.current = true
    setBusy(true)
    try {
      const result = await api<{ match: Match }>("/review-appearance", {
        id: hit.id,
        file: hit.file,
        name,
      })
      setMatch(result.match)
      setLast(hit.id)
      setReplacement("")
      setError("")
      setNotice(
        name
          ? "Saved as " + name + " at " + clock(hit.time)
          : "Dismissed match at " + clock(hit.time),
      )
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save decision.")
    } finally {
      lock.current = false
      setBusy(false)
    }
  }
  function skip() {
    setIndex((i) => i + 1)
    setReplacement("")
    setError("")
  }
  async function undo() {
    if (!last || !match || lock.current) return
    lock.current = true
    setBusy(true)
    try {
      const result = await api<{ match: Match }>("/undo-review", {
        id: last,
        revision: match.revision,
      })
      const next = Object.values(result.match.appearances ?? {}).filter(
        (e) => e.status === "pending" && (!filter || e.name === filter),
      )
      setIndex(
        Math.max(
          0,
          next.findIndex((e) => e.id === last),
        ),
      )
      setMatch(result.match)
      setLast(null)
      setReplacement("")
      setNotice("Decision undone")
      setError("")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not undo decision.")
    } finally {
      lock.current = false
      setBusy(false)
    }
  }
  useEffect(() => {
    function key(e: KeyboardEvent) {
      if (
        e.repeat ||
        e.metaKey ||
        e.ctrlKey ||
        e.altKey ||
        (e.target instanceof HTMLElement &&
          e.target.closest(
            "input,select,textarea,button,video,[contenteditable]",
          ))
      )
        return
      if (e.key === "1") {
        e.preventDefault()
        void decide(replacement || hit?.name || "")
      }
      if (e.key.toLowerCase() === "x") {
        e.preventDefault()
        void decide(null)
      }
      if (e.key.toLowerCase() === "n" && queue.length > 1) {
        e.preventDefault()
        skip()
      }
    }
    window.addEventListener("keydown", key)
    return () => window.removeEventListener("keydown", key)
  }, [hit, busy, replacement, queue.length])
  return (
    <FilmShell match={match} section="review" player={filter}>
      <main className="review-page">
        <div className="page-heading">
          <div>
            <p className="eyebrow">Player identification</p>
            <h1>Review matches</h1>
            <p className="subtitle" aria-live="polite">
              {match
                ? queue.length + " left · " + complete + " reviewed"
                : "Opening match…"}
            </p>
          </div>
          <NativeSelect
            aria-label="Filter review by player"
            disabled={busy}
            value={filter}
            onChange={(e) => {
              setFilter(e.target.value)
              setIndex(0)
              setReplacement("")
              setError("")
              history.replaceState(
                null,
                "",
                "/review" +
                  (e.target.value
                    ? "?player=" + encodeURIComponent(e.target.value)
                    : ""),
              )
            }}
          >
            <option value="">All players</option>
            {roster.map((n) => (
              <option key={n}>{n}</option>
            ))}
          </NativeSelect>
        </div>
        <div
          className="review-progress"
          role="progressbar"
          aria-label="Player matches reviewed"
          aria-valuemin={0}
          aria-valuemax={reviewable.length || 1}
          aria-valuenow={complete}
        >
          <div
            style={{
              width:
                (reviewable.length ? (complete / reviewable.length) * 100 : 0) +
                "%",
            }}
          />
        </div>
        {error && <p role="alert">{error}</p>}
        {notice && (
          <div className="buttons">
            <p className="notice" role="status">
              {notice}
            </p>
            {last && (
              <Button size="sm" variant="ghost" disabled={busy} onClick={undo}>
                <Undo2 />
                Undo
              </Button>
            )}
          </div>
        )}
        {hit ? (
          <div className="review-layout">
            <ContextVideo key={hit.id} hit={hit} />
            <section className="review-panel">
              <h2>Is this {hit.name}?</h2>
              <p>Match the player to your original tag.</p>
              <div className="comparison">
                <figure>
                  <img
                    src={"/scan-crop/" + hit.reference}
                    alt={"Your saved reference for " + hit.name}
                  />
                  <figcaption>Your reference</figcaption>
                </figure>
                <figure>
                  <img
                    src={"/scan-crop/" + hit.file}
                    alt={"Suggested appearance at " + clock(hit.time)}
                  />
                  <figcaption>At {clock(hit.time)}</figcaption>
                </figure>
              </div>
              <label>
                Player
                <NativeSelect
                  value={replacement || hit.name}
                  disabled={busy}
                  onChange={(e) => setReplacement(e.target.value)}
                >
                  {roster.map((n) => (
                    <option key={n}>{n}</option>
                  ))}
                </NativeSelect>
              </label>
              <Button
                className="save-review"
                disabled={busy}
                onClick={() => decide(replacement || hit.name)}
              >
                <Check />
                {busy ? "Saving…" : "Save as " + (replacement || hit.name)}
                <kbd>1</kbd>
              </Button>
              <div className="review-secondary">
                <Button
                  variant="ghost"
                  disabled={busy}
                  onClick={() => decide(null)}
                >
                  <X />
                  Dismiss <kbd>X</kbd>
                </Button>
                <Button
                  variant="ghost"
                  disabled={busy || queue.length < 2}
                  onClick={skip}
                >
                  <SkipForward />
                  Skip <kbd>N</kbd>
                </Button>
              </div>
            </section>
          </div>
        ) : (
          match && (
            <div className="empty-state">
              <Check size={30} />
              <h2>
                {filter
                  ? "You’re caught up for " + filter
                  : "You’re all caught up"}
              </h2>
              <p>Every suggested match in this view has a decision.</p>
              <a
                className="download"
                href={
                  "/" + (filter ? "?player=" + encodeURIComponent(filter) : "")
                }
              >
                Browse clips
              </a>
            </div>
          )
        )}
      </main>
    </FilmShell>
  )
}
