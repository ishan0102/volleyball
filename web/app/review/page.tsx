"use client"

import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { NativeSelect } from "@/components/ui/native-select"
import { api, clock, type Appearance, type Match } from "@/lib/film"

function ContextVideo({ hit }: { hit: Appearance }) {
  const video = useRef<HTMLVideoElement>(null)
  const [time, setTime] = useState(hit.time)
  const [x, y, w, h] = hit.box
  return (
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
  )
}

export default function ReviewPlayers() {
  const [match, setMatch] = useState<Match | null>(null)
  const [filter, setFilter] = useState("")
  const [replacement, setReplacement] = useState("")
  const [index, setIndex] = useState(0)
  const [context, setContext] = useState(false)
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  useEffect(() => {
    api<Match>("/match")
      .then(setMatch)
      .catch((e) => setError(e.message))
  }, [])
  const events = Object.values(match?.appearances ?? {})
  const pending = events.filter((e) => e.status === "pending")
  const queue = pending.filter((e) => !filter || e.name === filter)
  const hit = queue[index % (queue.length || 1)]
  const roster = [
    ...new Set(match?.clips.flatMap((c) => c.tags.map((t) => t.name))),
  ].sort()
  function clear() {
    setContext(false)
    setReplacement("")
    setError("")
  }
  async function decide(name: string | null) {
    if (!hit || busy) return
    setBusy(true)
    try {
      const result = await api<{ match: Match }>("/review-appearance", {
        id: hit.id,
        file: hit.file,
        name,
      })
      setMatch(result.match)
      clear()
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save decision.")
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <header>
        <div>
          <a href="/">← Film room</a>
        </div>
        <span>{match?.title}</span>
      </header>
      <main className="scan-review">
        <h1>Review player matches</h1>
        <div className="review-filters">
          <span aria-live="polite">
            {match ? pending.length + " left to review" : "Opening match…"}
          </span>
          <NativeSelect
            aria-label="Filter review by player"
            disabled={busy}
            value={filter}
            onChange={(e) => {
              setFilter(e.target.value)
              setIndex(0)
              clear()
            }}
          >
            <option value="">All players</option>
            {roster.map((n) => (
              <option key={n}>{n}</option>
            ))}
          </NativeSelect>
        </div>
        {error && <p role="alert">{error}</p>}
        {hit ? (
          <section className="details">
            <div className="section-title">
              <h2>Is this {hit.name}?</h2>
              <span className="time">{clock(hit.time)}</span>
            </div>
            <div className="comparison">
              <figure>
                <img
                  src={"/scan-crop/" + hit.reference}
                  alt={"Saved reference for " + hit.name}
                />
                <figcaption>Your tag · {hit.name}</figcaption>
              </figure>
              <figure>
                <img
                  src={"/scan-crop/" + hit.file}
                  alt={"Possible match at " + clock(hit.time)}
                />
                <figcaption>Proposed match · {clock(hit.time)}</figcaption>
              </figure>
            </div>
            <div className="buttons">
              <Button variant="outline" onClick={() => setContext((v) => !v)}>
                {context ? "Hide footage" : "View in footage"}
              </Button>
              <Button
                variant="ghost"
                disabled={busy || queue.length < 2}
                onClick={() => {
                  setIndex((i) => i + 1)
                  clear()
                }}
              >
                Skip for now
              </Button>
            </div>
            {context && <ContextVideo key={hit.id} hit={hit} />}
            <div className="review-actions">
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
                disabled={busy}
                onClick={() => decide(replacement || hit.name)}
              >
                Save as {replacement || hit.name}
              </Button>
              <Button
                variant="ghost"
                disabled={busy}
                onClick={() => decide(null)}
              >
                Dismiss
              </Button>
            </div>
          </section>
        ) : (
          match && (
            <p>
              {filter
                ? "No pending matches for " + filter + "."
                : "No player matches awaiting review."}
            </p>
          )
        )}
      </main>
    </>
  )
}
