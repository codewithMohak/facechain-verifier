import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { EvidenceDetail } from '../components/EvidenceDetail';
import { downloadReportFile, getReportDownloadUrl } from '../services/api';
import type { EvidenceRecord, IntegrityVerificationResponse } from '../types/forensics';

const createMockEvidence = (overrides: Partial<EvidenceRecord> = {}): EvidenceRecord => ({
  id: 'ev_test_123',
  filename: 'evidence.jpg',
  file_size: 20480,
  mime_type: 'image/jpeg',
  original_hash: '1111111111111111111111111111111111111111111111111111111111111111',
  original_path: '/storage/ev_test_123/evidence.jpg',
  working_path: '/storage/ev_test_123/working.jpg',
  status: 'analyzed',
  manifest_hash: '2222222222222222222222222222222222222222222222222222222222222222',
  manifest: {
    version: '1.0',
    evidence_id: 'ev_test_123',
    original_file_hash: '1111111111111111111111111111111111111111111111111111111111111111',
    acquisition: {
      acquired_at_utc: '2026-10-13T12:00:00Z',
      filename: 'evidence.jpg',
      file_size_bytes: 20480,
      mime_type: 'image/jpeg',
      format: 'JPEG',
      dimensions: { width: 800, height: 600 },
    },
    analysis_hash: '3333333333333333333333333333333333333333333333333333333333333333',
    tool_versions: {
      facechain_forensics: '1.0.0',
      opencv: '5.0.0',
      pillow: '12.3.0',
      python: '3.13',
      models: { face_detector: 'yunet', face_recognizer: 'sface' },
    },
    timestamps: {
      acquired_at: '2026-10-13T12:00:00Z',
      analyzed_at: '2026-10-13T12:05:00Z',
      manifest_created_at: '2026-10-13T12:05:01Z',
    },
  },
  report_path: '/storage/ev_test_123/report.json',
  blockchain_status: 'confirmed',
  blockchain_tx_hash: '0xabc1234567890abcdef1234567890abcdef1234567890abcdef1234567890',
  blockchain_block_number: 1234567,
  blockchain_anchored_at: '2026-10-13T12:10:00Z',
  created_at: '2026-10-13T12:00:00Z',
  ...overrides,
});

