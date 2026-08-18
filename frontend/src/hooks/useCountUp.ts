import { useEffect, useRef, useState } from 'react'

/** Animates a numeric display from 0 up to `target` over `durationMs`. Purely
 * cosmetic -- the final value is always the real, already-fetched number;
 * this never changes what data is shown, only how it visually arrives. */
export function useCountUp(target: number | null | undefined, durationMs = 900): number | null {
  const [value, setValue] = useState<number | null>(null)
  const frameRef = useRef<number | undefined>(undefined)

  useEffect(() => {
    if (target === null || target === undefined || Number.isNaN(target)) {
      setValue(null)
      return
    }
    const start = performance.now()
    const from = 0
    const animate = (now: number) => {
      const elapsed = now - start
      const progress = Math.min(1, elapsed / durationMs)
      const eased = 1 - (1 - progress) * (1 - progress)
      setValue(from + (target - from) * eased)
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(animate)
      } else {
        setValue(target)
      }
    }
    frameRef.current = requestAnimationFrame(animate)
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target, durationMs])

  return value
}

/** Stays `true` for at least `minMs` after `keys` changes, even if the
 * underlying async work finishes sooner -- gives a live "analyzing" beat
 * during a presentation instead of stats appearing instantly. Resolves once
 * both the minimum time has elapsed AND `ready` becomes true. */
export function useMinimumDelay(ready: boolean, keys: unknown[], minMs = 1400): boolean {
  const [elapsed, setElapsed] = useState(false)

  useEffect(() => {
    setElapsed(false)
    const timer = setTimeout(() => setElapsed(true), minMs)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, keys)

  return ready && elapsed
}
