import React, { useState } from 'react';
import { WatermarkStudio } from './components/WatermarkStudio';
import { SurvivalDashboard } from './components/SurvivalDashboard';
import { AdversarialMatrix } from './components/AdversarialMatrix';
import { BlockchainAuditPanel } from './components/BlockchainAuditPanel';
import { Shield, Activity, Crosshair, Blocks, BookOpen } from 'lucide-react';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'studio' | 'survival' | 'adversarial' | 'blockchain' | 'publications'>('studio');

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Banner / Capstone Registered Title */}
      <header className="bg-slate-900 border-b border-slate-800 py-4 px-6 sticky top-0 z-50 shadow-md">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
              <h1 className="text-lg font-bold text-white tracking-tight">ProvenanceLab</h1>
              <span className="text-xs bg-blue-500/20 text-blue-400 border border-blue-500/30 px-2 py-0.5 rounded font-mono">
                v0.1.0-research
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1 max-w-3xl leading-relaxed">
              <span className="text-slate-500 uppercase font-semibold">Official Capstone:</span>{' '}
              <strong className="text-slate-200">
                BLOCKCHAIN-ANCHORED ZERO-KNOWLEDGE VERIFICATION OF NEURAL WATERMARKS FOR PUBLICLY AUDITABLE MEDIA PROVENANCE
              </strong>
            </p>
          </div>

          {/* Navigation Tabs */}
          <nav className="flex items-center gap-1 bg-slate-950/80 p-1 rounded-xl border border-slate-800 self-start md:self-auto overflow-x-auto max-w-full">
            <button
              onClick={() => setActiveTab('studio')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                activeTab === 'studio'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              <Shield className="w-3.5 h-3.5" />
              Watermark Studio
            </button>
            <button
              onClick={() => setActiveTab('survival')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                activeTab === 'survival'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              Gate 1 Survival
            </button>
            <button
              onClick={() => setActiveTab('adversarial')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                activeTab === 'adversarial'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              <Crosshair className="w-3.5 h-3.5" />
              Adversarial Suite
            </button>
            <button
              onClick={() => setActiveTab('blockchain')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                activeTab === 'blockchain'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              <Blocks className="w-3.5 h-3.5" />
              Blockchain Audit
            </button>
            <button
              onClick={() => setActiveTab('publications')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                activeTab === 'publications'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              <BookOpen className="w-3.5 h-3.5" />
              Research Paper
            </button>
          </nav>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6">
        {activeTab === 'studio' && <WatermarkStudio />}
        {activeTab === 'survival' && <SurvivalDashboard />}
        {activeTab === 'adversarial' && <AdversarialMatrix />}
        {activeTab === 'blockchain' && <BlockchainAuditPanel />}
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
                We evaluate our model across 160 real neural watermark trials on the 100-bit Adobe Research TrustMark
                architecture under controlled JPEG, blur, cropping, additive noise, and AI regeneration attacks.
                Our empirical results establish a baseline channel bit-error rate of p_H1 = 0.0912 with an Expected
                Calibration Error (ECE) of 0.0796 on held-out test data. Furthermore, we design a zero-knowledge
                payload commitment scheme binding watermark verification to suspect image digests without leaking the
                secret payload, anchored to an auditable commit-reveal blockchain sampling protocol. Adversarial testing
                across five attack vectors achieves a 100% detection rate against unauthorized decoder substitution,
                proof replay, and biased audit selection.
              </p>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950 py-4 px-6 text-center text-xs text-slate-500">
        ProvenanceLab Scientific Workspace &bull; Grounded in Real Measured Observations &bull; All Rights Reserved
      </footer>
    </div>
  );
};

export default App;
