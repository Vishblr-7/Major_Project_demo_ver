// Mirrors backend/api/main.py response shapes exactly. If a field can be
// genuinely unavailable in the source data, its type includes `null` --
// callers must render "N/A" for null, never fabricate a placeholder number.

export type VehicleClass =
  | 'car'
  | 'motorcycle'
  | 'bus'
  | 'truck'
  | 'autorickshaw'
  | 'bicycle'

export type Pollutant = 'CO2' | 'NOx' | 'CO' | 'PM25'

export const POLLUTANTS: Pollutant[] = ['CO2', 'NOx', 'CO', 'PM25']

export interface Summary {
  videos_processed: number
  total_vehicles_tracked: number
  vehicle_class_counts: Record<VehicleClass, number>
  tracked_scope_note: string
  bicycle_note: string
  average_speed_kmph: number | null
  average_traffic_density_veh_per_100m2: number | null
  congestion_level: string
  total_emissions_g: Record<Pollutant, number>
  emission_source: string
}

export interface VideoListItem {
  video_id: string
  resolution: string
  fps: number
  frames: number
  calibration_profile: string
  status: string
}

export interface VideoDetail {
  video_id: string
  resolution: string
  fps: number | null
  frames: number | null
  vehicle_class_counts: Record<VehicleClass, number>
  total_vehicles: number
  note: string
  bicycle_excluded_count: number
  average_speed_kmph: number | null
  traffic_density_veh_per_100m2: number | null
  average_stop_duration_s: number | null
  total_distance_km: number | null
  congestion_status: string
}

export interface TrafficTimeseriesPoint {
  frame_number: number
  vehicle_count: number
  traffic_density: number | null
  average_speed_kmph: number | null
  stop_duration_s: number | null
}

export interface VideoEmissions {
  video_id: string
  included_tracks?: number
  totals_g: Record<Pollutant, number>
  average_per_vehicle_g?: Record<Pollutant, number>
  by_vehicle_type: Array<Record<string, number | string>> | Record<string, never>
  emission_source?: string
  note?: string
}

export interface EmissionsSummary {
  included_vehicle_tracks: number
  excluded_vehicle_tracks: number
  excluded_by_type: Record<string, number>
  total_emissions_g: Record<Pollutant, number>
  average_emission_per_vehicle_g: Record<Pollutant, number>
  by_vehicle_type: Array<Record<string, number | string>>
  pollutants: Pollutant[]
  emission_source: string
}

export interface PollutantPerformance {
  test_r2: number
  test_mae: number
  test_rmse: number
  n_test_windows: number
  cv_r2_mean: number
  cv_r2_std: number
}

export interface ModelPerformance {
  pollutants: Record<Pollutant, PollutantPerformance>
  model_type: string
  training_scale: string
  validation_method: string
  caveats: Record<string, string>
  source_file: string
}

export interface ArchitectureStage {
  stage: string
  detail: string
}

export interface Architecture {
  implemented: ArchitectureStage[]
  next_phase: ArchitectureStage[]
}
