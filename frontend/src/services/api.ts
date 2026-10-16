import type {
  EvidenceRecord,
  IntegrityVerificationResponse,
  SystemHealth,
} from '../types/forensics';

const API_BASE = `${(import.meta.env.VITE_API_BASE_URL || (import.meta.env.MODE === 'test' ? '' : 'https://facechain-verifier-tzqr.onrender.com')).replace(/\/+$/, '')}/api/v1`;

export async function fetchHealth(): Promise<SystemHealth> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) {
    throw new Error(`Health check failed (${res.status})`);
  }
  return res.json();
}

export async function fetchEvidenceList(limit = 50, offset = 0): Promise<EvidenceRecord[]> {
  const res = await fetch(`${API_BASE}/evidence?limit=${limit}&offset=${offset}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch evidence list (${res.status})`);
  }
  return res.json();
}

export async function fetchEvidence(evidenceId: string): Promise<EvidenceRecord> {
  const res = await fetch(`${API_BASE}/evidence/${encodeURIComponent(evidenceId)}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to fetch evidence.' }));
    throw new Error(err.detail || `Error ${res.status}`);
  }
  return res.json();
}

export async function uploadEvidence(file: File): Promise<EvidenceRecord> {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/evidence`, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to upload file.' }));
    throw new Error(err.detail || `Upload failed with status ${res.status}`);
  }

  return res.json();
}

export interface AnalyzeOptions {
  include_face_analysis?: boolean;
  include_web_search?: boolean;
  anchor_blockchain?: boolean;
}

export async function analyzeEvidence(
  evidenceId: string,
  options: AnalyzeOptions = {}
): Promise<EvidenceRecord> {
  const res = await fetch(`${API_BASE}/evidence/${encodeURIComponent(evidenceId)}/analyze`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      include_face_analysis: options.include_face_analysis ?? true,
      include_web_search: options.include_web_search ?? false,
      anchor_blockchain: options.anchor_blockchain ?? false,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Forensic analysis failed.' }));
    throw new Error(err.detail || `Analysis failed (${res.status})`);
  }

  return res.json();
}

export async function verifyEvidence(evidenceId: string): Promise<IntegrityVerificationResponse> {
  const res = await fetch(`${API_BASE}/evidence/${encodeURIComponent(evidenceId)}/verify`, {
    method: 'POST',
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Integrity verification failed.' }));
    throw new Error(err.detail || `Verification failed (${res.status})`);
  }

  return res.json();
}

export async function anchorEvidence(evidenceId: string): Promise<EvidenceRecord> {
  const res = await fetch(`${API_BASE}/evidence/${encodeURIComponent(evidenceId)}/anchor`, {
    method: 'POST',
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Blockchain anchoring failed.' }));
    throw new Error(err.detail || `Anchoring failed (${res.status})`);
  }

  return res.json();
}

export function getEvidenceFileUrl(
  evidenceId: string,
  fileType: 'original' | 'working' | 'ela' | 'face_crop' | 'report'
): string {
  return `${API_BASE}/evidence/${encodeURIComponent(evidenceId)}/files/${fileType}`;
}

export async function fetchReport(evidenceId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/evidence/${encodeURIComponent(evidenceId)}/report`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Failed to fetch report.' }));
    throw new Error(err.detail || `Report fetch failed (${res.status})`);
  }
  return res.json();
}

export function getReportDownloadUrl(
  evidenceId: string,
  format?: 'json' | 'html' | 'pdf'
): string {
  if (format) {
    return `${API_BASE}/evidence/${encodeURIComponent(evidenceId)}/report?format=${format}&download=true`;
  }
  return `${API_BASE}/evidence/${encodeURIComponent(evidenceId)}/report?download=true`;
}

export async function downloadReportFile(
  evidenceId: string,
  format: 'json' | 'html' | 'pdf'
): Promise<void> {
  const url = getReportDownloadUrl(evidenceId, format);
  const res = await fetch(url);

  if (!res.ok) {
    let errorDetail = `Failed to download ${format.toUpperCase()} report (HTTP ${res.status})`;
    try {
      const err = await res.json();
      if (err?.detail) {
        errorDetail = err.detail;
      }
    } catch {
      // ignore non-json errors
    }
    throw new Error(errorDetail);
  }

  // Parse filename from Content-Disposition header if available
  let filename = `facechain_forensics_report_${evidenceId}.${format}`;
  const disposition = res.headers.get('content-disposition');
  if (disposition && disposition.includes('filename=')) {
    const match = disposition.match(/filename="?([^";]+)"?/i);
    if (match && match[1]) {
      filename = match[1].trim();
    }
  }

  const blob = await res.blob();
  const blobUrl = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.style.display = 'none';
  a.href = blobUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(blobUrl);
}
