import React, { useState } from 'react';
import {
  ShieldCheck,
  Play,
  RotateCw,
  Link as LinkIcon,
  Download,
  Eye,
  FileCode,
  FileText,
  Camera,
  Compass,
  UserCheck,
  AlertTriangle,
  Info,
  CheckCircle2,
  XCircle,
  Copy,
  ExternalLink,
} from 'lucide-react';
import type {
  EvidenceRecord,
  IntegrityVerificationResponse,
} from '../types/forensics';
import {
  analyzeEvidence,
  verifyEvidence,
  anchorEvidence,
  getEvidenceFileUrl,
  downloadReportFile,
} from '../services/api';

interface EvidenceDetailProps {
  evidence: EvidenceRecord;
  onRefresh: (updated: EvidenceRecord) => void;
}

export const EvidenceDetail: React.FC<EvidenceDetailProps> = ({ evidence, onRefresh }) => {
  const [activeTab, setActiveTab] = useState<'image' | 'metadata' | 'face' | 'integrity' | 'report'>('image');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [isAnchoring, setIsAnchoring] = useState(false);
  const [verificationResult, setVerificationResult] = useState<IntegrityVerificationResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  // Report download states
  const [downloadingFormat, setDownloadingFormat] = useState<'json' | 'html' | 'pdf' | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  // Analysis options modal/state
  const [showAnalysisModal, setShowAnalysisModal] = useState(false);
  const [includeFace, setIncludeFace] = useState(true);
  const [includeWebSearch, setIncludeWebSearch] = useState(false);
  const [anchorOnAnalysis, setAnchorOnAnalysis] = useState(false);

  const copyToClipboard = (text: string, fieldName: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(fieldName);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const handleDownload = async (format: 'json' | 'html' | 'pdf') => {
    if (downloadingFormat) return; // Prevent duplicate requests
    setDownloadingFormat(format);
    setDownloadError(null);
    try {
      await downloadReportFile(evidence.id, format);
    } catch (err: any) {
      setDownloadError(err.message || `Failed to download ${format.toUpperCase()} report.`);
    } finally {
      setDownloadingFormat(null);
    }
  };

  const handleRunAnalysis = async () => {
    setIsAnalyzing(true);
    setErrorMessage(null);
    setShowAnalysisModal(false);
    try {
      const updated = await analyzeEvidence(evidence.id, {
        include_face_analysis: includeFace,
        include_web_search: includeWebSearch,
        anchor_blockchain: anchorOnAnalysis,
      });
      onRefresh(updated);
    } catch (err: any) {
      setErrorMessage(err.message || 'Analysis failed.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleVerifyIntegrity = async () => {
    if (isVerifying) return; // Prevent concurrent calls
    setIsVerifying(true);
    setErrorMessage(null);
    try {
      const res = await verifyEvidence(evidence.id);
      setVerificationResult(res);
      // Refresh record from backend to synchronize any state
      try {
        const refreshed = await analyzeEvidence(evidence.id);
        onRefresh(refreshed);
      } catch {
        // non-blocking
      }
    } catch (err: any) {
      const msg = err.message || 'Verification check failed.';
      setErrorMessage(msg);
      // Explicit error result: NEVER default to green on error or exception
      setVerificationResult({
        evidence_id: evidence.id,
        overall_status: 'ERROR',
        local_integrity: {
          verified: false,
          status: 'TAMPERED',
          file_hash_match: false,
          manifest_hash_match: false,
          original_file_hash: evidence.original_hash,
          actual_file_hash: 'UNAVAILABLE (FAILED)',
          expected_manifest_hash: evidence.manifest_hash || 'UNAVAILABLE',
          recomputed_manifest_hash: 'UNAVAILABLE',
          reason: msg,
        },
        blockchain_verification: {
          verified: false,
          status: 'ERROR',
          reason: msg,
        },
        failure_reasons: [msg],
      });
    } finally {
      setIsVerifying(false);
    }
  };

  const handleAnchorBlockchain = async () => {
    setIsAnchoring(true);
    setErrorMessage(null);
    try {
      const updated = await anchorEvidence(evidence.id);
      onRefresh(updated);
    } catch (err: any) {
      setErrorMessage(err.message || 'Blockchain anchoring failed.');
    } finally {
      setIsAnchoring(false);
    }
  };

  // Explicit, rigorous integrity evaluation logic
  const getIntegrityEvaluation = () => {
    if (isVerifying) {
      return {
        overallBadgeClass: 'badge-cyan',
        overallBadgeText: 'Verifying...',
        calloutClass: 'callout-info',
        calloutIcon: <RotateCw size={20} className="spinner" style={{ flexShrink: 0 }} />,
        title: 'Cryptographic Verification In Progress',
        message: 'Recomputing original file SHA-256 digest, verifying canonical manifest hash, and querying Sepolia on-chain payload...',
        checks: {
          localFile: { status: 'unverified' as const, badgeText: 'VERIFYING...', badgeClass: 'badge-cyan', label: 'Recomputing SHA-256...' },
          manifestDigest: { status: 'unverified' as const, badgeText: 'VERIFYING...', badgeClass: 'badge-cyan', label: 'Verifying canonical digest...' },
          blockchain: { status: 'unverified' as const, badgeText: 'VERIFYING...', badgeClass: 'badge-cyan', label: 'Querying Sepolia RPC node...' },
        },
      };
    }

    if (!verificationResult) {
      const isAnchored = evidence.blockchain_status === 'confirmed';
      return {
        overallBadgeClass: 'badge-neutral',
        overallBadgeText: 'Not Verified',
        calloutClass: 'callout-info',
        calloutIcon: <Info size={20} style={{ flexShrink: 0 }} />,
        title: 'Live Integrity Verification Not Run',
        message: 'Evidence is analyzed, but live cryptographic integrity has not been verified in this session. Click "Verify Integrity" to validate local hashes and blockchain state.',
        checks: {
          localFile: {
            status: 'unverified' as const,
            badgeText: 'NOT CHECKED',
            badgeClass: 'badge-neutral',
            label: 'Original file SHA-256 has not been verified against manifest.',
          },
          manifestDigest: {
            status: 'unverified' as const,
            badgeText: 'NOT CHECKED',
            badgeClass: 'badge-neutral',
            label: 'Manifest canonical digest has not been recomputed.',
          },
          blockchain: {
            status: 'unverified' as const,
            badgeText: isAnchored ? 'ANCHORED (UNVERIFIED)' : 'UNANCHORED',
            badgeClass: isAnchored ? 'badge-neutral' : 'badge-amber',
            label: isAnchored
              ? 'Anchored on Sepolia; live on-chain payload verification has not been executed.'
              : 'Evidence manifest is not anchored to Ethereum Sepolia ledger.',
          },
        },
      };
    }

    const local = verificationResult.local_integrity;
    const bc = verificationResult.blockchain_verification;
    const isError = verificationResult.overall_status === 'ERROR';

    // 1. Local File Match
    let localFileStatus: 'passed' | 'failed' | 'unverified' = 'unverified';
    let localFileBadge = 'NOT CHECKED';
    let localFileClass = 'badge-neutral';
    let localFileLabel = '';

    if (isError) {
      localFileStatus = 'failed';
      localFileBadge = 'REQUEST FAILED';
      localFileClass = 'badge-rose';
      localFileLabel = local?.reason || 'Verification request failed with error.';
    } else if (local?.file_hash_match === true) {
      localFileStatus = 'passed';
      localFileBadge = 'MATCHED';
      localFileClass = 'badge-emerald';
      localFileLabel = 'Stored original file SHA-256 digest matches manifest original_file_hash exactly.';
    } else if (local?.file_hash_match === false) {
      localFileStatus = 'failed';
      localFileBadge = 'TAMPER DETECTED';
      localFileClass = 'badge-rose';
      localFileLabel = 'File content has been modified on disk! SHA-256 mismatch detected.';
    }

    // 2. Manifest Canonical Digest
    let manifestStatus: 'passed' | 'failed' | 'unverified' = 'unverified';
    let manifestBadge = 'NOT CHECKED';
    let manifestClass = 'badge-neutral';
    let manifestLabel = '';

    if (isError) {
      manifestStatus = 'failed';
      manifestBadge = 'REQUEST FAILED';
      manifestClass = 'badge-rose';
      manifestLabel = 'Manifest verification request failed.';
    } else if (local?.manifest_hash_match === true) {
      manifestStatus = 'passed';
      manifestBadge = 'MATCHED';
      manifestClass = 'badge-emerald';
      manifestLabel = 'Recomputed canonical manifest hash matches expected manifest digest.';
    } else if (local?.manifest_hash_match === false) {
      manifestStatus = 'failed';
      manifestBadge = 'DIGEST MISMATCH';
      manifestClass = 'badge-rose';
      manifestLabel = 'Canonical manifest hash recomputation failed! Manifest content was altered.';
    }

    // 3. Sepolia On-Chain Record
    let bcStatus: 'passed' | 'failed' | 'warning' | 'unverified' = 'unverified';
    let bcBadge = 'UNANCHORED';
    let bcClass = 'badge-amber';
    let bcLabel = '';

    if (isError) {
      bcStatus = 'warning';
      bcBadge = 'ERROR';
      bcClass = 'badge-amber';
      bcLabel = bc?.reason || 'Blockchain verification query failed.';
    } else if (!evidence.blockchain_tx_hash && (!bc || bc.status === 'UNANCHORED')) {
      bcStatus = 'warning';
      bcBadge = 'UNANCHORED';
      bcClass = 'badge-amber';
      bcLabel = 'Evidence manifest is not anchored to Sepolia ledger (off-chain analysis only).';
    } else if (bc?.verified === true) {
      bcStatus = 'passed';
      bcBadge = 'VERIFIED ON-CHAIN';
      bcClass = 'badge-emerald';
      bcLabel = 'Anchored payload on Ethereum Sepolia matches local manifest digest perfectly.';
    } else if (bc?.status === 'OUTDATED_ANCHOR') {
      bcStatus = 'failed';
      bcBadge = 'OUTDATED ANCHOR';
      bcClass = 'badge-rose';
      bcLabel = bc.reason || 'Sepolia transaction anchors an older manifest digest from a previous analysis run. Evidence was re-analyzed after anchoring.';
    } else if (bc?.status === 'MALFORMED') {
      bcStatus = 'failed';
      bcBadge = 'MALFORMED PAYLOAD';
      bcClass = 'badge-rose';
      bcLabel = bc.reason || 'On-chain transaction data does not contain a valid FaceChain hash payload.';
    } else if (bc?.status === 'NOT_FOUND') {
      bcStatus = 'failed';
      bcBadge = 'TX NOT FOUND';
      bcClass = 'badge-rose';
      bcLabel = bc.reason || 'Transaction could not be found on Ethereum Sepolia ledger.';
    } else if (bc?.status === 'TAMPERED') {
      bcStatus = 'failed';
      bcBadge = 'ON-CHAIN MISMATCH';
      bcClass = 'badge-rose';
      bcLabel = 'On-chain payload does not match local manifest digest! Ledger mismatch detected.';
    } else if (bc?.status === 'ERROR') {
      bcStatus = 'warning';
      bcBadge = 'RPC ERROR';
      bcClass = 'badge-amber';
      bcLabel = bc.reason || 'Sepolia RPC node error / network timeout.';
    } else if (evidence.blockchain_status === 'pending') {
      bcStatus = 'warning';
      bcBadge = 'PENDING TX';
      bcClass = 'badge-amber';
      bcLabel = 'Transaction submitted to Sepolia; waiting for block mining confirmation.';
    } else if (evidence.blockchain_status === 'outdated') {
      bcStatus = 'failed';
      bcBadge = 'OUTDATED ANCHOR';
      bcClass = 'badge-rose';
      bcLabel = 'Evidence was re-analyzed after blockchain anchoring. On-chain record anchors an older manifest digest.';
    }

    // Overall verdict
    if (isError) {
      return {
        overallBadgeClass: 'badge-rose',
        overallBadgeText: 'Verification Error',
        calloutClass: 'callout-danger',
        calloutIcon: <XCircle size={20} style={{ flexShrink: 0 }} />,
        title: 'VERIFICATION REQUEST FAILED',
        message: verificationResult.failure_reasons?.[0] || 'Verification request returned an error. Cannot confirm integrity.',
        checks: {
          localFile: { status: localFileStatus, badgeText: localFileBadge, badgeClass: localFileClass, label: localFileLabel },
          manifestDigest: { status: manifestStatus, badgeText: manifestBadge, badgeClass: manifestClass, label: manifestLabel },
          blockchain: { status: bcStatus, badgeText: bcBadge, badgeClass: bcClass, label: bcLabel },
        },
      };
    }

    const hasFailure = localFileStatus === 'failed' || manifestStatus === 'failed' || bcStatus === 'failed';
    if (hasFailure) {
      let failMsg = 'Integrity verification failed! One or more cryptographic checks detected discrepancies.';
      if (localFileStatus === 'failed') failMsg = 'Original file SHA-256 does not match manifest. Stored image is tampered or corrupted!';
      else if (manifestStatus === 'failed') failMsg = 'Manifest canonical digest mismatch! Stored manifest metadata has been tampered with.';
      else if (bc?.status === 'OUTDATED_ANCHOR') failMsg = bc.reason || 'On-chain Sepolia hash mismatch! Stored transaction payload anchors an outdated manifest digest from prior analysis.';
      else if (bc?.status === 'MALFORMED') failMsg = bc.reason || 'On-chain transaction payload is malformed or invalid.';
      else if (bc?.status === 'NOT_FOUND') failMsg = bc.reason || 'Recorded transaction was not found on Ethereum Sepolia network.';
      else if (bcStatus === 'failed') failMsg = 'On-chain Sepolia hash mismatch! Stored transaction payload does not match manifest digest.';

      return {
        overallBadgeClass: 'badge-rose',
        overallBadgeText: 'Tamper Detected',
        calloutClass: 'callout-danger',
        calloutIcon: <XCircle size={20} style={{ flexShrink: 0 }} />,
        title: 'EVIDENCE INTEGRITY FAILED',
        message: failMsg,
        checks: {
          localFile: { status: localFileStatus, badgeText: localFileBadge, badgeClass: localFileClass, label: localFileLabel },
          manifestDigest: { status: manifestStatus, badgeText: manifestBadge, badgeClass: manifestClass, label: manifestLabel },
          blockchain: { status: bcStatus, badgeText: bcBadge, badgeClass: bcClass, label: bcLabel },
        },
      };
    }

    if (localFileStatus === 'passed' && manifestStatus === 'passed') {
      if (bcStatus === 'passed') {
        return {
          overallBadgeClass: 'badge-emerald',
          overallBadgeText: 'Fully Verified',
          calloutClass: 'callout-success',
          calloutIcon: <CheckCircle2 size={20} style={{ flexShrink: 0 }} />,
          title: 'CRYPTOGRAPHIC INTEGRITY FULLY VERIFIED',
          message: 'All 3 integrity checks passed: Local file matches SHA-256, manifest digest is canonical, and Sepolia on-chain payload is verified.',
          checks: {
            localFile: { status: localFileStatus, badgeText: localFileBadge, badgeClass: localFileClass, label: localFileLabel },
            manifestDigest: { status: manifestStatus, badgeText: manifestBadge, badgeClass: manifestClass, label: manifestLabel },
            blockchain: { status: bcStatus, badgeText: bcBadge, badgeClass: bcClass, label: bcLabel },
          },
        };
      }

      if (bcStatus === 'warning') {
        const isRpc = bcBadge === 'RPC ERROR';
        return {
          overallBadgeClass: 'badge-amber',
          overallBadgeText: isRpc ? 'Inconclusive (RPC Error)' : 'Verified (Local Only)',
          calloutClass: 'callout-warning',
          calloutIcon: <AlertTriangle size={20} style={{ flexShrink: 0 }} />,
          title: isRpc ? 'INTEGRITY INCONCLUSIVE: BLOCKCHAIN RPC ERROR' : 'LOCAL INTEGRITY VERIFIED (UNANCHORED)',
          message: isRpc
            ? `Local file and manifest passed, but Sepolia RPC node could not verify the on-chain receipt: ${bcLabel}`
            : 'Original file SHA-256 and manifest canonical hash are verified locally. Evidence is not anchored to Sepolia ledger.',
          checks: {
            localFile: { status: localFileStatus, badgeText: localFileBadge, badgeClass: localFileClass, label: localFileLabel },
            manifestDigest: { status: manifestStatus, badgeText: manifestBadge, badgeClass: manifestClass, label: manifestLabel },
            blockchain: { status: bcStatus, badgeText: bcBadge, badgeClass: bcClass, label: bcLabel },
          },
        };
      }
    }

    return {
      overallBadgeClass: 'badge-amber',
      overallBadgeText: 'Inconclusive',
      calloutClass: 'callout-warning',
      calloutIcon: <AlertTriangle size={20} style={{ flexShrink: 0 }} />,
      title: 'INCONCLUSIVE INTEGRITY STATE',
      message: 'Verification could not conclusively determine evidence status.',
      checks: {
        localFile: { status: localFileStatus, badgeText: localFileBadge, badgeClass: localFileClass, label: localFileLabel },
        manifestDigest: { status: manifestStatus, badgeText: manifestBadge, badgeClass: manifestClass, label: manifestLabel },
        blockchain: { status: bcStatus, badgeText: bcBadge, badgeClass: bcClass, label: bcLabel },
      },
    };
  };

  const integrityEval = getIntegrityEvaluation();

  const originalUrl = getEvidenceFileUrl(evidence.id, 'original');
  const elaUrl = evidence.ela_path ? getEvidenceFileUrl(evidence.id, 'ela') : null;
  const faceCropUrl = evidence.face_crop_path ? getEvidenceFileUrl(evidence.id, 'face_crop') : null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Banner / Actions Card */}
      <div className="card" style={{ padding: '20px 24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
              <span className="mono" style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--accent-cyan)' }}>
                {evidence.id}
              </span>
              <span className="badge badge-neutral">{evidence.filename}</span>
              {evidence.status === 'analyzed' ? (
                <span className="badge badge-cyan">Manifest v1.0</span>
              ) : (
                <span className="badge badge-amber">Awaiting Analysis</span>
              )}
              <span className={`badge ${integrityEval.overallBadgeClass}`}>
                {integrityEval.overallBadgeText}
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', color: 'var(--text-secondary)', fontSize: '0.84rem' }}>
              <span>Size: {(evidence.file_size / 1024).toFixed(1)} KB</span>
              <span>&bull;</span>
              <span>Type: {evidence.mime_type}</span>
              <span>&bull;</span>
              <span>Acquired: {new Date(evidence.created_at).toUTCString()}</span>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
            <button
              className="btn btn-primary"
              onClick={() => setShowAnalysisModal(true)}
              disabled={isAnalyzing}
            >
              <Play size={16} />
              <span>{isAnalyzing ? 'Analyzing...' : 'Run Forensic Analysis'}</span>
            </button>

            {evidence.status === 'analyzed' && (
              <>
                <button
                  className="btn btn-secondary"
                  onClick={handleVerifyIntegrity}
                  disabled={isVerifying}
                  title="Verify file SHA-256, manifest digest, and Sepolia on-chain record"
                >
                  <RotateCw size={16} className={isVerifying ? 'spinner' : ''} />
                  <span>{isVerifying ? 'Verifying...' : 'Verify Integrity'}</span>
                </button>

                {evidence.blockchain_status !== 'confirmed' && (
                  <button
                    className="btn btn-secondary"
                    onClick={handleAnchorBlockchain}
                    disabled={isAnchoring}
                  >
                    <LinkIcon size={16} />
                    <span>{isAnchoring ? 'Submitting Tx...' : 'Anchor to Sepolia'}</span>
                  </button>
                )}

                <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                  <button
                    className="btn btn-secondary"
                    onClick={() => handleDownload('json')}
                    disabled={downloadingFormat !== null}
                    style={{ padding: '8px 12px', fontSize: '0.82rem' }}
                    title="Download JSON evidence report"
                  >
                    {downloadingFormat === 'json' ? <RotateCw size={14} className="spinner" /> : <Download size={14} />}
                    <span>JSON</span>
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={() => handleDownload('html')}
                    disabled={downloadingFormat !== null}
                    style={{ padding: '8px 12px', fontSize: '0.82rem' }}
                    title="Download HTML print-ready report"
                  >
                    {downloadingFormat === 'html' ? <RotateCw size={14} className="spinner" /> : <Download size={14} />}
                    <span>HTML</span>
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={() => handleDownload('pdf')}
                    disabled={downloadingFormat !== null}
                    style={{ padding: '8px 12px', fontSize: '0.82rem' }}
                    title="Download formal PDF document"
                  >
                    {downloadingFormat === 'pdf' ? <RotateCw size={14} className="spinner" /> : <Download size={14} />}
                    <span>PDF</span>
                  </button>
                </div>
              </>
            )}
          </div>
        </div>

        {/* SHA-256 Digest Bar */}
        <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid var(--border-subtle)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
            <div style={{ fontSize: '0.78rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
              Original File SHA-256 Hash
            </div>
            <button
              className="btn btn-secondary"
              style={{ padding: '4px 10px', fontSize: '0.75rem' }}
              onClick={() => copyToClipboard(evidence.original_hash, 'sha256')}
            >
              <Copy size={12} />
              <span>{copiedField === 'sha256' ? 'Copied!' : 'Copy Hash'}</span>
            </button>
          </div>
          <div className="mono-box" style={{ marginTop: '6px' }}>
            <span>{evidence.original_hash}</span>
          </div>
        </div>

        {/* Dynamic Integrity Status Alert */}
        {(verificationResult || isVerifying) && (
          <div
            className={`callout ${integrityEval.calloutClass}`}
            style={{ marginTop: '16px' }}
          >
            {integrityEval.calloutIcon}
            <div style={{ width: '100%' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px', marginBottom: '4px' }}>
                <span style={{ fontWeight: 700 }}>{integrityEval.title}</span>
                <span className={`badge ${integrityEval.overallBadgeClass}`}>{integrityEval.overallBadgeText}</span>
              </div>
              <div style={{ fontSize: '0.84rem', marginBottom: '10px', lineHeight: 1.45 }}>
                {integrityEval.message}
              </div>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', fontSize: '0.78rem' }}>
                <span className={`badge ${integrityEval.checks.localFile.badgeClass}`}>
                  1. Local File: {integrityEval.checks.localFile.badgeText}
                </span>
                <span className={`badge ${integrityEval.checks.manifestDigest.badgeClass}`}>
                  2. Manifest Digest: {integrityEval.checks.manifestDigest.badgeText}
                </span>
                <span className={`badge ${integrityEval.checks.blockchain.badgeClass}`}>
                  3. Sepolia Ledger: {integrityEval.checks.blockchain.badgeText}
                </span>
              </div>
            </div>
          </div>
        )}

        {errorMessage && (
          <div className="callout callout-danger" style={{ marginTop: '16px' }}>
            <AlertTriangle size={18} />
            <div>{errorMessage}</div>
          </div>
        )}

        {downloadError && (
          <div className="callout callout-danger" style={{ marginTop: '16px' }}>
            <AlertTriangle size={18} />
            <div>{downloadError}</div>
          </div>
        )}
      </div>

      {/* Navigation Tabs */}
      <div className="nav-tabs">
        <button
          className={`nav-tab-btn ${activeTab === 'image' ? 'active' : ''}`}
          onClick={() => setActiveTab('image')}
        >
          <Eye size={16} />
          <span>Image & ELA Analysis</span>
        </button>
        <button
          className={`nav-tab-btn ${activeTab === 'metadata' ? 'active' : ''}`}
          onClick={() => setActiveTab('metadata')}
        >
          <Camera size={16} />
          <span>EXIF & Metadata</span>
        </button>
        <button
          className={`nav-tab-btn ${activeTab === 'face' ? 'active' : ''}`}
          onClick={() => setActiveTab('face')}
        >
          <UserCheck size={16} />
          <span>Biometric & Face AI</span>
        </button>
        <button
          className={`nav-tab-btn ${activeTab === 'integrity' ? 'active' : ''}`}
          onClick={() => setActiveTab('integrity')}
        >
          <ShieldCheck size={16} />
          <span>Integrity & Blockchain</span>
        </button>
        <button
          className={`nav-tab-btn ${activeTab === 'report' ? 'active' : ''}`}
          onClick={() => setActiveTab('report')}
        >
          <FileCode size={16} />
          <span>Forensic Report</span>
        </button>
      </div>

      {/* TAB 1: Image & ELA Analysis */}
      {activeTab === 'image' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">
                <Eye size={18} />
                <span>Visual Manipulation Inspection</span>
              </h3>
              <div style={{ display: 'flex', gap: '8px' }}>
                <span className="badge badge-neutral">Format: {evidence.metadata?.format || evidence.mime_type.split('/')[1]?.toUpperCase()}</span>
                {evidence.image_analysis?.ela_applicable && (
                  <span className="badge badge-cyan">JPEG ELA Active (Quality: {evidence.image_analysis.parameters?.recompression_quality}%)</span>
                )}
              </div>
            </div>

            {/* Side-by-side Image & ELA */}
            <div className="image-comparison-container">
              <div className="image-pane">
                <div className="image-pane-label">Original Acquired Image</div>
                <div className="image-wrapper">
                  <img src={originalUrl} alt="Original Evidence" />
                </div>
              </div>

              <div className="image-pane">
                <div className="image-pane-label">
                  {evidence.image_analysis?.ela_applicable
                    ? 'Error Level Analysis (ELA) Visualization (15x Scale)'
                    : 'Format Inspection Output'}
                </div>
                <div className="image-wrapper">
                  {elaUrl ? (
                    <img src={elaUrl} alt="ELA Visualization" />
                  ) : (
                    <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
                      <Info size={36} style={{ margin: '0 auto 12px auto' }} />
                      <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                        {evidence.status === 'acquired'
                          ? 'Run forensic analysis to compute ELA visualization.'
                          : evidence.image_analysis?.methodology_note || 'ELA visualization not applicable for this format.'}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Forensic Disclaimer */}
            <div className="callout callout-warning" style={{ marginTop: '20px', marginBottom: 0 }}>
              <AlertTriangle size={18} style={{ flexShrink: 0 }} />
              <div>
                <strong>Forensic Investigative Notice:</strong> Error Level Analysis visualizes compression rate differences.
                Elevated error levels naturally occur around sharp geometric edges, text, high-frequency textures, and noise.
                Results are investigative indicators, NOT definitive or automated proof of manipulation.
              </div>
            </div>
          </div>

          {/* Observable Indicators & Statistics Grid */}
          {evidence.image_analysis && (
            <div className="grid-2">
              <div className="card">
                <div className="card-header">
                  <h4 className="card-title">Encoding & Compression Metrics</h4>
                </div>
                {evidence.image_analysis.statistics ? (
                  <table className="kv-table">
                    <tbody>
                      <tr>
                        <th>Mean Error Level</th>
                        <td className="mono">{evidence.image_analysis.statistics.mean_error}</td>
                      </tr>
                      <tr>
                        <th>Max Error Delta</th>
                        <td className="mono">{evidence.image_analysis.statistics.max_error}</td>
                      </tr>
                      <tr>
                        <th>Standard Deviation</th>
                        <td className="mono">{evidence.image_analysis.statistics.std_error}</td>
                      </tr>
                      <tr>
                        <th>High-Contrast Pixels</th>
                        <td className="mono">{evidence.image_analysis.statistics.high_contrast_percentage}%</td>
                      </tr>
                      <tr>
                        <th>Progressive Scan</th>
                        <td>{evidence.image_analysis.encoding_properties?.progressive ? 'Yes' : 'No (Baseline)'}</td>
                      </tr>
                      <tr>
                        <th>Chroma Subsampling</th>
                        <td>{evidence.image_analysis.encoding_properties?.subsampling}</td>
                      </tr>
                    </tbody>
                  </table>
                ) : evidence.image_analysis.lossless_analysis ? (
                  <table className="kv-table">
                    <tbody>
                      <tr>
                        <th>Color Mode</th>
                        <td>{evidence.image_analysis.lossless_analysis.color_mode}</td>
                      </tr>
                      <tr>
                        <th>Alpha Channel</th>
                        <td>{evidence.image_analysis.lossless_analysis.alpha_properties?.has_alpha_channel ? 'Present' : 'None'}</td>
                      </tr>
                      {evidence.image_analysis.lossless_analysis.alpha_properties?.semi_transparent_pct !== undefined && (
                        <tr>
                          <th>Semi-Transparent Gradients</th>
                          <td>{evidence.image_analysis.lossless_analysis.alpha_properties.semi_transparent_pct}%</td>
                        </tr>
                      )}
                      <tr>
                        <th>Chunks Detected</th>
                        <td>{evidence.image_analysis.lossless_analysis.png_chunks_detected?.join(', ') || 'Standard'}</td>
                      </tr>
                    </tbody>
                  </table>
                ) : (
                  <p style={{ color: 'var(--text-secondary)' }}>Format details extracted.</p>
                )}
              </div>

              <div className="card">
                <div className="card-header">
                  <h4 className="card-title">Observable Findings</h4>
                </div>
                {evidence.image_analysis.observable_indicators?.length ? (
                  <ul style={{ paddingLeft: '20px', display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '0.88rem' }}>
                    {evidence.image_analysis.observable_indicators.map((ind, idx) => (
                      <li key={idx} style={{ color: 'var(--text-secondary)' }}>
                        {ind}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p style={{ color: 'var(--text-muted)' }}>No notable anomalies observed.</p>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: Metadata */}
      {activeTab === 'metadata' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Missing / Suspicious Metadata Cards */}
          {evidence.metadata && (
            <div className="grid-2">
              <div className="card">
                <div className="card-header">
                  <h3 className="card-title">
                    <AlertTriangle size={18} style={{ color: 'var(--accent-amber)' }} />
                    <span>Suspicious Metadata Indicators</span>
                  </h3>
                  <span className={`badge ${evidence.metadata.suspicious_indicators.length > 0 ? 'badge-amber' : 'badge-emerald'}`}>
                    {evidence.metadata.suspicious_indicators.length} Flagged
                  </span>
                </div>
                {evidence.metadata.suspicious_indicators.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {evidence.metadata.suspicious_indicators.map((ind, i) => (
                      <div key={i} className="callout callout-warning" style={{ margin: 0 }}>
                        <div>
                          <strong>{ind.indicator}</strong>
                          <div style={{ marginTop: '4px', fontSize: '0.82rem' }}>{ind.detail}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem' }}>
                    No editing software strings or contradictory capture timestamps detected.
                  </p>
                )}
              </div>

              <div className="card">
                <div className="card-header">
                  <h3 className="card-title">
                    <Info size={18} />
                    <span>Unavailable Metadata Checklist</span>
                  </h3>
                  <span className="badge badge-neutral">
                    {evidence.metadata.missing_metadata.length} Absent Fields
                  </span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {evidence.metadata.missing_metadata.map((item, i) => (
                    <div key={i} style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '6px' }}>
                      <strong style={{ color: 'var(--text-primary)' }}>{item.field}:</strong> {item.detail}
                    </div>
                  ))}
                </div>
                <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)', marginTop: '12px' }}>
                  Note: Metadata stripping is routine across messaging apps (WhatsApp, Telegram) and social networks.
                </div>
              </div>
            </div>
          )}

          {/* Camera, Capture & GPS Table */}
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">
                <Camera size={18} />
                <span>Extracted EXIF & Photographic Parameters</span>
              </h3>
              <span className="badge badge-neutral">
                {evidence.metadata?.raw_exif_count || 0} Raw Tags
              </span>
            </div>

            {evidence.metadata ? (
              <div className="grid-2">
                <table className="kv-table">
                  <tbody>
                    <tr>
                      <th>Camera Make</th>
                      <td>{evidence.metadata.camera.make || 'Unavailable'}</td>
                    </tr>
                    <tr>
                      <th>Camera Model</th>
                      <td>{evidence.metadata.camera.model || 'Unavailable'}</td>
                    </tr>
                    <tr>
                      <th>Software</th>
                      <td>{evidence.metadata.camera.software || 'Unavailable'}</td>
                    </tr>
                    <tr>
                      <th>Lens Hardware</th>
                      <td>{evidence.metadata.camera.lens_model || 'Unavailable'}</td>
                    </tr>
                    <tr>
                      <th>Dimensions</th>
                      <td>{evidence.metadata.width} &times; {evidence.metadata.height} px</td>
                    </tr>
                    <tr>
                      <th>Color Space</th>
                      <td>{evidence.metadata.color_mode} {evidence.metadata.has_icc_profile ? '(ICC Profile Embedded)' : ''}</td>
                    </tr>
                  </tbody>
                </table>

                <table className="kv-table">
                  <tbody>
                    <tr>
                      <th>Capture Timestamp</th>
                      <td>{evidence.metadata.timestamps.original || 'Unavailable'}</td>
                    </tr>
                    <tr>
                      <th>Digitized Timestamp</th>
                      <td>{evidence.metadata.timestamps.digitized || 'Unavailable'}</td>
                    </tr>
                    <tr>
                      <th>Modified Timestamp</th>
                      <td>{evidence.metadata.timestamps.modified || 'Unavailable'}</td>
                    </tr>
                    <tr>
                      <th>Exposure Time</th>
                      <td>{evidence.metadata.capture_parameters.exposure_time ? `${evidence.metadata.capture_parameters.exposure_time} s` : 'Unavailable'}</td>
                    </tr>
                    <tr>
                      <th>F-Number (Aperture)</th>
                      <td>{evidence.metadata.capture_parameters.f_number ? `f/${evidence.metadata.capture_parameters.f_number}` : 'Unavailable'}</td>
                    </tr>
                    <tr>
                      <th>ISO Sensitivity</th>
                      <td>{evidence.metadata.capture_parameters.iso || 'Unavailable'}</td>
                    </tr>
                    <tr>
                      <th>GPS Coordinates</th>
                      <td>
                        {evidence.metadata.gps.available ? (
                          <a
                            href={evidence.metadata.gps.map_url || '#'}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{ color: 'var(--accent-cyan)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                          >
                            <span>{evidence.metadata.gps.latitude}, {evidence.metadata.gps.longitude}</span>
                            <ExternalLink size={13} />
                          </a>
                        ) : (
                          'Unavailable'
                        )}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            ) : (
              <p style={{ color: 'var(--text-muted)' }}>Run forensic analysis to extract metadata.</p>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: Face & AI Analysis */}
      {activeTab === 'face' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">
                <UserCheck size={18} />
                <span>YuNet Face Detection & OpenCV SFace Biometrics</span>
              </h3>
              {evidence.face_analysis && (
                <span className={`badge ${evidence.face_analysis.face_detected ? 'badge-cyan' : 'badge-neutral'}`}>
                  {evidence.face_analysis.face_count} Face(s) Detected
                </span>
              )}
            </div>

            {evidence.face_analysis?.face_detected ? (
              <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: '24px' }}>
                <div>
                  <div className="image-pane-label" style={{ marginBottom: '6px' }}>Normalized Face Crop</div>
                  <div className="image-wrapper" style={{ minHeight: '180px', maxHeight: '200px' }}>
                    {faceCropUrl && <img src={faceCropUrl} alt="Face Crop" style={{ maxHeight: '180px' }} />}
                  </div>
                </div>

                <div>
                  <table className="kv-table">
                    <tbody>
                      <tr>
                        <th>Detection Confidence</th>
                        <td className="mono">{(evidence.face_analysis.confidence! * 100).toFixed(2)}%</td>
                      </tr>
                      <tr>
                        <th>Bounding Box</th>
                        <td className="mono">
                          [{evidence.face_analysis.bounding_box?.x}, {evidence.face_analysis.bounding_box?.y}, {evidence.face_analysis.bounding_box?.width}x{evidence.face_analysis.bounding_box?.height}]
                        </td>
                      </tr>
                      <tr>
                        <th>Recognition Model</th>
                        <td>{evidence.face_analysis.embedding_model}</td>
                      </tr>
                      <tr>
                        <th>Embedding Dimension</th>
                        <td className="mono">{evidence.face_analysis.embedding_dimensions}-D Vector</td>
                      </tr>
                      {evidence.face_analysis.landmarks && (
                        <tr>
                          <th>Facial Landmarks</th>
                          <td>5-Point (Right Eye, Left Eye, Nose, Mouth Corners)</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <p style={{ color: 'var(--text-secondary)' }}>
                {evidence.face_analysis?.message || 'No face detection data available. Run analysis with Face Detection enabled.'}
              </p>
            )}

            <div className="callout callout-info" style={{ marginTop: '20px', marginBottom: 0 }}>
              <Info size={18} style={{ flexShrink: 0 }} />
              <div>
                <strong>Investigative Notice:</strong> YuNet face bounding boxes and SFace 128-D cosine embeddings
                are biometric investigative aids. They do NOT constitute definitive proof of human identity.
              </div>
            </div>
          </div>

          {/* Web Search Section */}
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">
                <Compass size={18} />
                <span>Reverse Image Search & Public Candidate Verification</span>
              </h3>
              <span className="badge badge-neutral">
                {evidence.web_search?.status || 'Not Run'}
              </span>
            </div>

            {evidence.web_search ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div style={{ fontSize: '0.88rem' }}>
                  <strong>Search Status:</strong> {evidence.web_search.status}
                </div>

                {evidence.web_search.best_match && evidence.web_search.best_match.url && (
                  <div style={{ fontSize: '0.88rem' }}>
                    <strong>Top Public Match:</strong>{' '}
                    <a
                      href={evidence.web_search.best_match.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: 'var(--accent-cyan)' }}
                    >
                      {evidence.web_search.best_match.title || evidence.web_search.best_match.source || 'Public Match'}
                    </a>
                  </div>
                )}

                {evidence.web_search.public_face_match && (
                  <div style={{ fontSize: '0.88rem' }}>
                    <strong>Verified Public Face Similarity:</strong>{' '}
                    <span className="mono">
                      {evidence.web_search.public_face_match.similarity
                        ? (evidence.web_search.public_face_match.similarity * 100).toFixed(1) + '%'
                        : 'Exact visual match'}
                    </span>
                  </div>
                )}

                <div className="callout callout-neutral" style={{ fontSize: '0.8rem', marginTop: '6px' }}>
                  {evidence.web_search.third_party_disclosure}
                </div>
              </div>
            ) : (
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem' }}>
                Public web reverse search was not requested or is disabled.
              </p>
            )}
          </div>
        </div>
      )}

      {/* TAB 4: Integrity & Blockchain */}
      {activeTab === 'integrity' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* 1. Dedicated Cryptographic Integrity Verification Card */}
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">
                <ShieldCheck size={18} />
                <span>Cryptographic Integrity Verification Checks</span>
              </h3>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button
                  className="btn btn-secondary"
                  style={{ padding: '5px 12px', fontSize: '0.8rem' }}
                  onClick={handleVerifyIntegrity}
                  disabled={isVerifying || evidence.status !== 'analyzed'}
                >
                  <RotateCw size={14} className={isVerifying ? 'spinner' : ''} />
                  <span>{isVerifying ? 'Verifying...' : 'Run Verification Now'}</span>
                </button>
                <span className={`badge ${integrityEval.overallBadgeClass}`}>
                  {integrityEval.overallBadgeText}
                </span>
              </div>
            </div>

            <p style={{ color: 'var(--text-secondary)', fontSize: '0.86rem', marginBottom: '16px' }}>
              FaceChain Forensics evaluates three independent cryptographic trust boundaries. All three checks must pass for full forensic verification.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {/* Check 1: Local File Match */}
              <div
                style={{
                  background: 'var(--bg-surface-elevated)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '16px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '10px', marginBottom: '8px' }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '0.92rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span>1. Local File Match</span>
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      Does the actual stored original file's SHA-256 match the trusted manifest original_file_hash?
                    </div>
                  </div>
                  <span className={`badge ${integrityEval.checks.localFile.badgeClass}`}>
                    {integrityEval.checks.localFile.badgeText}
                  </span>
                </div>

                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                  {integrityEval.checks.localFile.label}
                </div>

                <table className="kv-table" style={{ fontSize: '0.8rem' }}>
                  <tbody>
                    <tr>
                      <th style={{ width: '22%' }}>Expected Hash</th>
                      <td className="mono" style={{ wordBreak: 'break-all' }}>
                        {verificationResult?.local_integrity.original_file_hash || evidence.original_hash}
                      </td>
                    </tr>
                    <tr>
                      <th>Actual Hash</th>
                      <td className="mono" style={{ wordBreak: 'break-all', color: integrityEval.checks.localFile.status === 'failed' ? 'var(--accent-rose)' : 'inherit' }}>
                        {verificationResult ? verificationResult.local_integrity.actual_file_hash : 'Not computed yet (click Verify)'}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* Check 2: Manifest Digest */}
              <div
                style={{
                  background: 'var(--bg-surface-elevated)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '16px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '10px', marginBottom: '8px' }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '0.92rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span>2. Manifest Digest</span>
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      Does the recomputed canonical manifest digest match the trusted expected manifest digest?
                    </div>
                  </div>
                  <span className={`badge ${integrityEval.checks.manifestDigest.badgeClass}`}>
                    {integrityEval.checks.manifestDigest.badgeText}
                  </span>
                </div>

                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                  {integrityEval.checks.manifestDigest.label}
                </div>

                <table className="kv-table" style={{ fontSize: '0.8rem' }}>
                  <tbody>
                    <tr>
                      <th style={{ width: '22%' }}>Expected Digest</th>
                      <td className="mono" style={{ wordBreak: 'break-all' }}>
                        {verificationResult?.local_integrity.expected_manifest_hash || evidence.manifest_hash || 'N/A'}
                      </td>
                    </tr>
                    <tr>
                      <th>Recomputed Digest</th>
                      <td className="mono" style={{ wordBreak: 'break-all', color: integrityEval.checks.manifestDigest.status === 'failed' ? 'var(--accent-rose)' : 'inherit' }}>
                        {verificationResult ? verificationResult.local_integrity.recomputed_manifest_hash : 'Not recomputed yet'}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              {/* Check 3: Sepolia On-Chain Record */}
              <div
                style={{
                  background: 'var(--bg-surface-elevated)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '16px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '10px', marginBottom: '8px' }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '0.92rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span>3. Sepolia On-Chain Record</span>
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                      Does the anchored payload on Ethereum Sepolia match the expected manifest digest?
                    </div>
                  </div>
                  <span className={`badge ${integrityEval.checks.blockchain.badgeClass}`}>
                    {integrityEval.checks.blockchain.badgeText}
                  </span>
                </div>

                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                  {integrityEval.checks.blockchain.label}
                </div>

                <table className="kv-table" style={{ fontSize: '0.8rem' }}>
                  <tbody>
                    <tr>
                      <th style={{ width: '22%' }}>Transaction Hash</th>
                      <td>
                        {evidence.blockchain_tx_hash ? (
                          <a
                            href={`https://sepolia.etherscan.io/tx/${evidence.blockchain_tx_hash}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{ color: 'var(--accent-cyan)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                          >
                            <span className="mono">{evidence.blockchain_tx_hash}</span>
                            <ExternalLink size={12} />
                          </a>
                        ) : (
                          <span style={{ color: 'var(--text-muted)' }}>Not anchored (off-chain analysis only)</span>
                        )}
                      </td>
                    </tr>
                    <tr>
                      <th>On-Chain Hash</th>
                      <td className="mono" style={{ wordBreak: 'break-all' }}>
                        {verificationResult?.blockchain_verification?.on_chain_hash || (evidence.blockchain_tx_hash ? 'Not queried yet' : 'N/A (Unanchored)')}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          {/* Manifest & Cryptographic Hashes Card */}
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">
                <ShieldCheck size={18} />
                <span>Evidence Manifest & Cryptographic Hashes</span>
              </h3>
              <span className="badge badge-cyan">Version 1.0</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                  Original Image SHA-256 Digest
                </div>
                <div className="mono-box">
                  <span>{evidence.original_hash}</span>
                  <button
                    className="btn btn-secondary"
                    style={{ padding: '2px 8px', fontSize: '0.72rem' }}
                    onClick={() => copyToClipboard(evidence.original_hash, 'orig_hash')}
                  >
                    {copiedField === 'orig_hash' ? 'Copied' : 'Copy'}
                  </button>
                </div>
              </div>

              {evidence.manifest_hash && (
                <div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Versioned Manifest Canonical SHA-256 Hash
                  </div>
                  <div className="mono-box">
                    <span>{evidence.manifest_hash}</span>
                    <button
                      className="btn btn-secondary"
                      style={{ padding: '2px 8px', fontSize: '0.72rem' }}
                      onClick={() => copyToClipboard(evidence.manifest_hash!, 'man_hash')}
                    >
                      {copiedField === 'man_hash' ? 'Copied' : 'Copy'}
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Canonical Manifest JSON Box */}
            {evidence.manifest && (
              <div style={{ marginTop: '20px' }}>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Canonical Manifest Structure (Excludes own digest & blockchain metadata)
                </div>
                <pre
                  className="mono"
                  style={{
                    background: '#060911',
                    padding: '16px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-subtle)',
                    fontSize: '0.78rem',
                    color: '#93c5fd',
                    maxHeight: '260px',
                    overflowY: 'auto',
                  }}
                >
                  {JSON.stringify(evidence.manifest, null, 2)}
                </pre>
              </div>
            )}
          </div>

          {/* Blockchain Ledger State Card */}
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">
                <LinkIcon size={18} />
                <span>Ethereum Sepolia Ledger Record</span>
              </h3>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {evidence.status === 'analyzed' && (evidence.blockchain_status === 'unanchored' || evidence.blockchain_status === 'outdated') && (
                  <button
                    className="btn btn-secondary"
                    style={{ padding: '4px 10px', fontSize: '0.78rem' }}
                    onClick={handleAnchorBlockchain}
                    disabled={isAnchoring}
                  >
                    <LinkIcon size={13} className={isAnchoring ? 'spinner' : ''} />
                    <span>{isAnchoring ? 'Anchoring...' : (evidence.blockchain_status === 'outdated' ? 'Re-anchor Current Manifest' : 'Anchor to Sepolia')}</span>
                  </button>
                )}
                <span
                  className={`badge ${
                    evidence.blockchain_status === 'confirmed'
                      ? 'badge-emerald'
                      : evidence.blockchain_status === 'outdated'
                      ? 'badge-rose'
                      : evidence.blockchain_status === 'pending'
                      ? 'badge-amber'
                      : 'badge-neutral'
                  }`}
                >
                  {evidence.blockchain_status === 'outdated' ? 'OUTDATED ANCHOR' : evidence.blockchain_status.toUpperCase()}
                </span>
              </div>
            </div>

            <table className="kv-table">
              <tbody>
                <tr>
                  <th>Blockchain Network</th>
                  <td>Ethereum Sepolia Testnet (ChainID: 11155111)</td>
                </tr>
                <tr>
                  <th>Anchoring Status</th>
                  <td style={{ textTransform: 'capitalize', fontWeight: 600 }}>{evidence.blockchain_status}</td>
                </tr>
                <tr>
                  <th>Transaction Hash</th>
                  <td>
                    {evidence.blockchain_tx_hash ? (
                      <a
                        href={`https://sepolia.etherscan.io/tx/${evidence.blockchain_tx_hash}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: 'var(--accent-cyan)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                      >
                        <span className="mono">{evidence.blockchain_tx_hash}</span>
                        <ExternalLink size={13} />
                      </a>
                    ) : (
                      'Not submitted'
                    )}
                  </td>
                </tr>
                <tr>
                  <th>Mined Block Number</th>
                  <td className="mono">{evidence.blockchain_block_number || 'N/A'}</td>
                </tr>
                <tr>
                  <th>Anchored Timestamp</th>
                  <td>{evidence.blockchain_anchored_at ? new Date(evidence.blockchain_anchored_at).toUTCString() : 'N/A'}</td>
                </tr>
              </tbody>
            </table>

            {evidence.blockchain_error && (
              <div className="callout callout-danger" style={{ marginTop: '16px' }}>
                <AlertTriangle size={16} />
                <div>{evidence.blockchain_error}</div>
              </div>
            )}

            <div className="callout callout-info" style={{ marginTop: '16px', marginBottom: 0 }}>
              <Info size={18} style={{ flexShrink: 0 }} />
              <div>
                <strong>Evidence Privacy Notice:</strong> No images, biometric facial embeddings, GPS coordinates,
                or personally identifiable information are transmitted to the blockchain. Only the SHA-256 manifest
                digest is anchored via transaction payload data.
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 5: Forensic Report & Downloads */}
      {activeTab === 'report' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Dedicated Download Reports Card */}
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">
                <Download size={18} />
                <span>Download Forensic Reports</span>
              </h3>
              <span className="badge badge-cyan">3 Export Formats</span>
            </div>

            <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', marginBottom: '20px' }}>
              Download the official cryptographic forensic report generated from this evidence record. All three formats maintain one structured report model containing consistent file hashes, EXIF/GPS metadata, ELA manipulation analysis, biometric face correlation, and Sepolia blockchain verification.
            </p>

            {downloadError && (
              <div className="callout callout-danger" style={{ marginBottom: '20px' }}>
                <AlertTriangle size={18} />
                <div>{downloadError}</div>
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px' }}>
              {/* Option 1: JSON */}
              <div
                style={{
                  background: 'var(--bg-surface-elevated)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '18px',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  gap: '14px',
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <div style={{ fontWeight: 600, fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <FileCode size={18} style={{ color: 'var(--accent-cyan)' }} />
                      <span>JSON Evidence Report</span>
                    </div>
                    <span className="badge badge-cyan">.json</span>
                  </div>
                  <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.5 }}>
                    Complete structured machine-readable forensic data model including all timestamps, raw digests, and technical parameters.
                  </p>
                </div>
                <button
                  className="btn btn-secondary"
                  onClick={() => handleDownload('json')}
                  disabled={downloadingFormat !== null || evidence.status !== 'analyzed'}
                  style={{ width: '100%', justifyContent: 'center' }}
                >
                  {downloadingFormat === 'json' ? (
                    <>
                      <RotateCw size={15} className="spinner" />
                      <span>Downloading JSON...</span>
                    </>
                  ) : (
                    <>
                      <Download size={15} />
                      <span>Download JSON Report</span>
                    </>
                  )}
                </button>
              </div>

              {/* Option 2: HTML */}
              <div
                style={{
                  background: 'var(--bg-surface-elevated)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '18px',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  gap: '14px',
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <div style={{ fontWeight: 600, fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <Eye size={18} style={{ color: 'var(--accent-emerald)' }} />
                      <span>HTML Forensic Report</span>
                    </div>
                    <span className="badge badge-emerald">.html</span>
                  </div>
                  <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.5 }}>
                    Standalone, print-friendly, interactive report designed to open locally in any browser with sanitized styling and Google Maps link.
                  </p>
                </div>
                <button
                  className="btn btn-secondary"
                  onClick={() => handleDownload('html')}
                  disabled={downloadingFormat !== null || evidence.status !== 'analyzed'}
                  style={{ width: '100%', justifyContent: 'center' }}
                >
                  {downloadingFormat === 'html' ? (
                    <>
                      <RotateCw size={15} className="spinner" />
                      <span>Downloading HTML...</span>
                    </>
                  ) : (
                    <>
                      <Download size={15} />
                      <span>Download HTML Report</span>
                    </>
                  )}
                </button>
              </div>

              {/* Option 3: PDF */}
              <div
                style={{
                  background: 'var(--bg-surface-elevated)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '18px',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  gap: '14px',
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <div style={{ fontWeight: 600, fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <FileText size={18} style={{ color: 'var(--accent-amber)' }} />
                      <span>PDF Forensic Document</span>
                    </div>
                    <span className="badge badge-amber">.pdf</span>
                  </div>
                  <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.5 }}>
                    Formal, paginated PDF report generated via ReportLab with running headers, page numbers ("Page X of Y"), and wrapped hashes.
                  </p>
                </div>
                <button
                  className="btn btn-primary"
                  onClick={() => handleDownload('pdf')}
                  disabled={downloadingFormat !== null || evidence.status !== 'analyzed'}
                  style={{ width: '100%', justifyContent: 'center' }}
                >
                  {downloadingFormat === 'pdf' ? (
                    <>
                      <RotateCw size={15} className="spinner" />
                      <span>Downloading PDF...</span>
                    </>
                  ) : (
                    <>
                      <Download size={15} />
                      <span>Download PDF Report</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Analysis Options Modal */}
      {showAnalysisModal && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.75)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            padding: '20px',
          }}
          onClick={() => setShowAnalysisModal(false)}
        >
          <div
            className="card"
            style={{ width: '100%', maxWidth: '520px', boxShadow: 'var(--shadow-md)' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="card-header">
              <h3 className="card-title">Configure Forensic Pipeline</h3>
              <button
                className="btn btn-secondary"
                style={{ padding: '4px 8px' }}
                onClick={() => setShowAnalysisModal(false)}
              >
                &times;
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', margin: '20px 0' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={includeFace}
                  onChange={(e) => setIncludeFace(e.target.checked)}
                  style={{ width: '18px', height: '18px', accentColor: 'var(--accent-cyan)' }}
                />
                <div>
                  <div style={{ fontWeight: 600 }}>Run Face Detection & Biometrics</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    YuNet detection, face crop, and OpenCV SFace 128-D embedding.
                  </div>
                </div>
              </label>

              <label style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={includeWebSearch}
                  onChange={(e) => setIncludeWebSearch(e.target.checked)}
                  style={{ width: '18px', height: '18px', accentColor: 'var(--accent-cyan)' }}
                />
                <div>
                  <div style={{ fontWeight: 600 }}>Run Google Lens Reverse Search</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    Queries SerpApi for public image candidates (discloses external upload).
                  </div>
                </div>
              </label>

              <label style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={anchorOnAnalysis}
                  onChange={(e) => setAnchorOnAnalysis(e.target.checked)}
                  style={{ width: '18px', height: '18px', accentColor: 'var(--accent-cyan)' }}
                />
                <div>
                  <div style={{ fontWeight: 600 }}>Anchor to Ethereum Sepolia</div>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    Submits manifest SHA-256 hash to testnet if configured.
                  </div>
                </div>
              </label>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button className="btn btn-secondary" onClick={() => setShowAnalysisModal(false)}>
                Cancel
              </button>
              <button className="btn btn-primary" onClick={handleRunAnalysis}>
                Execute Analysis
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
