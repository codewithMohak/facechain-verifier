export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface CropBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  width: number;
  height: number;
}

export interface CameraMetadata {
  make?: string | null;
  model?: string | null;
  software?: string | null;
  lens_make?: string | null;
  lens_model?: string | null;
}

export interface CaptureParameters {
  exposure_time?: number | string | null;
  f_number?: number | null;
  iso?: number | null;
  focal_length?: number | null;
  flash?: number | null;
  white_balance?: number | null;
}

export interface GPSMetadata {
  available: boolean;
  latitude?: number | null;
  longitude?: number | null;
  altitude?: number | null;
  map_url?: string | null;
}

export interface MissingMetadataItem {
  field: string;
  category: string;
  detail: string;
}

export interface SuspiciousIndicator {
  indicator: string;
  severity: 'low' | 'medium' | 'high';
  detail: string;
}

export interface ExtractedMetadata {
  format: string;
  width: number;
  height: number;
  color_mode: string;
  has_icc_profile: boolean;
  file_size_bytes: number;
  has_exif: boolean;
  camera: CameraMetadata;
  capture_parameters: CaptureParameters;
  timestamps: {
    original?: string | null;
    digitized?: string | null;
    modified?: string | null;
    filesystem_ctime?: string | null;
    filesystem_mtime?: string | null;
  };
  gps: GPSMetadata;
  missing_metadata: MissingMetadataItem[];
  suspicious_indicators: SuspiciousIndicator[];
  raw_exif_count: number;
  disclaimer: string;
}

export interface ELAStatistics {
  mean_error: number;
  max_error: number;
  std_error: number;
  median_error: number;
  high_contrast_percentage: number;
}

export interface JPEGEncodingProperties {
  progressive: boolean;
  subsampling: string;
  quantization_tables_present: boolean;
}

export interface LosslessAnalysis {
  color_mode: string;
  alpha_properties?: {
    has_alpha_channel: boolean;
    fully_opaque_pct?: number;
    fully_transparent_pct?: number;
    semi_transparent_pct?: number;
  };
  png_chunks_detected?: string[];
  text_metadata_entries?: Record<string, string>;
  interlaced?: boolean;
}

export interface WebPProperties {
  mode: string;
  has_alpha: boolean;
  is_animated: boolean;
  frame_count: number;
}

export interface ImageAnalysis {
  format: string;
  ela_applicable: boolean;
  ela_path?: string | null;
  parameters?: {
    recompression_quality: number;
    display_scale: number;
  };
  statistics?: ELAStatistics;
  encoding_properties?: JPEGEncodingProperties;
  lossless_analysis?: LosslessAnalysis;
  webp_properties?: WebPProperties;
  observable_indicators: string[];
  methodology_note: string;
  disclaimer: string;
}

export interface FaceAnalysis {
  face_detected: boolean;
  face_count: number;
  confidence?: number;
  bounding_box?: BoundingBox;
  crop_box?: CropBox;
  landmarks?: Record<string, [number, number]>;
  face_crop_path?: string;
  embedding_model?: string;
  embedding_dimensions?: number;
  disclaimer?: string;
  message?: string;
  error?: string;
}

export interface WebSearchResult {
  status: string;
  best_match?: {
    match_type: string;
    verification_level: string;
    title?: string | null;
    url?: string | null;
    source?: string | null;
    thumbnail?: string | null;
    visual_match_count?: number;
  };
  public_face_match?: {
    similarity?: number | null;
    is_match?: boolean;
    title?: string | null;
    source?: string | null;
    url?: string | null;
  } | null;
  third_party_disclosure: string;
  error?: string;
}

export interface ManifestAcquisition {
  acquired_at_utc: string;
  filename: string;
  file_size_bytes: number;
  mime_type: string;
  format: string;
  dimensions: {
    width: number;
    height: number;
  };
}

export interface ToolVersions {
  facechain_forensics: string;
  opencv: string;
  pillow: string;
  python: string;
  models: {
    face_detector: string;
    face_recognizer: string;
  };
}

export interface EvidenceManifest {
  version: string;
  evidence_id: string;
  original_file_hash: string;
  acquisition: ManifestAcquisition;
  analysis_hash: string;
  tool_versions: ToolVersions;
  timestamps: {
    acquired_at: string;
    analyzed_at: string;
    manifest_created_at: string;
  };
}

export interface EvidenceRecord {
  id: string;
  filename: string;
  file_size: number;
  mime_type: string;
  original_hash: string;
  original_path: string;
  working_path: string;
  ela_path?: string | null;
  face_crop_path?: string | null;
  created_at: string;
  analyzed_at?: string | null;
  status: 'acquired' | 'analyzed' | 'error';
  metadata?: ExtractedMetadata | null;
  image_analysis?: ImageAnalysis | null;
  face_analysis?: FaceAnalysis | null;
  web_search?: WebSearchResult | null;
  manifest?: EvidenceManifest | null;
  manifest_hash?: string | null;
  report_path?: string | null;
  blockchain_status: 'unanchored' | 'pending' | 'confirmed' | 'failed' | 'revoked' | 'outdated';
  blockchain_tx_hash?: string | null;
  blockchain_block_number?: number | null;
  blockchain_anchored_at?: string | null;
  blockchain_error?: string | null;
}

export interface LocalIntegrityResult {
  verified: boolean;
  status: 'VERIFIED' | 'TAMPERED';
  file_hash_match: boolean;
  manifest_hash_match: boolean;
  analysis_hash_match?: boolean;
  original_file_hash: string;
  actual_file_hash: string;
  expected_manifest_hash: string;
  recomputed_manifest_hash: string;
  reason?: string;
}

export interface BlockchainVerificationResult {
  verified: boolean;
  status: 'VERIFIED' | 'TAMPERED' | 'ERROR' | 'UNANCHORED' | 'OUTDATED_ANCHOR' | 'MALFORMED' | 'NOT_FOUND' | string;
  manifest_hash?: string;
  on_chain_hash?: string;
  transaction_hash?: string;
  reason?: string;
}

export type IntegrityBadgeStatus = 'passed' | 'failed' | 'warning' | 'unverified';

export interface IntegrityCheckItem {
  status: IntegrityBadgeStatus;
  matched?: boolean;
  expected_hash?: string;
  actual_hash?: string;
  state?: string;
  transaction_hash?: string | null;
  on_chain_hash?: string | null;
  manifest_hash?: string;
  error?: string | null;
}

export interface IntegrityVerificationChecks {
  local_file: IntegrityCheckItem;
  manifest_digest: IntegrityCheckItem;
  blockchain_record: IntegrityCheckItem;
}

export interface IntegrityVerificationResponse {
  evidence_id: string;
  overall_status: 'VERIFIED' | 'TAMPERED' | 'BLOCKCHAIN_MISMATCH' | 'BLOCKCHAIN_ERROR' | string;
  local_integrity: LocalIntegrityResult;
  blockchain_verification?: BlockchainVerificationResult | null;
  checks?: IntegrityVerificationChecks;
  failure_reasons?: string[];
  verified_at?: string;
}

export interface SystemHealth {
  status: string;
  service: string;
  version: string;
  blockchain: {
    enabled: boolean;
    network: string;
  };
  models: {
    yunet_detector: boolean;
    sface_recognizer: boolean;
  };
}
