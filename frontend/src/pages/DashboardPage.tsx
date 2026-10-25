import React, { useState, useEffect } from 'react';
import { Blocks, Clock, ArrowRight, ShieldCheck, ExternalLink, CheckCircle2, Cpu } from 'lucide-react';

interface DashboardProps {
  onNavigate: (tab: string) => void;
}

// Custom VTOP-style square login/enter icon
const VtopLoginIcon: React.FC<{ className?: string }> = ({ className = "w-4 h-4" }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
    <polyline points="10 17 15 12 10 7" />
    <line x1="15" y1="12" x2="3" y2="12" />
  </svg>
);

// Tailored vector illustrations matching the aesthetic of the 4 cards:
// Card 1: Publisher / Creator (Camera & Media Canvas with Watermark)
const PublisherIllustration: React.FC = () => (
  <svg viewBox="0 0 100 80" className="w-16 h-14 select-none">
    {/* Digital Canvas / Image Frame */}
    <rect x="18" y="14" width="64" height="48" rx="6" fill="#f1f5f9" stroke="#94a3b8" strokeWidth="2" />
    {/* Landscape Mountain / Sun inside image */}
    <circle cx="36" cy="28" r="5" fill="#f59e0b" />
    <polygon points="26,54 44,34 56,46 64,38 74,54" fill="#cbd5e1" />
    {/* Camera Badge / Floating Chip */}
    <rect x="42" y="44" width="44" height="26" rx="5" fill="#1e40af" />
    <circle cx="64" cy="57" r="7" fill="#ffffff" stroke="#93c5fd" strokeWidth="2" />
    <circle cx="64" cy="57" r="3" fill="#3b82f6" />
    <rect x="52" y="40" width="12" height="5" rx="1.5" fill="#1d4ed8" />
    {/* Microscopic Neural Frequency Wave */}
    <path d="M22,20 Q28,16 34,20 T46,20" stroke="#3b82f6" strokeWidth="1.5" fill="none" strokeDasharray="2,2" />
  </svg>
);

// Card 2: Verifier / Evaluator (Security Shield & Neural Node Graph)
const VerifierIllustration: React.FC = () => (
  <svg viewBox="0 0 100 80" className="w-16 h-14 select-none">
    {/* Security Shield */}
    <path d="M50,10 L78,22 C78,48 50,68 50,68 C50,68 22,48 22,22 Z" fill="#fffbeb" stroke="#d97706" strokeWidth="2.5" />
    {/* Neural Network Nodes inside Shield */}
    <line x1="38" y1="32" x2="62" y2="32" stroke="#f59e0b" strokeWidth="1.5" />
    <line x1="38" y1="32" x2="50" y2="48" stroke="#f59e0b" strokeWidth="1.5" />
    <line x1="62" y1="32" x2="50" y2="48" stroke="#f59e0b" strokeWidth="1.5" />
    <circle cx="38" cy="32" r="4.5" fill="#d97706" />
    <circle cx="62" cy="32" r="4.5" fill="#d97706" />
    <circle cx="50" cy="48" r="5.5" fill="#b45309" />
    {/* Verified Green Check Badge */}
    <circle cx="70" cy="52" r="10" fill="#16a34a" />
    <path d="M66,52 L69,55 L75,49" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
  </svg>
);

// Card 3: Auditor / Public (Ethereum Blocks & Blockchain Ledger)
const AuditorIllustration: React.FC = () => (
  <svg viewBox="0 0 100 80" className="w-16 h-14 select-none">
    {/* Left Block */}
    <polygon points="32,24 48,16 48,34 32,42" fill="#dcfce7" stroke="#16a34a" strokeWidth="1.5" />
    <polygon points="16,16 32,24 32,42 16,34" fill="#bbf7d0" stroke="#16a34a" strokeWidth="1.5" />
    <polygon points="16,16 32,8 48,16 32,24" fill="#86efac" stroke="#16a34a" strokeWidth="1.5" />
    {/* Right Block */}
    <polygon points="80,44 96,36 96,54 80,62" fill="#dcfce7" stroke="#16a34a" strokeWidth="1.5" />
    <polygon points="64,36 80,44 80,62 64,54" fill="#bbf7d0" stroke="#16a34a" strokeWidth="1.5" />
    <polygon points="64,36 80,28 96,36 80,44" fill="#86efac" stroke="#16a34a" strokeWidth="1.5" />
    {/* Central Ethereum Diamond */}
    <polygon points="50,22 62,42 50,48 38,42" fill="#15803d" />
    <polygon points="50,51 62,45 50,62 38,45" fill="#166534" />
    <polygon points="50,22 38,42 50,48" fill="#22c55e" opacity="0.8" />
    {/* Connecting Chain */}
    <path d="M38,32 Q50,30 64,44" stroke="#15803d" strokeWidth="2" fill="none" strokeDasharray="2,2" />
  </svg>
);

