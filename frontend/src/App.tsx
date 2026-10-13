import React, { useState, useEffect } from 'react';
import {
  UploadCloud,
  Layers,
  ArrowLeft,
  AlertCircle,
} from 'lucide-react';
import { Navbar } from './components/Navbar';
import { EvidenceList } from './components/EvidenceList';
import { EvidenceUpload } from './components/EvidenceUpload';
import { EvidenceDetail } from './components/EvidenceDetail';
import type { EvidenceRecord, SystemHealth } from './types/forensics';
import { fetchHealth, fetchEvidenceList, fetchEvidence } from './services/api';

export const App: React.FC = () => {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [evidenceList, setEvidenceList] = useState<EvidenceRecord[]>([]);
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceRecord | null>(null);
  const [view, setView] = useState<'dashboard' | 'upload' | 'detail'>('dashboard');
  const [loading, setLoading] = useState(true);
  const [appError, setAppError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setAppError(null);
      const [healthData, listData] = await Promise.all([
        fetchHealth().catch(() => null),
        fetchEvidenceList().catch(() => []),
      ]);
      setHealth(healthData);
      setEvidenceList(listData);
    } catch (err: any) {
      setAppError(err.message || 'Failed to connect to FaceChain Forensics backend.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSelectEvidence = async (id: string) => {
    try {
      setLoading(true);
      const full = await fetchEvidence(id);
      setSelectedEvidence(full);
      setView('detail');
    } catch (err: any) {
      setAppError(err.message || 'Failed to load evidence detail.');
    } finally {
      setLoading(false);
    }
  };

  const handleUploadSuccess = (newRecord: EvidenceRecord) => {
    setEvidenceList((prev) => [newRecord, ...prev]);
    setSelectedEvidence(newRecord);
    setView('detail');
  };

  const handleDetailRefresh = (updatedRecord: EvidenceRecord) => {
    setSelectedEvidence(updatedRecord);
    setEvidenceList((prev) =>
      prev.map((item) => (item.id === updatedRecord.id ? updatedRecord : item))
    );
  };

  // Summary statistics
  const totalCount = evidenceList.length;
  const analyzedCount = evidenceList.filter((e) => e.status === 'analyzed').length;
  const anchoredCount = evidenceList.filter((e) => e.blockchain_status === 'confirmed').length;

  return (
    <div className="app-container">
      <Navbar health={health} totalEvidenceCount={totalCount} />

      {appError && (
        <div className="callout callout-danger" style={{ marginBottom: '24px' }}>
          <AlertCircle size={20} />
          <div>
            <strong>Backend Connection Notice:</strong> {appError}
          </div>
        </div>
      )}

      {/* Primary Top View Navigation */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div style={{ display: 'flex', gap: '8px' }}>
          {view === 'detail' && (
            <button
              className="btn btn-secondary"
              onClick={() => {
                setView('dashboard');
                setSelectedEvidence(null);
              }}
            >
              <ArrowLeft size={16} />
              <span>Back to Registry</span>
            </button>
          )}

          {view !== 'detail' && (
            <>
              <button
                className={`nav-tab-btn ${view === 'dashboard' ? 'active' : ''}`}
                onClick={() => setView('dashboard')}
              >
                <Layers size={16} />
                <span>Evidence Dashboard</span>
              </button>
              <button
                className={`nav-tab-btn ${view === 'upload' ? 'active' : ''}`}
                onClick={() => setView('upload')}
              >
                <UploadCloud size={16} />
                <span>Acquire New Evidence</span>
              </button>
            </>
          )}
        </div>

        {view === 'dashboard' && (
          <div style={{ display: 'flex', gap: '14px' }}>
            <div className="badge badge-cyan">
              <span>{analyzedCount} Analyzed</span>
            </div>
            <div className="badge badge-emerald">
              <span>{anchoredCount} Anchored</span>
            </div>
          </div>
        )}
      </div>

      {/* Main View Display */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '80px 20px' }}>
          <div className="spinner" style={{ width: '36px', height: '36px', margin: '0 auto 16px auto' }} />
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Synchronizing with Forensic Engine...
          </div>
        </div>
      ) : (
        <>
          {view === 'dashboard' && (
            <EvidenceList
              evidenceList={evidenceList}
              selectedId={selectedEvidence?.id || null}
              onSelect={handleSelectEvidence}
              onNewUploadClick={() => setView('upload')}
            />
          )}

          {view === 'upload' && (
            <EvidenceUpload onUploadSuccess={handleUploadSuccess} />
          )}

          {view === 'detail' && selectedEvidence && (
            <EvidenceDetail
              evidence={selectedEvidence}
              onRefresh={handleDetailRefresh}
            />
          )}
        </>
      )}
    </div>
  );
};

export default App;
