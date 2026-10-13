import React from 'react';
import {
  FileText,
  Clock,
  Layers,
  ChevronRight,
} from 'lucide-react';
import type { EvidenceRecord } from '../types/forensics';

interface EvidenceListProps {
  evidenceList: EvidenceRecord[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNewUploadClick: () => void;
}

export const EvidenceList: React.FC<EvidenceListProps> = ({
  evidenceList,
  selectedId,
  onSelect,
  onNewUploadClick,
}) => {
  if (evidenceList.length === 0) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '60px 20px' }}>
        <Layers size={48} style={{ color: 'var(--text-muted)', margin: '0 auto 16px auto' }} />
        <h3 style={{ fontSize: '1.2rem', marginBottom: '8px' }}>No Evidence Acquired Yet</h3>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '24px', maxWidth: '440px', margin: '0 auto 24px auto' }}>
          Upload an image to start cryptographic hashing, metadata extraction, Error Level Analysis, and face biometric checks.
        </p>
        <button className="btn btn-primary" onClick={onNewUploadClick}>
          Acquire First Evidence
        </button>
      </div>
    );
  }

  const getStatusBadge = (rec: EvidenceRecord) => {
    if (rec.status === 'acquired') {
      return <span className="badge badge-cyan">Acquired</span>;
    }
    if (rec.blockchain_status === 'confirmed') {
      return <span className="badge badge-emerald">On-Chain Confirmed</span>;
    }
    if (rec.status === 'analyzed') {
      return <span className="badge badge-cyan">Manifest Built</span>;
    }
    return <span className="badge badge-neutral">{rec.status}</span>;
  };

  return (
    <div className="card">
      <div className="card-header">
        <h2 className="card-title">
          <FileText size={20} />
          <span>Evidence Registry</span>
          <span className="badge badge-neutral">{evidenceList.length} Items</span>
        </h2>
        <button className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: '0.8rem' }} onClick={onNewUploadClick}>
          + Upload New Image
        </button>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Evidence ID</th>
              <th>Filename</th>
              <th>Original SHA-256 Digest</th>
              <th>Format & Size</th>
              <th>Status</th>
              <th>Acquired (UTC)</th>
              <th style={{ textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {evidenceList.map((rec) => {
              const isSelected = rec.id === selectedId;
              const dateStr = new Date(rec.created_at).toLocaleString(undefined, {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
              });

              return (
                <tr
                  key={rec.id}
                  onClick={() => onSelect(rec.id)}
                  style={{
                    cursor: 'pointer',
                    background: isSelected ? 'var(--bg-surface-elevated)' : undefined,
                    borderLeft: isSelected ? '3px solid var(--accent-cyan)' : '3px solid transparent',
                  }}
                >
                  <td style={{ fontWeight: 600, color: 'var(--accent-cyan)' }}>
                    <span className="mono">{rec.id}</span>
                  </td>
                  <td style={{ fontWeight: 500, maxWidth: '180px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {rec.filename}
                  </td>
                  <td>
                    <span className="mono" style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                      {rec.original_hash.slice(0, 10)}...{rec.original_hash.slice(-8)}
                    </span>
                  </td>
                  <td style={{ color: 'var(--text-secondary)', fontSize: '0.82rem' }}>
                    {rec.mime_type.split('/')[1]?.toUpperCase()} &bull; {(rec.file_size / 1024).toFixed(1)} KB
                  </td>
                  <td>{getStatusBadge(rec)}</td>
                  <td style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                      <Clock size={12} />
                      {dateStr}
                    </span>
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <button
                      className="btn btn-secondary"
                      style={{ padding: '6px 12px', fontSize: '0.78rem' }}
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelect(rec.id);
                      }}
                    >
                      <span>Inspect</span>
                      <ChevronRight size={14} />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
