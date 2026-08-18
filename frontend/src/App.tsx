import { Layout, Menu, Typography, Button } from 'antd'
import {
  DashboardOutlined,
  VideoCameraOutlined,
  BarChartOutlined,
  CloudOutlined,
  RobotOutlined,
  ApartmentOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import { Link, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import VideoAnalysis from './pages/VideoAnalysis'
import TrafficAnalytics from './pages/TrafficAnalytics'
import EmissionAnalytics from './pages/EmissionAnalytics'
import AIPrediction from './pages/AIPrediction'
import ArchitecturePage from './pages/Architecture'
import DemoMode from './pages/DemoMode'

const { Sider, Content, Header } = Layout

const NAV_ITEMS = [
  { key: '/', icon: <DashboardOutlined />, label: 'Dashboard' },
  { key: '/video-analysis', icon: <VideoCameraOutlined />, label: 'Traffic Video Analysis' },
  { key: '/traffic-analytics', icon: <BarChartOutlined />, label: 'Traffic Analytics' },
  { key: '/emission-analytics', icon: <CloudOutlined />, label: 'Emission Analytics' },
  { key: '/ai-prediction', icon: <RobotOutlined />, label: 'AI Emission Prediction' },
  { key: '/architecture', icon: <ApartmentOutlined />, label: 'System Architecture' },
]

export default function App() {
  const location = useLocation()
  const navigate = useNavigate()

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider width={250} style={{ background: '#0e1626', borderRight: '1px solid #1f2b45' }}>
        <div style={{ padding: '20px 20px 12px 20px' }}>
          <Typography.Text style={{ color: '#22d3ee', fontSize: 12, letterSpacing: '0.08em' }}>
            MAJOR_P_HYBRID
          </Typography.Text>
          <div style={{ color: '#f2f6fc', fontWeight: 700, fontSize: 16, marginTop: 2 }}>
            Hybrid Traffic System
          </div>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          style={{ background: 'transparent', borderRight: 'none' }}
          selectedKeys={[location.pathname]}
          items={NAV_ITEMS}
          onClick={(e) => navigate(e.key)}
        />
        <div style={{ padding: 20, position: 'absolute', bottom: 0, width: '100%' }}>
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            block
            size="large"
            onClick={() => navigate('/demo')}
            style={{ fontWeight: 700 }}
          >
            START DEMO
          </Button>
        </div>
      </Sider>
      <Layout>
        <Header
          style={{
            background: '#0e1626',
            borderBottom: '1px solid #1f2b45',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 24px',
            lineHeight: 'normal',
          }}
        >
          <div>
            <div style={{ color: '#f2f6fc', fontWeight: 600, fontSize: 15, lineHeight: 1.3 }}>
              Hybrid Intelligent Traffic &amp; Emission Monitoring System
            </div>
            <div style={{ color: '#8a99b8', fontSize: 12, lineHeight: 1.3 }}>
              AI-Based Traffic Detection, Emission Estimation &amp; Prediction
            </div>
          </div>
          <Link to="/demo">
            <Button
              icon={<ThunderboltOutlined />}
              style={{ borderColor: '#22d3ee', color: '#22d3ee', background: 'transparent' }}
            >
              Presentation Demo Mode
            </Button>
          </Link>
        </Header>
        <Content style={{ padding: 24, overflowY: 'auto' }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/video-analysis" element={<VideoAnalysis />} />
            <Route path="/traffic-analytics" element={<TrafficAnalytics />} />
            <Route path="/emission-analytics" element={<EmissionAnalytics />} />
            <Route path="/ai-prediction" element={<AIPrediction />} />
            <Route path="/architecture" element={<ArchitecturePage />} />
            <Route path="/demo" element={<DemoMode />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  )
}
