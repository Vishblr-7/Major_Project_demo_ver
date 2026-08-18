import { useEffect, useState } from 'react'
import { Row, Col, Card, Select, Alert, Statistic, Tag, Empty } from 'antd'
import { PlayCircleOutlined } from '@ant-design/icons'
import PageHeader from '../components/PageHeader'
import CongestionBadge from '../components/CongestionBadge'
import { formatValue } from '../components/KpiCard'
import AnalyzingOverlay from '../components/AnalyzingOverlay'
import { useCountUp, useMinimumDelay } from '../hooks/useCountUp'
import { api, DEMO_VIDEO_ANNOTATED_URL, DEMO_VIDEO_ID, DEMO_VIDEO_RAW_URL } from '../services/api'
import type { VideoDetail, VideoListItem } from '../types/api'

const CLASS_ORDER: Array<[string, string]> = [
  ['car', 'Cars'],
  ['motorcycle', 'Motorcycles'],
  ['bus', 'Buses'],
  ['truck', 'Trucks'],
  ['autorickshaw', 'Autorickshaws'],
  ['bicycle', 'Bicycles (excluded)'],
]

function AnimatedStatistic({
  title,
  value,
  suffix,
}: {
  title: string
  value: number | null
  suffix?: string
}) {
  const animated = useCountUp(value)
  return (
    <Statistic
      title={title}
      value={value === null ? 'N/A' : formatValue(animated ?? value)}
      suffix={value === null ? undefined : suffix}
    />
  )
}

export default function VideoAnalysis() {
  const [videos, setVideos] = useState<VideoListItem[]>([])
  const [selected, setSelected] = useState<string>(DEMO_VIDEO_ID)
  const [detail, setDetail] = useState<VideoDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [fetching, setFetching] = useState(false)

  useEffect(() => {
    api.getVideos().then(setVideos).catch(() => undefined)
  }, [])

  useEffect(() => {
    setFetching(true)
    setError(null)
    api
      .getVideoDetail(selected)
      .then(setDetail)
      .catch((e) => setError(String(e)))
      .finally(() => setFetching(false))
  }, [selected])

  // Real request has usually already finished well before this elapses --
  // this paces the reveal so it visibly "analyzes" during a live demo
  // instead of the numbers appearing instantly. Data itself is untouched.
  const ready = useMinimumDelay(!fetching && detail !== null, [selected], 1600)

  const hasProcessedMedia = selected === DEMO_VIDEO_ID

  return (
    <div>
      <PageHeader
        title="Traffic Video Analysis"
        subtitle="YOLO11s + ByteTrack detection results for a selected INDRA video"
      />

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={10}>
          <Select
            style={{ width: '100%' }}
            value={selected}
            onChange={setSelected}
            showSearch
            options={videos.map((v) => ({
              value: v.video_id,
              label: `${v.video_id} · ${v.frames} frames · ${v.resolution}`,
            }))}
            placeholder="Select a demo video"
          />
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={13}>
          <Card
            title={
              <span>
                <PlayCircleOutlined /> Processed Video {hasProcessedMedia ? '(YOLO+ByteTrack annotated)' : ''}
              </span>
            }
            variant="borderless"
            style={{ background: '#111a2c' }}
          >
            {hasProcessedMedia ? (
              <video
                key={DEMO_VIDEO_ANNOTATED_URL}
                controls
                style={{ width: '100%', borderRadius: 8, background: '#000' }}
                src={DEMO_VIDEO_ANNOTATED_URL}
              >
                <track kind="captions" />
              </video>
            ) : (
              <Empty
                description="Annotated video is only prepared for the demo video (video2). Statistics below are still real, computed from the authoritative dataset for this video."
              />
            )}
            {hasProcessedMedia && (
              <div className="data-source-tag" style={{ marginTop: 10 }}>
                Source: outputs/module1_indra_batch/individual_runs/video2/video2_annotated.mp4
                {' · '}
                <a href={DEMO_VIDEO_RAW_URL} target="_blank" rel="noreferrer">
                  view raw source video
                </a>
              </div>
            )}
          </Card>
        </Col>

        <Col xs={24} lg={11}>
          {!ready && !error && <AnalyzingOverlay />}
          {error && <Alert type="error" title="Failed to load video statistics" description={error} showIcon />}
          {ready && detail && (
            <>
              <Card title="Detection Results by Class" variant="borderless" style={{ background: '#111a2c', marginBottom: 16 }}>
                {CLASS_ORDER.map(([key, label]) => (
                  <div
                    key={key}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      padding: '6px 0',
                      borderBottom: '1px solid #1f2b45',
                    }}
                  >
                    <span style={{ color: key === 'bicycle' ? '#8a99b8' : '#e6edf7' }}>{label}</span>
                    <Tag color={key === 'bicycle' ? 'default' : 'blue'}>
                      {formatValue(detail.vehicle_class_counts[key as keyof typeof detail.vehicle_class_counts])}
                    </Tag>
                  </div>
                ))}
              </Card>

              <Card title="Traffic Statistics" variant="borderless" style={{ background: '#111a2c' }}>
                <Row gutter={[16, 16]}>
                  <Col span={12}>
                    <AnimatedStatistic title="Total Vehicles" value={detail.total_vehicles} />
                  </Col>
                  <Col span={12}>
                    <AnimatedStatistic title="Bicycles Excluded" value={detail.bicycle_excluded_count} />
                  </Col>
                  <Col span={12}>
                    <AnimatedStatistic title="Average Speed" value={detail.average_speed_kmph} suffix="km/h" />
                  </Col>
                  <Col span={12}>
                    <AnimatedStatistic
                      title="Traffic Density"
                      value={detail.traffic_density_veh_per_100m2}
                      suffix="veh/100m²"
                    />
                  </Col>
                  <Col span={12}>
                    <AnimatedStatistic title="Avg Stop Duration" value={detail.average_stop_duration_s} suffix="s" />
                  </Col>
                  <Col span={12}>
                    <div className="metric-label" style={{ marginBottom: 6 }}>Congestion Status</div>
                    <CongestionBadge level={detail.congestion_status} />
                  </Col>
                </Row>
                <div className="data-source-tag" style={{ marginTop: 12 }}>{detail.note}</div>
              </Card>
            </>
          )}
        </Col>
      </Row>
    </div>
  )
}
