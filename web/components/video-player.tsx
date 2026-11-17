"use client"

import { useEffect, useState, type RefObject } from "react"
import { RotateCcw, UserRoundPlus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { clock, type Clip, type Draft, type Mark } from "@/lib/film"

export function VideoPlayer({
  video,
  clip,
  draft,
  busy,
  onMark,
  tagging,
  setTagging,
  fullMatch,
  setFullMatch,
}: {
  video: RefObject<HTMLVideoElement | null>
  clip: Clip
  draft: Draft | null
  busy: boolean
  onMark: (point: Mark) => void
  tagging: boolean
  setTagging: (value: boolean) => void
  fullMatch: boolean
  setFullMatch: (value: boolean) => void
}) {
  const [time, setTime] = useState(clip.start)
  const [error, setError] = useState("")
  useEffect(() => {
    if (tagging || draft) video.current?.pause()
  }, [tagging, draft, video])
  const pins = [
    ...clip.tags,
    ...(draft ? [{ ...draft, name: draft.name || "Player" }] : []),
  ].filter((p) => Math.abs(p.time - time) < 0.5)
  return (
    <section className="watch-player" aria-label="Match player">
      <div className="frame">
        <video
          ref={video}
          playsInline
          preload="metadata"
          controls={!tagging && !draft}
          src="/preview.mp4"
          onLoadedMetadata={(e) => {
            e.currentTarget.currentTime = draft?.time ?? clip.start
          }}
          onError={() =>
            setError(
              "The video could not load. Refresh and check that the match preview is available.",
            )
          }
          onTimeUpdate={(e) => {
            const t = e.currentTarget.currentTime
            setTime(t)
            if (!fullMatch && t >= clip.end && !e.currentTarget.paused)
              e.currentTarget.pause()
          }}
        />
        {(tagging || draft) && (
          <button
            className="frame-hit"
            aria-label="Pin a player on this frame"
            disabled={busy}
            onClick={(e) => {
              const v = video.current
              if (!v?.videoWidth) return
              const r = e.currentTarget.getBoundingClientRect()
              onMark({
                time: v.currentTime,
                x: e.detail ? (e.clientX - r.left) / r.width : 0.5,
                y: e.detail ? (e.clientY - r.top) / r.height : 0.5,
              })
            }}
          />
        )}
        {pins.map((p, i) => (
          <span
            className="marker"
            key={i}
            style={{ left: p.x * 100 + "%", top: p.y * 100 + "%" }}
          >
            {p.name}
          </span>
        ))}
      </div>
      {error && <p role="alert">{error}</p>}
      <div className="clip-transport">
        <span>{clock(Math.max(0, time - clip.start))}</span>
        <input
          type="range"
          aria-label="Clip position"
          min={clip.start}
          max={clip.end}
          step={0.05}
          value={Math.min(clip.end, Math.max(clip.start, time))}
          disabled={busy || !!draft || tagging}
          onChange={(e) => {
            const v = video.current
            if (v) {
              v.pause()
              v.currentTime = Number(e.target.value)
              setTime(v.currentTime)
            }
          }}
        />
        <span>{clock(clip.end - clip.start)}</span>
      </div>
      <div className="video-tools">
        <div className="buttons">
          <Button
            size="sm"
            variant="outline"
            disabled={busy || !!draft || tagging}
            onClick={() => {
              const v = video.current
              if (v) {
                v.currentTime = clip.start
                void v
                  .play()
                  .catch(() => setError("Press play to start the video."))
              }
            }}
          >
            <RotateCcw />
            Replay clip
          </Button>
          <label className="inline-check">
            <input
              type="checkbox"
              checked={fullMatch}
              disabled={!!draft || tagging}
              onChange={(e) => setFullMatch(e.target.checked)}
            />
            Full recording
          </label>
        </div>
        <Button
          variant={tagging ? "secondary" : "outline"}
          size="sm"
          disabled={busy || !!draft}
          onClick={() => setTagging(!tagging)}
        >
          <UserRoundPlus />
          {tagging ? "Cancel tagging" : "Tag player"}
        </Button>
      </div>
      {tagging && (
        <p className="hint">
          Click the player’s shirt at {clock(time)} to add a tag.
        </p>
      )}
    </section>
  )
}
