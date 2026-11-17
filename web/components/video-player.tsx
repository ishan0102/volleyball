"use client"

import { useEffect, useState, type RefObject } from "react"
import { Pause, Play, UserRoundPlus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { clock, type Clip, type Draft, type Mark } from "@/lib/film"

type Props = {
  video: RefObject<HTMLVideoElement | null>
  clip: Clip
  duration: number
  draft: Draft | null
  busy: boolean
  onMark: (point: Mark) => void
}

export function VideoPlayer({
  video,
  clip,
  duration,
  draft,
  busy,
  onMark,
}: Props) {
  const [time, setTime] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [clipEnd, setClipEnd] = useState<number | null>(null)
  const [aspect, setAspect] = useState("16 / 9")
  useEffect(() => setClipEnd(null), [clip.id])
  const pins = [
    ...clip.tags,
    ...(draft ? [{ ...draft, name: draft.name || "Player" }] : []),
  ].filter((p) => Math.abs(p.time - time) < 0.65)
  function toggle() {
    const v = video.current
    if (!v) return
    if (v.paused) {
      setClipEnd(null)
      void v.play().catch(() => {})
    } else v.pause()
  }
  return (
    <section aria-label="Match player">
      <div className="frame" style={{ aspectRatio: aspect }}>
        <video
          ref={video}
          playsInline
          preload="metadata"
          src="/preview.mp4"
          onLoadedMetadata={(e) =>
            setAspect(
              e.currentTarget.videoWidth + " / " + e.currentTarget.videoHeight,
            )
          }
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onTimeUpdate={(e) => {
            const t = e.currentTarget.currentTime
            setTime(t)
            if (clipEnd !== null && t >= clipEnd) {
              e.currentTarget.pause()
              setClipEnd(null)
            }
          }}
        />
        <button
          type="button"
          className="frame-hit"
          aria-label="Tag a player on this frame"
          disabled={busy}
          onClick={(e) => {
            const v = video.current
            if (!v || !v.videoWidth) return
            v.pause()
            const r = e.currentTarget.getBoundingClientRect()
            onMark({
              time: v.currentTime,
              x: e.detail ? (e.clientX - r.left) / r.width : 0.5,
              y: e.detail ? (e.clientY - r.top) / r.height : 0.5,
            })
          }}
        />
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
      <div className="transport">
        <Button
          aria-label={playing ? "Pause" : "Play match"}
          variant="ghost"
          size="icon"
          disabled={busy || !!draft}
          onClick={toggle}
        >
          {playing ? <Pause /> : <Play />}
        </Button>
        <span className="time">{clock(time)}</span>
        <input
          type="range"
          aria-label="Match timeline"
          min={0}
          max={duration}
          step={0.05}
          value={time}
          disabled={busy || !!draft}
          onChange={(e) => {
            const v = video.current
            if (v) {
              v.pause()
              setClipEnd(null)
              v.currentTime = Number(e.target.value)
              setTime(v.currentTime)
            }
          }}
        />
        <span className="time">{clock(duration)}</span>
      </div>
      <div className="video-tools">
        <span>
          <UserRoundPlus size={15} />
          Click a player in the frame to tag them.
        </span>
        <Button
          size="sm"
          variant="outline"
          disabled={busy || !!draft}
          onClick={() => {
            const v = video.current
            if (v) {
              v.currentTime = clip.start
              setClipEnd(clip.end)
              void v.play().catch(() => {})
            }
          }}
        >
          Play clip
        </Button>
      </div>
    </section>
  )
}
