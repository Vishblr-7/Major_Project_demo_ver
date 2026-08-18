import { useEffect, useState } from 'react'
import { Steps, Card, Button, Row, Col, Alert, Tag } from 'antd'
import {
  VideoCameraOutlined,
  CarOutlined,
  DashboardOutlined,
  ThunderboltOutlined,
  CloudOutlined,
  RobotOutlined,
  ApartmentOutlined,
  LeftOutlined,
  RightOutlined,
  LoadingOutlined,
} from '@ant-design/icons'
import KpiCard from '../components/KpiCard'
import CongestionBadge from '../components/CongestionBadge'
import AnalyzingOverlay from '../components/AnalyzingOverlay'
import { CopertTag, XgboostTag } from '../components/SourceTag'
import { useMinimumDelay } from '../hooks/useCountUp'
import { api, DEMO_VIDEO_ANNOTATED_URL, DEMO_VIDEO_ID } from '../services/api'
import type { ModelPerformance, Pollutant, VideoDetail } from '../types/api'

const STEPS = [
  { title: 'Demo Video', icon: <VideoCameraOutlined /> },
  { title: 'Vehicle Counts', icon: <CarOutlined /> },
  { title: 'Traffic Density', icon: <DashboardOutlined /> },
  { title: 'Avg Speed & Congestion', icon: <ThunderboltOutlined /> },
  { title: 'Emissions', icon: <CloudOutlined /> },
  { title: 'Model Performance', icon: <RobotOutlined /> },
  { title: 'Architecture', icon: <ApartmentOutlined /> },
]

const POLLUTANT_META: Record<Pollutant, { label: string; accent: string }> = {
  CO2: { label: 'CO2', accent: '#f87171' },
  NOx: { label: 'NOx', accent: '#fb923c' },
  CO: { label: 'CO', accent: '#facc15' },
  PM25: { label: 'PM2.5', accent: '#c084fc' },
}

function StepLoading() {
  return (
    <div style={{ textAlign: 'center', padding: '70px 0' }}>
      <LoadingOutlined style={{ fontSize: 24, color: '#22d3ee' }} spin />
      <div style={{ color: '#8a99b8', marginTop: 10, fontSize: 13 }}>Computing…</div>
    </div>
  )
}

