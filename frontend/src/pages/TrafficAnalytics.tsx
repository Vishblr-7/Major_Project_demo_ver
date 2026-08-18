import { useEffect, useState } from 'react'
import { Row, Col, Card, Select, Spin, Alert } from 'antd'
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  BarChart,
  Bar,
  Legend,
} from 'recharts'
import PageHeader from '../components/PageHeader'
import CongestionBadge from '../components/CongestionBadge'
import { api, DEMO_VIDEO_ID } from '../services/api'
import type { TrafficTimeseriesPoint, VideoDetail, VideoListItem } from '../types/api'

const CHART_GRID = '#1f2b45'
const AXIS_COLOR = '#8a99b8'

export default function TrafficAnalytics() {
  const [videos, setVideos] = useState<VideoListItem[]>([])
  const [selected, setSelected] = useState(DEMO_VIDEO_ID)
  const [series, setSeries] = useState<TrafficTimeseriesPoint[]>([])
  const [detail, setDetail] = useState<VideoDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.getVideos().then(setVideos).catch(() => undefined)
  }, [])

  useEffect(() => {
    setLoading(true)
    setError(null)
    Promise.all([api.getTrafficTimeseries(selected), api.getVideoDetail(selected)])
      .then(([ts, d]) => {
        setSeries(ts)
        setDetail(d)
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false))
  }, [selected])

  const composition = detail
    ? Object.entries(detail.vehicle_class_counts).map(([name, count]) => ({ name, count }))
    : []

  return (
    <div>
      <PageHeader
        title="Traffic Analytics"
        subtitle="Per-frame traffic behaviour, derived from Module 1's own precomputed columns"
      />

      <Row gutter={16} style={{ marginBottom: 16 }} align="middle">
        <Col span={10}>
          <Select
            style={{ width: '100%' }}
            value={selected}
            onChange={setSelected}
            showSearch
            options={videos.map((v) => ({ value: v.video_id, label: v.video_id }))}
          />
        </Col>
        <Col>
          {detail && (
            <span style={{ color: '#8a99b8', fontSize: 13 }}>
              Congestion status: <CongestionBadge level={detail.congestion_status} />
            </span>
          )}
        </Col>
      </Row>

      {loading && <Spin />}
      {error && <Alert type="error" title="Failed to load traffic analytics" description={error} showIcon />}

      {!loading && !error && (
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={12}>
            <Card title="Vehicle Composition" variant="borderless" style={{ background: '#111a2c' }}>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={composition}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                  <XAxis dataKey="name" stroke={AXIS_COLOR} fontSize={12} />
                  <YAxis stroke={AXIS_COLOR} fontSize={12} allowDecimals={false} />
                  <Tooltip contentStyle={{ background: '#0e1626', border: '1px solid #1f2b45' }} />
                  <Bar dataKey="count" fill="#22d3ee" radius={[4, 4, 0, 0]} isAnimationActive={false} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </Col>

          <Col xs={24} lg={12}>
            <Card title="Vehicle Count Over Time" variant="borderless" style={{ background: '#111a2c' }}>
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={series}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                  <XAxis dataKey="frame_number" stroke={AXIS_COLOR} fontSize={12} label={{ value: 'Frame', position: 'insideBottom', offset: -4, fill: AXIS_COLOR }} />
                  <YAxis stroke={AXIS_COLOR} fontSize={12} allowDecimals={false} />
                  <Tooltip contentStyle={{ background: '#0e1626', border: '1px solid #1f2b45' }} />
                  <Line type="monotone" dataKey="vehicle_count" stroke="#22d3ee" dot={false} strokeWidth={2} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </Card>
          </Col>

          <Col xs={24} lg={12}>
            <Card title="Traffic Density Over Time" variant="borderless" style={{ background: '#111a2c' }}>
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={series}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                  <XAxis dataKey="frame_number" stroke={AXIS_COLOR} fontSize={12} />
                  <YAxis stroke={AXIS_COLOR} fontSize={12} label={{ value: 'veh/100m²', angle: -90, position: 'insideLeft', fill: AXIS_COLOR }} />
                  <Tooltip contentStyle={{ background: '#0e1626', border: '1px solid #1f2b45' }} />
                  <Line type="monotone" dataKey="traffic_density" stroke="#facc15" dot={false} strokeWidth={2} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </Card>
          </Col>

          <Col xs={24} lg={12}>
            <Card title="Average Speed Over Time" variant="borderless" style={{ background: '#111a2c' }}>
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={series}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                  <XAxis dataKey="frame_number" stroke={AXIS_COLOR} fontSize={12} />
                  <YAxis stroke={AXIS_COLOR} fontSize={12} label={{ value: 'km/h', angle: -90, position: 'insideLeft', fill: AXIS_COLOR }} />
                  <Tooltip contentStyle={{ background: '#0e1626', border: '1px solid #1f2b45' }} />
                  <Line type="monotone" dataKey="average_speed_kmph" stroke="#34d399" dot={false} strokeWidth={2} connectNulls isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </Card>
          </Col>

          <Col span={24}>
            <Card title="Stop Duration Over Time" variant="borderless" style={{ background: '#111a2c' }}>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={series}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                  <XAxis dataKey="frame_number" stroke={AXIS_COLOR} fontSize={12} />
                  <YAxis stroke={AXIS_COLOR} fontSize={12} label={{ value: 'seconds', angle: -90, position: 'insideLeft', fill: AXIS_COLOR }} />
                  <Tooltip contentStyle={{ background: '#0e1626', border: '1px solid #1f2b45' }} />
                  <Legend />
                  <Line type="monotone" name="Avg stop duration (s)" dataKey="stop_duration_s" stroke="#f87171" dot={false} strokeWidth={2} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </Card>
          </Col>
        </Row>
      )}
    </div>
  )
}