describe('Integrity Display & Visual Indicators', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders unverified state as neutral gray and NEVER defaults to green', () => {
    const evidence = createMockEvidence();
    render(<EvidenceDetail evidence={evidence} onRefresh={vi.fn()} />);

    // Header badge must be "Not Verified" and neutral gray
    const notVerifiedBadge = screen.getByText('Not Verified');
    expect(notVerifiedBadge).toBeDefined();
    expect(notVerifiedBadge.className).toContain('badge-neutral');
    expect(notVerifiedBadge.className).not.toContain('badge-emerald');
  });

  it('displays green ONLY when all 3 checks genuinely pass', async () => {
    const evidence = createMockEvidence();
    const mockSuccessResponse: IntegrityVerificationResponse = {
      evidence_id: 'ev_test_123',
      overall_status: 'VERIFIED',
      local_integrity: {
        verified: true,
        status: 'VERIFIED',
        file_hash_match: true,
        manifest_hash_match: true,
        original_file_hash: evidence.original_hash,
        actual_file_hash: evidence.original_hash,
        expected_manifest_hash: evidence.manifest_hash!,
        recomputed_manifest_hash: evidence.manifest_hash!,
      },
      blockchain_verification: {
        verified: true,
        status: 'VERIFIED',
        manifest_hash: evidence.manifest_hash!,
        on_chain_hash: evidence.manifest_hash!,
        transaction_hash: evidence.blockchain_tx_hash!,
      },
    };

    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/verify')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockSuccessResponse),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve(evidence) });
    });

    render(<EvidenceDetail evidence={evidence} onRefresh={vi.fn()} />);

    const verifyBtn = screen.getByRole('button', { name: /verify integrity/i });
    fireEvent.click(verifyBtn);

    await waitFor(() => {
      expect(screen.getAllByText('Fully Verified').length).toBeGreaterThanOrEqual(1);
    });

    const successBadge = screen.getAllByText('Fully Verified')[0];
    expect(successBadge.className).toContain('badge-emerald');
    expect(screen.getByText(/CRYPTOGRAPHIC INTEGRITY FULLY VERIFIED/i)).toBeDefined();
  });

  it('renders red badge and warning when local file hash is mismatched (tamper detected)', async () => {
    const evidence = createMockEvidence();
    const mockTamperResponse: IntegrityVerificationResponse = {
      evidence_id: 'ev_test_123',
      overall_status: 'TAMPERED',
      local_integrity: {
        verified: false,
        status: 'TAMPERED',
        file_hash_match: false, // Mismatch!
        manifest_hash_match: true,
        original_file_hash: evidence.original_hash,
        actual_file_hash: '9999999999999999999999999999999999999999999999999999999999999999',
        expected_manifest_hash: evidence.manifest_hash!,
        recomputed_manifest_hash: evidence.manifest_hash!,
      },
      blockchain_verification: {
        verified: true,
        status: 'VERIFIED',
      },
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockTamperResponse),
    });

    render(<EvidenceDetail evidence={evidence} onRefresh={vi.fn()} />);
    const verifyBtn = screen.getByRole('button', { name: /verify integrity/i });
    fireEvent.click(verifyBtn);

    await waitFor(() => {
      expect(screen.getAllByText('Tamper Detected').length).toBeGreaterThanOrEqual(1);
    });

    const tamperBadge = screen.getAllByText('Tamper Detected')[0];
    expect(tamperBadge.className).toContain('badge-rose');
    expect(tamperBadge.className).not.toContain('badge-emerald');
    expect(screen.getByText(/EVIDENCE INTEGRITY FAILED/i)).toBeDefined();
    expect(screen.getByText(/Original file SHA-256 does not match manifest/i)).toBeDefined();
  });

  it('renders red badge when manifest digest is mismatched', async () => {
    const evidence = createMockEvidence();
    const mockManifestTamper: IntegrityVerificationResponse = {
      evidence_id: 'ev_test_123',
      overall_status: 'TAMPERED',
      local_integrity: {
        verified: false,
        status: 'TAMPERED',
        file_hash_match: true,
        manifest_hash_match: false, // Manifest mismatch!
        original_file_hash: evidence.original_hash,
        actual_file_hash: evidence.original_hash,
        expected_manifest_hash: evidence.manifest_hash!,
        recomputed_manifest_hash: '8888888888888888888888888888888888888888888888888888888888888888',
      },
      blockchain_verification: null,
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockManifestTamper),
    });

    render(<EvidenceDetail evidence={evidence} onRefresh={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /verify integrity/i }));

    await waitFor(() => {
      expect(screen.getAllByText('Tamper Detected').length).toBeGreaterThanOrEqual(1);
    });

    const badge = screen.getAllByText('Tamper Detected')[0];
    expect(badge.className).toContain('badge-rose');
    expect(screen.getByText(/Manifest canonical digest mismatch/i)).toBeDefined();
  });

  it('renders amber badge when blockchain verification encounters RPC error', async () => {
    const evidence = createMockEvidence();
    const mockRpcError: IntegrityVerificationResponse = {
      evidence_id: 'ev_test_123',
      overall_status: 'BLOCKCHAIN_ERROR',
      local_integrity: {
        verified: true,
        status: 'VERIFIED',
        file_hash_match: true,
        manifest_hash_match: true,
        original_file_hash: evidence.original_hash,
        actual_file_hash: evidence.original_hash,
        expected_manifest_hash: evidence.manifest_hash!,
        recomputed_manifest_hash: evidence.manifest_hash!,
      },
      blockchain_verification: {
        verified: false,
        status: 'ERROR',
        reason: 'Sepolia RPC node connection timeout',
      },
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockRpcError),
    });

    render(<EvidenceDetail evidence={evidence} onRefresh={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /verify integrity/i }));

    await waitFor(() => {
      expect(screen.getAllByText(/Inconclusive \(RPC Error\)/i).length).toBeGreaterThanOrEqual(1);
    });

    const badge = screen.getAllByText(/Inconclusive \(RPC Error\)/i)[0];
    expect(badge.className).toContain('badge-amber');
    expect(badge.className).not.toContain('badge-emerald');
    expect(screen.getByText(/INTEGRITY INCONCLUSIVE: BLOCKCHAIN RPC ERROR/i)).toBeDefined();
  });

  it('renders amber badge when unanchored rather than falsely claiming on-chain verification', async () => {
    const unanchoredEvidence = createMockEvidence({
      blockchain_status: 'unanchored',
      blockchain_tx_hash: null,
    });
    const mockUnanchored: IntegrityVerificationResponse = {
      evidence_id: 'ev_test_123',
      overall_status: 'VERIFIED',
      local_integrity: {
        verified: true,
        status: 'VERIFIED',
        file_hash_match: true,
        manifest_hash_match: true,
        original_file_hash: unanchoredEvidence.original_hash,
        actual_file_hash: unanchoredEvidence.original_hash,
        expected_manifest_hash: unanchoredEvidence.manifest_hash!,
        recomputed_manifest_hash: unanchoredEvidence.manifest_hash!,
      },
      blockchain_verification: {
        verified: false,
        status: 'UNANCHORED',
      },
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockUnanchored),
    });

    render(<EvidenceDetail evidence={unanchoredEvidence} onRefresh={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /verify integrity/i }));

    await waitFor(() => {
      expect(screen.getAllByText('Verified (Local Only)').length).toBeGreaterThanOrEqual(1);
    });

    const badge = screen.getAllByText('Verified (Local Only)')[0];
    expect(badge.className).toContain('badge-amber');
    expect(badge.className).not.toContain('badge-emerald');
  });

  it('handles network / HTTP errors gracefully and shows error message without defaulting to green', async () => {
    const evidence = createMockEvidence();
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ detail: 'Database connection failed during verification' }),
    });

    render(<EvidenceDetail evidence={evidence} onRefresh={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /verify integrity/i }));

    await waitFor(() => {
      expect(screen.getAllByText('Verification Error').length).toBeGreaterThanOrEqual(1);
    });

    const errorBadge = screen.getAllByText('Verification Error')[0];
    expect(errorBadge.className).toContain('badge-rose');
    expect(errorBadge.className).not.toContain('badge-emerald');
    expect(screen.getAllByText(/Database connection failed during verification/i).length).toBeGreaterThanOrEqual(1);
  });
});