export default function DemoMode() {
  const [step, setStep] = useState(0)
  const [video, setVideo] = useState<VideoDetail | null>(null)
  const [emissions, setEmissions] = useState<Record<Pollutant, number> | null>(null)
  const [perf, setPerf] = useState<ModelPerformance | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      api.getVideoDetail(DEMO_VIDEO_ID),
      api.getVideoEmissions(DEMO_VIDEO_ID),
      api.getModelPerformance(),
    ])
      .then(([v, e, p]) => {
        setVideo(v)
        setEmissions(e.totals_g)
        setPerf(p)
      })
      .catch((err) => setError(String(err)))
  }, [])

  const dataLoaded = video !== null && emissions !== null && perf !== null
  // Real fetch usually finishes well under this -- pacing the reveal so a
  // live audience sees an analysis pass happen, not a static page. The
  // numbers that follow are always the same real, already-computed values.
  const ready = useMinimumDelay(dataLoaded, [], 1800)
  // Steps 1-5 each re-run a short "recomputing this step" beat when
  // navigated to, keyed on `step` so it replays on every visit.
  const stepReady = useMinimumDelay(ready, [step], step === 0 || step === 6 ? 0 : 900)

  if (error) return <Alert type="error" title="Demo failed to load" description={error} showIcon />
  if (!ready || !video || !emissions || !perf) {
    return <AnalyzingOverlay durationMs={1800} />
  }

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 className="page-title">Presentation Demo — video2</h1>
        <p className="page-subtitle">
          Live walkthrough of the completed pipeline, driven entirely by real project outputs.
        </p>
      </div>

      <Steps
        current={step}
        items={STEPS}
        size="small"
        style={{ marginBottom: 28 }}
        onChange={setStep}
      />

      <Card variant="borderless" style={{ background: '#111a2c', minHeight: 380 }}>
        {step === 0 && (
          <div style={{ textAlign: 'center' }}>
            <h2 className="section-title">1. Input Video → YOLO11s + ByteTrack Detection</h2>
            <video
              controls
              autoPlay
              muted
              loop
              style={{ maxWidth: 640, width: '100%', borderRadius: 10, background: '#000' }}
              src={DEMO_VIDEO_ANNOTATED_URL}
            >
              <track kind="captions" />
            </video>
            <p className="data-source-tag" style={{ marginTop: 10 }}>
              {video.resolution} · {video.frames} frames · {video.fps} fps
            </p>
          </div>
        )}

        {step === 1 && (!stepReady ? <StepLoading /> : (
          <div>
            <h2 className="section-title">2. Vehicle Detection & Class Counts</h2>
            <Row gutter={[16, 16]}>
              {Object.entries(video.vehicle_class_counts).map(([cls, count]) => (
                <Col span={8} key={cls}>
                  <KpiCard
                    label={cls === 'bicycle' ? 'Bicycles (excluded)' : cls}
                    value={count}
                    accent={cls === 'bicycle' ? '#5c6b8a' : '#22d3ee'}
                    animate
                  />
                </Col>
              ))}
            </Row>
            <p className="data-source-tag" style={{ marginTop: 16 }}>{video.note}</p>
          </div>
        ))}

        {step === 2 && (!stepReady ? <StepLoading /> : (
          <div>
            <h2 className="section-title">3. Traffic Density</h2>
            <Row gutter={16}>
              <Col span={12}>
                <KpiCard label="Traffic Density" value={video.traffic_density_veh_per_100m2} unit="veh/100m²" accent="#facc15" animate />
              </Col>
              <Col span={12}>
                <KpiCard label="Total Vehicles" value={video.total_vehicles} accent="#22d3ee" animate />
              </Col>
            </Row>
          </div>
        ))}

        {step === 3 && (!stepReady ? <StepLoading /> : (
          <div>
            <h2 className="section-title">4. Average Speed &amp; Congestion Status</h2>
            <Row gutter={16}>
              <Col span={12}>
                <KpiCard label="Average Speed" value={video.average_speed_kmph} unit="km/h" accent="#34d399" animate />
              </Col>
              <Col span={12}>
                <Card variant="borderless" style={{ background: '#0e1626', height: '100%' }}>
                  <div className="metric-label">Congestion Status</div>
                  <div style={{ marginTop: 10 }}>
                    <CongestionBadge level={video.congestion_status} />
                  </div>
                </Card>
              </Col>
            </Row>
          </div>
        ))}

        {step === 4 && (!stepReady ? <StepLoading /> : (
          <div>
            <h2 className="section-title">5. Emission Estimation</h2>
            <div style={{ marginBottom: 12 }}><CopertTag /></div>
            <Row gutter={[16, 16]}>
              {(Object.keys(emissions) as Pollutant[]).map((p) => (
                <Col span={6} key={p}>
                  <KpiCard label={POLLUTANT_META[p].label} value={emissions[p]} unit="g" accent={POLLUTANT_META[p].accent} animate />
                </Col>
              ))}
            </Row>
          </div>
        ))}

        {step === 5 && (!stepReady ? <StepLoading /> : (
          <div>
            <h2 className="section-title">6. AI Model Performance (XGBoost)</h2>
            <div style={{ marginBottom: 12 }}><XgboostTag /></div>
            <Row gutter={[16, 16]}>
              {(Object.keys(perf.pollutants) as Pollutant[]).map((p) => (
                <Col span={6} key={p}>
                  <KpiCard
                    label={`${POLLUTANT_META[p].label} R²`}
                    value={perf.pollutants[p].test_r2}
                    accent={POLLUTANT_META[p].accent}
                    sub="Held-out test set"
                    animate
                  />
                </Col>
              ))}
            </Row>
            <p style={{ color: '#c3ccdc', fontSize: 13, marginTop: 16 }}>
              Trained on 104 INDRA videos with video-level train/val/test splitting and GroupKFold
              validation — no window from the same video appears in both train and test.
            </p>
          </div>
        ))}

        {step === 6 && (
          <div style={{ textAlign: 'center' }}>
            <h2 className="section-title">7. Complete Pipeline</h2>
            <p style={{ color: '#c3ccdc' }}>
              Video → YOLO11s → ByteTrack → Vehicle Tracking → Traffic Features → Distance &amp;
              Density → COPERT → Emission Dataset → XGBoost → CO2 / NOx / CO / PM2.5
            </p>
            <Tag color="processing" style={{ marginTop: 12 }}>
              Full diagram available on the System Architecture page
            </Tag>
            <div style={{ marginTop: 20 }}>
              <Tag color="default">Next Phase (not implemented): TomTom API → Navigation → VAC → WACC → Hybrid/Quantum Optimization</Tag>
            </div>
          </div>
        )}
      </Card>

      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 20 }}>
        <Button icon={<LeftOutlined />} disabled={step === 0} onClick={() => setStep((s) => s - 1)}>
          Previous
        </Button>
        <Button
          type="primary"
          icon={<RightOutlined />}
          iconPlacement="end"
          disabled={step === STEPS.length - 1}
          onClick={() => setStep((s) => s + 1)}
        >
          Next
        </Button>
      </div>
    </div>
  )
}
