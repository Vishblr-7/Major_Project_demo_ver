import { useEffect, useState } from 'react'
import { Progress } from 'antd'
import { LoadingOutlined } from '@ant-design/icons'

const STAGES = [
  'Loading frames…',
  'Running YOLO11s detection…',
  'ByteTrack vehicle tracking…',
  'Computing traffic & distance features…',
  'Aggregating results…',
]

/** Presentation-only staged loading sequence: the numbers it precedes are
 * always the real, already-computed values from the authoritative dataset
 * (see services/api.ts) -- this does not run inference, it paces how the
 * already-fetched result is revealed so a live audience sees an analysis
 * step happen rather than a static page. */
export default function AnalyzingOverlay({ durationMs = 1400 }: { durationMs?: number }) {
  const [percent, setPercent] = useState(0)

  useEffect(() => {
    const start = performance.now()
    let raf: number
    const tick = (now: number) => {
      const pct = Math.min(100, ((now - start) / durationMs) * 100)
      setPercent(pct)
      if (pct < 100) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [durationMs])

  const stageIndex = Math.min(STAGES.length - 1, Math.floor((percent / 100) * STAGES.length))

  return (
    <div style={{ padding: '48px 24px', textAlign: 'center' }}>
      <LoadingOutlined style={{ fontSize: 28, color: '#22d3ee' }} spin />
      <div style={{ color: '#e6edf7', fontWeight: 600, marginTop: 14, fontSize: 15 }}>
        {STAGES[stageIndex]}
      </div>
      <Progress
        percent={Math.round(percent)}
        showInfo={false}
        strokeColor="#22d3ee"
        railColor="#1f2b45"
        style={{ maxWidth: 360, margin: '16px auto 0 auto' }}
      />
      <div className="data-source-tag" style={{ marginTop: 10 }}>
        Replaying Module 1 + Module 2 results for this video
      </div>
    </div>
  )
}
