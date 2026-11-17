export type Mark = { x: number; y: number; time: number }
export type Tag = Mark & {
  id?: string
  name: string
  source?: "automatic" | "reviewed"
  skill: string
  result: string
}
export type Clip = {
  id: string
  start: number
  end: number
  keep: boolean
  tags: Tag[]
  note: string
  description?: string
}
export type Match = {
  appearances?: Record<string, Appearance>
  title: string
  match_id: string
  duration: number
  revision: number
  clips: Clip[]
  skills: string[]
  results: string[]
}
export type Draft = Tag & { id: string; clipId: string | null }
export type Suggestion = Mark & { id: string }

export function clock(seconds: number) {
  return (
    Math.floor(seconds / 60) +
    ":" +
    String(Math.floor(seconds % 60)).padStart(2, "0")
  )
}

export const touchSkills = ["Serve", "Pass", "Set", "Attack", "Block", "Dig"]

export function hasTouch(clip: Clip, player?: string) {
  return clip.tags.some(
    (t) => (!player || t.name === player) && touchSkills.includes(t.skill),
  )
}

export function clipName(clip: Clip) {
  return (
    clip.note ||
    (clip.tags.length
      ? Array.from(new Set(clip.tags.map((t) => t.name))).join(" · ")
      : "Suggested clip")
  )
}

export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(
    path,
    body === undefined
      ? { cache: "no-store" }
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  )
  const data = await response.json()
  if (!response.ok)
    throw new Error(data.error || "Request failed. Please retry.")
  return data
}

export type Appearance = {
  id: string
  name: string
  time: number
  file: string
  reference: string
  box: [number, number, number, number]
  status: "pending" | "automatic" | "reviewed" | "rejected"
}
