import React, { useState } from 'react';
import { DashboardPage } from './pages/DashboardPage';
import { EmbedPage } from './pages/EmbedPage';
import { VerifyPage } from './pages/VerifyPage';
import { BlockchainAuditPage } from './pages/BlockchainAuditPage';
import { Shield, ArrowLeft } from 'lucide-react';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'embed' | 'verify' | 'audit'>('dashboard');

  const isHome = activeTab === 'dashboard';

  return (
    <div className={`min-h-screen flex flex-col font-sans transition-colors duration-200 ${
      isHome ? 'bg-[#f4f6f9] text-slate-800' : 'bg-slate-950 text-slate-100'
    }`}>
      {/* Top Banner */}
      <header className="py-3.5 px-6 sticky top-0 z-50 shadow-md transition-colors duration-200 vtop-header">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          {isHome ? (
            /* Home page: ProvenanceLab on left */
            <div
              className="vtop-brand flex items-center gap-2.5 cursor-pointer hover:opacity-90 transition active:scale-95"
              onClick={() => setActiveTab('dashboard')}
              title="ProvenanceLab"
            >
              <div className="p-1.5 bg-white/20 rounded-lg backdrop-blur-sm border border-white/30 flex items-center justify-center">
                <Shield className="w-5 h-5 text-white" />
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-xl font-bold tracking-tight text-white">
                  ProvenanceLab
                </span>
              </div>
            </div>
          ) : (
            /* Workspace Pages: Back to Home on LEFT, ProvenanceLab on RIGHT */
            <>
              <button
                onClick={() => setActiveTab('dashboard')}
                className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold text-white bg-white/15 hover:bg-white/25 border border-white/30 backdrop-blur-sm transition active:scale-95 shadow-sm"
                title="Return to Home Portal"
              >
                <ArrowLeft className="w-4 h-4 text-white" />
                <span>Back to Home</span>
              </button>

              <div
                className="vtop-brand flex items-center gap-2.5 cursor-pointer hover:opacity-90 transition active:scale-95"
                onClick={() => setActiveTab('dashboard')}
                title="ProvenanceLab — Return to Home"
              >
                <div className="p-1.5 bg-white/20 rounded-lg backdrop-blur-sm border border-white/30 flex items-center justify-center">
                  <Shield className="w-5 h-5 text-white" />
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-xl font-bold tracking-tight text-white">
                    ProvenanceLab
                  </span>
                </div>
              </div>
            </>
          )}
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6">
        {activeTab === 'dashboard' && <DashboardPage onNavigate={(tab: any) => setActiveTab(tab)} />}
        {activeTab === 'embed' && <EmbedPage onProceedToVerify={() => setActiveTab('verify')} />}
        {activeTab === 'verify' && <VerifyPage />}
        {activeTab === 'audit' && <BlockchainAuditPage />}
      </main>
    </div>
  );
};

export default App;