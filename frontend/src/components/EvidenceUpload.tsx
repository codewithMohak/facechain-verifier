import React, { useState, useRef } from 'react';
import { UploadCloud, Image as ImageIcon, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { uploadEvidence } from '../services/api';
import type { EvidenceRecord } from '../types/forensics';

interface EvidenceUploadProps {
  onUploadSuccess: (evidence: EvidenceRecord) => void;
}

const SUPPORTED_EXTS = ['.jpg', '.jpeg', '.png', '.webp'];
const MAX_SIZE_MB = 20;

export const EvidenceUpload: React.FC<EvidenceUploadProps> = ({ onUploadSuccess }) => {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFile = (file: File) => {
    setValidationError(null);
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();

    if (!SUPPORTED_EXTS.includes(ext)) {
      setValidationError(`Unsupported file type '${ext}'. Please upload JPEG, PNG, or WebP.`);
      setSelectedFile(null);
      setPreviewUrl(null);
      return;
    }

    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      setValidationError(`File size (${(file.size / (1024 * 1024)).toFixed(1)} MB) exceeds ${MAX_SIZE_MB} MB limit.`);
      setSelectedFile(null);
      setPreviewUrl(null);
      return;
    }

    setSelectedFile(file);
    const objectUrl = URL.createObjectURL(file);
    setPreviewUrl(objectUrl);
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const handleUploadSubmit = async () => {
    if (!selectedFile) return;

    setUploading(true);
    setValidationError(null);

    try {
      const record = await uploadEvidence(selectedFile);
      setSelectedFile(null);
      setPreviewUrl(null);
      onUploadSuccess(record);
    } catch (err: any) {
      setValidationError(err.message || 'Evidence upload failed.');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="card" style={{ maxWidth: '780px', margin: '0 auto' }}>
      <div className="card-header">
        <h2 className="card-title">
          <UploadCloud size={20} className="text-cyan" />
          Acquire Digital Image Evidence
        </h2>
        <span className="badge badge-neutral">Standard Acquisition Protocol</span>
      </div>

      {validationError && (
        <div className="callout callout-danger">
          <AlertCircle size={18} style={{ flexShrink: 0 }} />
          <div>
            <strong>Validation Error:</strong> {validationError}
          </div>
        </div>
      )}

      <div
        className={`dropzone ${dragActive ? 'drag-active' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          style={{ display: 'none' }}
          onChange={handleChange}
        />

        {previewUrl ? (
          <div style={{ textAlign: 'center' }}>
            <img
              src={previewUrl}
              alt="Evidence Preview"
              style={{
                maxHeight: '260px',
                maxWidth: '100%',
                borderRadius: '8px',
                border: '1px solid var(--border-strong)',
                marginBottom: '16px',
                boxShadow: 'var(--shadow-md)',
              }}
            />
            <div style={{ fontSize: '0.95rem', fontWeight: 600 }}>{selectedFile?.name}</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
              {selectedFile ? (selectedFile.size / 1024).toFixed(1) : 0} KB &bull;{' '}
              {selectedFile?.type || 'Image'}
            </div>
          </div>
        ) : (
          <>
            <div className="dropzone-icon">
              <ImageIcon size={52} />
            </div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '6px' }}>
              Drag & Drop Evidence Image Here
            </h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', marginBottom: '16px' }}>
              or click to browse your local filesystem
            </p>
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'center' }}>
              <span className="badge badge-neutral">JPEG (.jpg, .jpeg)</span>
              <span className="badge badge-neutral">PNG (.png)</span>
              <span className="badge badge-neutral">WebP (.webp)</span>
            </div>
            <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)', marginTop: '14px' }}>
              Max size: 20 MB &bull; File will be SHA-256 hashed and preserved unchanged
            </div>
          </>
        )}
      </div>

      {selectedFile && (
        <div style={{ marginTop: '20px', display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={(e) => {
              e.stopPropagation();
              setSelectedFile(null);
              setPreviewUrl(null);
              setValidationError(null);
            }}
            disabled={uploading}
          >
            Clear Selection
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={(e) => {
              e.stopPropagation();
              handleUploadSubmit();
            }}
            disabled={uploading}
          >
            {uploading ? (
              <>
                <Loader2 size={16} className="spinner" />
                <span>Hashing & Preserving...</span>
              </>
            ) : (
              <>
                <CheckCircle2 size={16} />
                <span>Acquire & Register Evidence</span>
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
};
