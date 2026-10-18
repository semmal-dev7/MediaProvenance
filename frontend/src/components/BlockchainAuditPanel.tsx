import React, { useState } from 'react';
import { Blocks, KeyRound, ShieldCheck, ArrowRight, RefreshCw } from 'lucide-react';

export const BlockchainAuditPanel: React.FC = () => {
  const [datasetRoot, setDatasetRoot] = useState<string>('0x7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069');
  const [decoderVer, setDecoderVer] = useState<string>('TrustMark-Q');
  const [auditSize, setAuditSize] = useState<number>(50);
  const [targetBlock, setTargetBlock] = useState<number>(20845910);
  const [activeSession, setActiveSession] = useState<any | null>(null);
  const [sampledIndices, setSampledIndices] = useState<number[]>([]);

  const handleCommitAudit = () => {
    const session = {
      auditId: Math.floor(Math.random() * 9000) + 1000,
      datasetRoot,
      decoderVersion: decoderVer,
      auditSize,
      targetBlockNumber: targetBlock,
      status: 'COMMITTED',
      timestamp: new Date().toLocaleTimeString(),
    };
    setActiveSession(session);

    // Simulate deterministic seed calculation
    const dummySeed = '0x9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f9a8b';
    const indices: number[] = [];
    for (let i = 0; i < 8; i++) {
      indices.push((parseInt(dummySeed.slice(2 + i * 4, 6 + i * 4), 16) % 1000) + 1);
    }
    setSampledIndices(indices);
  };

  return (
    <div className="space-y-6">
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 shadow-xl">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 bg-amber-500/20 text-amber-400 rounded-lg">
            <Blocks className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">Blockchain-Anchored Negative-Image Audit Protocol</h2>
            <p className="text-sm text-slate-400">
              Commit-reveal future blockhash sampling and Solidity verification contract
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Commit Phase */}
          <div className="space-y-4 bg-slate-900/60 p-5 rounded-xl border border-slate-700">
            <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <KeyRound className="w-4 h-4 text-amber-400" />
              1. Commit Audit Configuration (Pre-Entropy)
            </h3>

            <div>
              <label className="block text-xs font-semibold text-slate-400 mb-1">Dataset Manifest SHA-256 Root:</label>
              <input
                type="text"
                value={datasetRoot}
                onChange={(e) => setDatasetRoot(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-200"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1">Committed Decoder:</label>
                <input
                  type="text"
                  value={decoderVer}
                  onChange={(e) => setDecoderVer(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-400 mb-1">Audit Size (k):</label>
                <input
                  type="number"
                  value={auditSize}
                  onChange={(e) => setAuditSize(parseInt(e.target.value) || 10)}
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 mb-1">Target Future Block Number:</label>
              <input
                type="number"
                value={targetBlock}
                onChange={(e) => setTargetBlock(parseInt(e.target.value) || 0)}
                className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-200"
              />
              <span className="text-xs text-slate-500 mt-1 block">
                Public entropy source: blockhash(targetBlockNumber)
              </span>
            </div>

            <button
              onClick={handleCommitAudit}
              className="w-full py-2.5 px-4 bg-amber-600 hover:bg-amber-700 text-white font-medium rounded-lg shadow transition flex items-center justify-center gap-2 text-sm"
            >
              <Blocks className="w-4 h-4" />
              Commit Audit to Smart Contract
            </button>
          </div>

          {/* Verification & Deterministic Sampling */}
          <div className="bg-slate-900/60 p-5 rounded-xl border border-slate-700 flex flex-col justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2 mb-4">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                2. On-Chain Fulfillment & Deterministic Sample
              </h3>

              {activeSession ? (
                <div className="space-y-4">
                  <div className="p-3 bg-slate-800 rounded-lg border border-slate-700 text-xs font-mono space-y-1.5">
                    <div className="flex justify-between">
                      <span className="text-slate-400">Audit Session ID:</span>
                      <span className="text-amber-400 font-bold">#{activeSession.auditId}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Target Block:</span>
                      <span className="text-white">{activeSession.targetBlockNumber}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-400">Status:</span>
                      <span className="text-emerald-400 font-bold uppercase">{activeSession.status}</span>
                    </div>
                  </div>

                  <div>
                    <span className="text-xs font-semibold text-slate-400 block mb-2">
                      Deterministically Selected Negative Images (Auditor Reproducible):
                    </span>
                    <div className="flex flex-wrap gap-2">
                      {sampledIndices.map((idx, i) => (
                        <span
                          key={i}
                          className="px-2.5 py-1 bg-slate-800 text-indigo-300 border border-slate-700 rounded text-xs font-mono"
                        >
                          Image #{idx}
                        </span>
                      ))}
                      <span className="text-xs text-slate-500 self-center">... and {auditSize - sampledIndices.length} more</span>
                    </div>
                  </div>

                  <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-xs text-emerald-300">
                    <strong>Audit Verification Result:</strong> 0 false acceptances detected in sample (k={auditSize}). Statistical upper bound FAR ≤ 5.8% (95% confidence).
                  </div>
                </div>
              ) : (
                <div className="h-56 flex flex-col items-center justify-center text-slate-500 text-sm">
                  <Blocks className="w-8 h-8 mb-2 opacity-50" />
                  Commit an audit session to derive deterministic sample
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
