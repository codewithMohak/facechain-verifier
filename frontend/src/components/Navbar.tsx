import React from 'react';
import { ShieldCheck, Cpu, Database, Activity } from 'lucide-react';
import type { SystemHealth } from '../types/forensics';

interface NavbarProps {
  health: SystemHealth | null;
  totalEvidenceCount: number;
}

export const Navbar: React.FC<NavbarProps> = ({ health, totalEvidenceCount }) => {
  const isBlockchainEnabled = health?.blockchain.enabled ?? false;

  return (
    <header className="app-header">
      <div className="brand">
        <div className="brand-icon">
          <ShieldCheck size={26} />
        </div>
        <div>
          <h1 className="brand-title">FaceChain Forensics</h1>
          <div className="brand-subtitle">Image Integrity & Cryptographic Verifier</div>
        </div>
      </div>

      <div className="header-status-group">
        <div className="badge badge-neutral" title="Total Evidence Catalog">
          <Database size={13} />
          <span>{totalEvidenceCount} Items</span>
        </div>

        <div
          className={`badge ${isBlockchainEnabled ? 'badge-emerald' : 'badge-neutral'}`}
          title={isBlockchainEnabled ? 'Sepolia Anchoring Configured' : 'Local Verification Only'}
        >
          <Activity size={13} />
          <span>{isBlockchainEnabled ? 'Sepolia Active' : 'Sepolia Disabled'}</span>
        </div>

        <div className="badge badge-cyan" title="OpenCV + YuNet + SFace Engine">
          <Cpu size={13} />
          <span>YuNet / SFace v1.0</span>
        </div>
      </div>
    </header>
  );
};