export const DashboardPage: React.FC<DashboardProps> = ({ onNavigate }) => {
  const [anchors, setAnchors] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [health, setHealth] = useState<any>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [healthRes, anchorsRes, jobsRes] = await Promise.all([
          fetch('/api/v1/health').then(r => r.json()).catch(() => null),
          fetch('/api/v1/anchors').then(r => r.json()).catch(() => []),
          fetch('/api/v1/jobs').then(r => r.json()).catch(() => []),
        ]);
        setHealth(healthRes);
        setAnchors(Array.isArray(anchorsRes) ? anchorsRes : []);
        setJobs(Array.isArray(jobsRes) ? jobsRes : []);
      } catch (err) {
        console.error(err);
      }
    };
    fetchData();
  }, []);

  return (
    <div className="space-y-8 py-2">
      {/* VTOP Design: Main Institutional Title & Subtitle */}
      <div className="text-center space-y-2.5 max-w-4xl mx-auto px-4">
        <h2 className="text-2xl sm:text-3xl font-extrabold text-[#1a56a4] tracking-tight">
          ProvenanceLab — Media Provenance &amp; Verification Portal
        </h2>
        <p className="text-xs sm:text-[13px] text-slate-700 leading-relaxed font-normal">
          A digital initiative facilitating Creators, Journalists, Researchers, and Public Auditors to embed, verify, and anchor neural watermarks on Ethereum.
        </p>
      </div>

      {/* VTOP Design: 3 Horizontal Portal Cards with Distinct Accent Top Borders */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5 px-2">
        {/* Card 1: Media Publisher (Embed Watermark) */}
        <div className="bg-white rounded border border-slate-200/90 shadow-sm border-t-[3.5px] border-t-[#1a73e8] p-4 flex items-center justify-between hover:shadow-md transition">
          <div className="flex items-center gap-2">
            <PublisherIllustration />
          </div>
          <div className="flex flex-col items-end gap-2 text-right">
            <div>
              <span className="text-sm font-bold text-[#1a73e8] block">Publisher</span>
              <span className="text-[10px] text-slate-500 font-medium block">Embed TrustMark-Q</span>
            </div>
            <button
              onClick={() => onNavigate('embed')}
              title="Open Watermark Embedding Portal"
              className="w-8 h-8 rounded bg-[#1a73e8] hover:bg-blue-600 text-white flex items-center justify-center shadow-sm transition active:scale-95"
            >
              <VtopLoginIcon className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Card 2: ZK Verifier (Verify & ZK Proof) */}
        <div className="bg-white rounded border border-slate-200/90 shadow-sm border-t-[3.5px] border-t-[#d97706] p-4 flex items-center justify-between hover:shadow-md transition">
          <div className="flex items-center gap-2">
            <VerifierIllustration />
          </div>
          <div className="flex flex-col items-end gap-2 text-right">
            <div>
              <span className="text-sm font-bold text-[#d97706] block">Verifier</span>
              <span className="text-[10px] text-slate-500 font-medium block">Halo2 ZK-SNARK Prover</span>
            </div>
            <button
              onClick={() => onNavigate('verify')}
              title="Open Zero-Knowledge Verification Portal"
              className="w-8 h-8 rounded bg-[#d97706] hover:bg-amber-600 text-white flex items-center justify-center shadow-sm transition active:scale-95"
            >
              <VtopLoginIcon className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Card 3: Public Auditor (Blockchain Explorer) */}
        <div className="bg-white rounded border border-slate-200/90 shadow-sm border-t-[3.5px] border-t-[#16a34a] p-4 flex items-center justify-between hover:shadow-md transition">
          <div className="flex items-center gap-2">
            <AuditorIllustration />
          </div>
          <div className="flex flex-col items-end gap-2 text-right">
            <div>
              <span className="text-sm font-bold text-[#16a34a] block">Auditor</span>
              <span className="text-[10px] text-slate-500 font-medium block">Sepolia Public Ledger</span>
            </div>
            <button
              onClick={() => onNavigate('audit')}
              title="Open Public Blockchain Audit"
              className="w-8 h-8 rounded bg-[#16a34a] hover:bg-emerald-600 text-white flex items-center justify-center shadow-sm transition active:scale-95"
            >
              <VtopLoginIcon className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Academic Capstone Project Information Card */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm space-y-3">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-100 pb-3">
          <div>
            <h3 className="text-base sm:text-lg font-bold text-slate-900 mt-0.5">
              Blockchain-Anchored Zero-Knowledge Verification of Neural Watermarks for Publicly Auditable Media Provenance
            </h3>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] bg-emerald-50 text-emerald-700 border border-emerald-200 px-2.5 py-1 rounded-full font-semibold flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Sepolia Contract Live
            </span>
          </div>
        </div>

        {/* Metric Badges */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs pt-1">
          <div className="bg-slate-50 p-3 rounded-lg border border-slate-200/80">
            <span className="text-slate-500 font-medium text-[11px] block">Carrier Architecture</span>
            <span className="font-bold text-slate-900 mt-0.5 block">TrustMark-Q (100-bit)</span>
            <span className="text-[10px] text-emerald-600">Spatial Residual Neural</span>
          </div>
          <div className="bg-slate-50 p-3 rounded-lg border border-slate-200/80">
            <span className="text-slate-500 font-medium text-[11px] block">ZK-SNARK Prover</span>
            <span className="font-bold text-slate-900 mt-0.5 block">Two-Stage Feature-Witness</span>
            <span className="text-[10px] text-blue-600">Halo2 · KZG on BN254</span>
          </div>
          <div className="bg-slate-50 p-3 rounded-lg border border-slate-200/80">
            <span className="text-slate-500 font-medium text-[11px] block">On-Chain Anchors</span>
            <span className="font-bold text-slate-900 mt-0.5 block">{anchors.length} Confirmed</span>
            <span className="text-[10px] text-amber-600">Sepolia Ledger Synced</span>
          </div>
          <div className="bg-slate-50 p-3 rounded-lg border border-slate-200/80">
            <span className="text-slate-500 font-medium text-[11px] block">Contract Address</span>
            <a
              href="https://sepolia.etherscan.io/address/0x6D8C82dc761Ed9bac93ca99987b91614B90Ad43F"
              target="_blank"
              rel="noreferrer"
              className="font-bold text-blue-600 hover:text-blue-700 mt-0.5 flex items-center gap-1 truncate"
            >
              0x6D8C...d43F <ExternalLink className="w-3 h-3 flex-shrink-0" />
            </a>
            <span className="text-[10px] text-slate-500">Public Read Auditing</span>
          </div>
        </div>
      </div>

      {/* Recent Blockchain Anchors Registry */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
            <Blocks className="w-4 h-4 text-[#1a56a4]" />
            Recent On-Chain Provenance Anchors
          </h3>
          <button
            onClick={() => onNavigate('audit')}
            className="text-xs text-[#1a56a4] hover:underline font-semibold flex items-center gap-1"
          >
            Open Full Ledger <ArrowRight className="w-3 h-3" />
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
          {anchors.slice(0, 4).map((a, i) => (
            <div key={i} className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-xs space-y-1 hover:border-slate-300 transition">
              <div className="flex items-center justify-between">
                <span className="font-mono text-slate-900 font-semibold truncate max-w-[200px]">
                  {a.asset_id}
                </span>
                <a
                  href={`https://sepolia.etherscan.io/block/${a.block_number}`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-[10px] bg-blue-100 hover:bg-blue-200 text-blue-800 font-mono px-1.5 py-0.5 rounded transition inline-flex items-center gap-0.5"
                  title={`View Block #${a.block_number} on Sepolia Etherscan`}
                >
                  Block #{a.block_number}
                  <ExternalLink className="w-2.5 h-2.5 opacity-60" />
                </a>
              </div>
              <div className="flex items-center justify-between text-slate-500 text-[11px]">
                <span className="font-mono text-slate-600 truncate max-w-[220px]">
                  Commitment: {a.commitment.slice(0, 18)}...
                </span>
                <a
                  href={a.etherscan_url || `https://sepolia.etherscan.io/tx/${a.tx_hash}`}
                  target="_blank"
                  rel="noreferrer"
                  className="text-blue-600 hover:text-blue-800 flex items-center gap-0.5 font-medium"
                >
                  Tx <ExternalLink className="w-2.5 h-2.5" />
                </a>
              </div>
            </div>
          ))}
          {anchors.length === 0 && (
            <p className="text-xs text-slate-500 py-4 col-span-2 text-center">No anchors registered yet.</p>
          )}
        </div>
      </div>
    </div>
  );
};
