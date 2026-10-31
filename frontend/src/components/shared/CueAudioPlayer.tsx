import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'

export function CueAudioPlayer({ audio }: { audio: string }) {
  const context = useRef<AudioContext | null>(null)
  const source = useRef<AudioBufferSourceNode | null>(null)
  const generation = useRef(0)
  const [playing, setPlaying] = useState(false)
  const [loading, setLoading] = useState(false)
  const [seconds, setSeconds] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  function stop() {
    generation.current += 1
    source.current?.stop()
    source.current = null
    if (context.current) void context.current.close()
    context.current = null
    setPlaying(false); setLoading(false)
  }
  useEffect(() => {
    setSeconds(null); setError(null); setPlaying(false); setLoading(false)
    return () => {
      generation.current += 1
      source.current?.stop()
      source.current = null
      if (context.current) void context.current.close()
      context.current = null
    }
  }, [audio])

  async function play() {
    stop()
    const token = generation.current
    setLoading(true); setError(null)
    try {
      const prefix = 'data:audio/wav;base64,'
      if (!audio.startsWith(prefix)) throw new Error('Unexpected audio preview format')
      const binary = atob(audio.slice(prefix.length))
      const bytes = Uint8Array.from(binary, character => character.charCodeAt(0))
      // Create/resume inside the click handler to retain the browser's gesture permission.
      const engine = new AudioContext()
      context.current = engine
      const resumed = engine.resume()
      const decoded = await engine.decodeAudioData(bytes.buffer)
      await resumed
      if (token !== generation.current) return
      setSeconds(decoded.duration)
      const node = engine.createBufferSource()
      node.buffer = decoded
      node.connect(engine.destination)
      source.current = node
      node.onended = () => {
        if (token !== generation.current) return
        source.current = null
        setPlaying(false)
        void engine.close()
        if (context.current === engine) context.current = null
      }
      node.start()
      setPlaying(true)
    } catch (reason) {
      if (token === generation.current) { stop(); setError(String(reason)) }
    } finally {
      if (token === generation.current) setLoading(false)
    }
  }
  return <div className="flex flex-wrap items-center gap-2 rounded border border-border p-2" data-cue-player>
    <Button size="sm" disabled={loading || playing} onClick={() => void play()}>Play preview</Button>
    <Button size="sm" variant="outline" disabled={!loading && !playing} onClick={stop}>Stop preview</Button>
    <span className="text-xs text-muted-foreground">{loading ? 'Loading audio…' : playing ? 'Playing' : 'Ready'}{seconds !== null && ` · ${seconds.toFixed(3)} seconds`}</span>
    {error && <span role="alert" className="text-xs text-destructive">{error}</span>}
  </div>
}
