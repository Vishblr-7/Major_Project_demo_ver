import axios from 'axios'
import type {
  Architecture,
  EmissionsSummary,
  ModelPerformance,
  Summary,
  TrafficTimeseriesPoint,
  VideoDetail,
  VideoEmissions,
  VideoListItem,
} from '../types/api'

const client = axios.create({ baseURL: '' })

export const api = {
  getSummary: () => client.get<Summary>('/api/summary').then((r) => r.data),
  getVideos: () => client.get<VideoListItem[]>('/api/videos').then((r) => r.data),
  getVideoDetail: (videoId: string) =>
    client.get<VideoDetail>(`/api/video/${videoId}`).then((r) => r.data),
  getTrafficTimeseries: (videoId: string) =>
    client.get<TrafficTimeseriesPoint[]>(`/api/traffic/${videoId}`).then((r) => r.data),
  getVideoEmissions: (videoId: string) =>
    client.get<VideoEmissions>(`/api/emissions/${videoId}`).then((r) => r.data),
  getEmissionsSummary: () =>
    client.get<EmissionsSummary>('/api/emissions/summary').then((r) => r.data),
  getModelPerformance: () =>
    client.get<ModelPerformance>('/api/models/performance').then((r) => r.data),
  getArchitecture: () => client.get<Architecture>('/api/architecture').then((r) => r.data),
}

export const DEMO_VIDEO_ID = 'video2'
// The original outputs/.../video2_annotated.mp4 is mpeg4-coded (OpenCV's
// mp4v fourcc) and unplayable in a browser <video> tag. The backend
// transcodes a browser-playable H.264 copy on startup and serves it here --
// same detection overlay, same pixels, just a browser-decodable codec.
export const DEMO_VIDEO_ANNOTATED_URL = '/media/playable/video2_annotated_h264.mp4'
export const DEMO_VIDEO_RAW_URL = '/media/raw/video2.mp4'