describe('Report Download Options & Functionality', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('constructs correct download URLs for JSON, HTML, and PDF formats', () => {
    expect(getReportDownloadUrl('ev_99', 'json')).toBe('/api/v1/evidence/ev_99/report?format=json&download=true');
    expect(getReportDownloadUrl('ev_99', 'html')).toBe('/api/v1/evidence/ev_99/report?format=html&download=true');
    expect(getReportDownloadUrl('ev_99', 'pdf')).toBe('/api/v1/evidence/ev_99/report?format=pdf&download=true');
  });

  it('downloadReportFile fetches blob, triggers download, and revokes object URL', async () => {
    const fakeBlob = new Blob(['test report data'], { type: 'application/pdf' });
    const createObjectURLMock = vi.fn().mockReturnValue('blob:http://localhost/test-blob');
    const revokeObjectURLMock = vi.fn();
    window.URL.createObjectURL = createObjectURLMock;
    window.URL.revokeObjectURL = revokeObjectURLMock;

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: {
        get: (h: string) => (h === 'content-disposition' ? 'attachment; filename="facechain_report_ev_99.pdf"' : null),
      },
      blob: () => Promise.resolve(fakeBlob),
    });

    await downloadReportFile('ev_99', 'pdf');

    expect(globalThis.fetch).toHaveBeenCalledWith('/api/v1/evidence/ev_99/report?format=pdf&download=true');
    expect(createObjectURLMock).toHaveBeenCalledWith(fakeBlob);
    expect(revokeObjectURLMock).toHaveBeenCalledWith('blob:http://localhost/test-blob');
  });

  it('downloadReportFile throws clean error when report is missing / HTTP 400', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: () => Promise.resolve({ detail: 'Forensic report has not been generated yet. Run analysis first.' }),
    });

    await expect(downloadReportFile('ev_unready', 'html')).rejects.toThrow(
      'Forensic report has not been generated yet. Run analysis first.'
    );
  });

  it('renders all 3 download options in the Report tab', () => {
    const evidence = createMockEvidence();
    render(<EvidenceDetail evidence={evidence} onRefresh={vi.fn()} />);

    // Switch to Report tab
    const reportTab = screen.getByRole('button', { name: /report/i });
    fireEvent.click(reportTab);

    expect(screen.getByText('Download Forensic Reports')).toBeDefined();
    expect(screen.getByRole('button', { name: /download json report/i })).toBeDefined();
    expect(screen.getByRole('button', { name: /download html report/i })).toBeDefined();
    expect(screen.getByRole('button', { name: /download pdf report/i })).toBeDefined();
  });
});
