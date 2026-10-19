import React, { useState } from 'react';
import { DashboardPage } from './pages/DashboardPage';
import { EmbedPage } from './pages/EmbedPage';
import { VerifyPage } from './pages/VerifyPage';
import { BlockchainAuditPage } from './pages/BlockchainAuditPage';
import { ExperimentsPage } from './pages/ExperimentsPage';
import { Shield, Activity, Crosshair, Blocks, BookOpen, Cpu, CheckCircle2, LayoutDashboard } from 'lucide-react';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'embed' | 'verify' | 'audit' | 'experiments' | 'publications'>('dashboard');

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Banner / Capstone Registered Title */}
      <header className="bg-slate-900 border-b border-slate-800 py-3.5 px-6 sticky top-0 z-50 shadow-md">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
              <h1 className="text-lg font-bold text-white tracking-tight">ProvenanceLab</h1>
              <span className="text-xs bg-blue-500/20 text-blue-400 border border-blue-500/30 px-2 py-0.5 rounded font-mono">
                v1.0.0-blueprint
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5 max-w-3xl leading-relaxed">
              <span className="text-slate-500 uppercase font-semibold">Official Capstone:</span>{' '}
              <strong className="text-slate-200">
                BLOCKCHAIN-ANCHORED ZERO-KNOWLEDGE VERIFICATION OF NEURAL WATERMARKS FOR PUBLICLY AUDITABLE MEDIA PROVENANCE
              </strong>
            </p>
          </div>

          {/* Navigation Tabs (5 Core Pages + Publication) */}
          <nav className="flex items-center gap-1 bg-slate-950/90 p-1 rounded-xl border border-slate-800 self-start md:self-auto overflow-x-auto max-w-full">
            <button
              onClick={() => setActiveTab('dashboard')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                activeTab === 'dashboard'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              <LayoutDashboard className="w-3.5 h-3.5" />
              Dashboard
            </button>
            <button
              onClick={() => setActiveTab('embed')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                activeTab === 'embed'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              <Cpu className="w-3.5 h-3.5" />
              Embed Watermark
            </button>
            <button
              onClick={() => setActiveTab('verify')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                activeTab === 'verify'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              Verify Image
            </button>
            <button
              onClick={() => setActiveTab('audit')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                activeTab === 'audit'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              <Blocks className="w-3.5 h-3.5" />
              Blockchain Audit
            </button>
            <button
              onClick={() => setActiveTab('experiments')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                activeTab === 'experiments'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              Experiments &amp; Ablation
            </button>
            <button
              onClick={() => setActiveTab('publications')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                activeTab === 'publications'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              <BookOpen className="w-3.5 h-3.5" />
              Paper Draft
            </button>
          </nav>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6">
        {activeTab === 'dashboard' && <DashboardPage onNavigate={(tab: any) => setActiveTab(tab)} />}
        {activeTab === 'embed' && <EmbedPage onProceedToVerify={() => setActiveTab('verify')} />}
        {activeTab === 'verify' && <VerifyPage />}
        {activeTab === 'audit' && <BlockchainAuditPage />}
        {activeTab === 'experiments' && <ExperimentsPage />}
        {activeTab === 'publications' && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-8 max-w-4xl mx-auto shadow-2xl space-y-6">
            <div className="border-b border-slate-800 pb-4">
              <span className="text-xs font-bold text-blue-400 uppercase tracking-widest block mb-1">
                IEEE WIFS / IH&amp;MMSec Submission Draft
              </span>
              <h2 className="text-2xl font-bold text-white">
                Noisy-Channel Modeling of Deep Neural Watermark Degradation and Publicly Auditable Blockchain Verification
              </h2>
              <p className="text-xs text-slate-400 mt-2">
                Draft available at: <code className="text-blue-300">docs/paper/research_paper_draft.md</code>
              </p>
            </div>

            <div className="text-sm text-slate-300 space-y-4 leading-relaxed">
              <h3 className="text-base font-bold text-white uppercase tracking-wider">Abstract</h3>
              <p>
                Neural image watermarking provides robust perceptual provenance tracking under lossy transformations,
                yet existing verification schemes lack defensible statistical evidence measures and require either
                trusting a centralized oracle or exposing sensitive watermark payloads. In this paper, we formulate a
                rigorous noisy-channel model of neural-watermark degradation under realistic image transformations,
                characterizing bit degradation via Binomial and Beta-Binomial channels with empirical Platt calibration.
              </p>
              <p>
                We demonstrate that the empirical degradation satisfies Gate 1 survival requirements (100% decodability across 160 trials),
                formalize a Zero-Knowledge payload commitment protocol satisfying strict non-repudiation while keeping model weights confidential,
                and deploy an on-chain commitment registry (<code className="text-amber-300 font-mono">ProvenanceAnchor.sol</code>) with fixed $O(1)$ gas complexity.
              </p>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-900/60 py-4 px-6 text-center text-xs text-slate-500">
        <p>
          ProvenanceLab Experimental Framework · Institutional Final-Year Capstone (BCSE497J) · Vit University
        </p>
      </footer>
    </div>
  );
};

export default App;
