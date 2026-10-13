import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Navbar } from '../components/Navbar';
import { EvidenceList } from '../components/EvidenceList';
import { EvidenceUpload } from '../components/EvidenceUpload';
import { getEvidenceFileUrl, getReportDownloadUrl } from '../services/api';
import type { EvidenceRecord, SystemHealth } from '../types/forensics';

describe('Navbar Component', () => {
  it('renders branding and status badges', () => {
    const health: SystemHealth = {
      status: 'healthy',
      service: 'FaceChain Forensics API',
      version: '1.0.0',
      blockchain: { enabled: true, network: 'Ethereum Sepolia' },
      models: { yunet_detector: true, sface_recognizer: true },
    };

    render(<Navbar health={health} totalEvidenceCount={5} />);
    expect(screen.getByText('FaceChain Forensics')).toBeDefined();
    expect(screen.getByText('5 Items')).toBeDefined();
    expect(screen.getByText('Sepolia Active')).toBeDefined();
  });

  it('renders disabled status when blockchain is not configured', () => {
    const health: SystemHealth = {
      status: 'healthy',
      service: 'FaceChain Forensics API',
      version: '1.0.0',
      blockchain: { enabled: false, network: 'Ethereum Sepolia' },
      models: { yunet_detector: true, sface_recognizer: true },
    };

    render(<Navbar health={health} totalEvidenceCount={0} />);
    expect(screen.getByText('Sepolia Disabled')).toBeDefined();
  });
});

describe('EvidenceList Component', () => {
  it('renders empty state when list is empty', () => {
    const onSelect = vi.fn();
    const onNewUpload = vi.fn();
    render(
      <EvidenceList
        evidenceList={[]}
        selectedId={null}
        onSelect={onSelect}
        onNewUploadClick={onNewUpload}
      />
    );
    expect(screen.getByText('No Evidence Acquired Yet')).toBeDefined();
  });

  it('renders evidence records with hashes and status', () => {
    const sampleRecord: EvidenceRecord = {
      id: 'ev_test123',
      filename: 'sample_photo.jpg',
      file_size: 45000,
      mime_type: 'image/jpeg',
      original_hash: 'abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890',
      original_path: 'storage/original.jpg',
      working_path: 'storage/working.jpg',
      created_at: new Date().toISOString(),
      status: 'acquired',
      blockchain_status: 'unanchored',
    };

    render(
      <EvidenceList
        evidenceList={[sampleRecord]}
        selectedId={null}
        onSelect={vi.fn()}
        onNewUploadClick={vi.fn()}
      />
    );

    expect(screen.getByText('ev_test123')).toBeDefined();
    expect(screen.getByText('sample_photo.jpg')).toBeDefined();
    expect(screen.getByText('Acquired')).toBeDefined();
  });
});

describe('EvidenceUpload Component', () => {
  it('renders drag and drop zone with supported formats', () => {
    render(<EvidenceUpload onUploadSuccess={vi.fn()} />);
    expect(screen.getByText('Drag & Drop Evidence Image Here')).toBeDefined();
    expect(screen.getByText('JPEG (.jpg, .jpeg)')).toBeDefined();
    expect(screen.getByText('PNG (.png)')).toBeDefined();
    expect(screen.getByText('WebP (.webp)')).toBeDefined();
  });
});

describe('API URL Builders', () => {
  it('builds secure encoded file URLs', () => {
    const url = getEvidenceFileUrl('ev_123', 'ela');
    expect(url).toBe('/api/v1/evidence/ev_123/files/ela');

    const downloadUrl = getReportDownloadUrl('ev_123');
    expect(downloadUrl).toBe('/api/v1/evidence/ev_123/report?download=true');
  });
});
