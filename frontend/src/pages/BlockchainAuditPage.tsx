import React, { useState, useEffect } from 'react';
import { Blocks, Search, ExternalLink, ShieldCheck, Clock, KeyRound, RefreshCw, Hash } from 'lucide-react';
import { BlockchainAuditPanel } from '../components/BlockchainAuditPanel';

export const BlockchainAuditPage: React.FC = () => {
  const [activeSubTab, setActiveSubTab] = useState<'anchors' | 'commit_reveal'>('anchors');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [searchResult, setSearchResult] = useState<any | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [anchorsList, setAnchorsList] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  useEffect(() => {
    fetchAnchors(true);
  }, []);

  const fetchAnchors = async (triggerSync: boolean = false) => {
    setIsRefreshing(true);
    try {
      if (triggerSync) {
        try {
          await fetch('/api/v1/anchors/sync', { method: 'POST' });
        } catch {
          // Sync warning handled silently
        }
      }
      const res = await fetch('/api/v1/anchors');
      const data = await res.json();
      if (Array.isArray(data)) {
        setAnchorsList(data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setLoading(true);
    setSearchError(null);
    setSearchResult(null);

    try {
      const clean = searchQuery.trim();
      const res = await fetch(`/api/v1/anchors/${clean}`);
      if (res.ok) {
        const data = await res.json();
        setSearchResult(data);
      } else {
        setSearchError(`No record found for query: ${clean}`);
      }
    } catch (err: any) {
      setSearchError(err.message || 'Lookup failed.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-500/20 text-amber-400 rounded-xl">
              <Blocks className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Public Blockchain Audit Explorer</h2>
              <p className="text-xs text-slate-400">
                Inspect smart contract commitments in ProvenanceAnchor.sol &amp; ProvenanceAudit.sol
              </p>
            </div>
          </div>

          {/* Sub-tab selection - Temporarily sealed (unseal whenever needed) */}
          {/*
          <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800 self-start sm:self-auto">
            <button
              onClick={() => setActiveSubTab('anchors')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                activeSubTab === 'anchors'
                  ? 'bg-amber-600 text-white shadow'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Anchor Registry
            </button>
            <button
              onClick={() => setActiveSubTab('commit_reveal')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                activeSubTab === 'commit_reveal'
                  ? 'bg-amber-600 text-white shadow'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Commit-Reveal Entropy
            </button>
          </div>
          */}
        </div>
      </div>

      {activeSubTab === 'anchors' ? (
        <div className="space-y-6">
          {/* Search Box */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-3">
              Search by Asset ID or Transaction Hash
            </h3>
            <form onSubmit={handleSearch} className="flex gap-2">
              <div className="relative flex-1">
                <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Enter 0x... asset ID or image SHA-256 digest"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-amber-500"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-xl text-xs font-semibold shadow transition"
              >
                {loading ? 'Searching...' : 'Lookup'}
              </button>
            </form>

            {searchError && (
              <div className="mt-3 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-xs">
                {searchError}
              </div>
            )}

            {searchResult && (
              <div className="mt-4 p-4 rounded-xl bg-slate-950 border border-amber-500/30 text-xs space-y-3">
                <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                  <span className="font-bold text-amber-400 flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4" />
                    Record Found in Smart Contract
                  </span>
                  <span className="text-[10px] text-slate-500">
                    Block #{searchResult.block_number}
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-[11px]">
                  <div>
                    <span className="text-slate-500 block mb-0.5">Asset ID:</span>
                    <code className="text-slate-200 font-mono break-all">{searchResult.asset_id}</code>
                  </div>
                  <div>
                    <span className="text-slate-500 block mb-0.5">Payload Commitment (C):</span>
                    <code className="text-amber-300 font-mono break-all">{searchResult.commitment}</code>
                  </div>
                  <div>
                    <span className="text-slate-500 block mb-0.5">Submitter Address:</span>
                    <code className="text-blue-300 font-mono break-all">{searchResult.submitter}</code>
                  </div>
                  <div>
                    <span className="text-slate-500 block mb-0.5">Block Timestamp:</span>
                    <span className="text-slate-300">
                      {new Date(searchResult.timestamp * 1000).toLocaleString()}
                    </span>
                  </div>
                  <div className="md:col-span-2 flex items-center justify-between">
                    <div>
                      <span className="text-slate-500 block mb-0.5">Transaction Hash:</span>
                      <a
                        href={`https://sepolia.etherscan.io/tx/${searchResult.tx_hash}`}
                        target="_blank"
                        rel="noreferrer"
                        className="text-emerald-400 hover:text-emerald-300 font-mono break-all flex items-center gap-1 group"
                      >
                        {searchResult.tx_hash}
                        <ExternalLink className="w-3 h-3 flex-shrink-0 opacity-70 group-hover:opacity-100" />
                      </a>
                    </div>
                    <span className="text-[10px] font-mono text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                      Sepolia Testnet
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* All Anchored Records Table */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
                  <Hash className="w-4 h-4 text-amber-400" />
                  Live ProvenanceAnchor Ledger ({anchorsList.length} Records)
                </h3>
                <span className="text-[11px] text-slate-400">
                  Target Network: Ethereum Sepolia (Contract: 0x6D8C82dc761Ed9bac93ca99987b91614B90Ad43F)
                </span>
              </div>
              <button
                onClick={() => fetchAnchors(true)}
                disabled={isRefreshing}
                className="text-xs text-slate-400 hover:text-slate-200 flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-800/80 hover:bg-slate-800 transition"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-amber-400' : ''}`} />
                {isRefreshing ? 'Syncing...' : 'Refresh'}
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400">
                    <th className="pb-3 font-semibold">Asset ID</th>
                    <th className="pb-3 font-semibold">Commitment (C)</th>
                    <th className="pb-3 font-semibold">Submitter</th>
                    <th className="pb-3 font-semibold">Block #</th>
                    <th className="pb-3 font-semibold">Timestamp</th>
                    <th className="pb-3 font-semibold text-right">Etherscan</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono text-[11px]">
                  {anchorsList.map((a, i) => (
                    <tr key={i} className="hover:bg-slate-950/40 transition">
                      <td className="py-3 text-slate-200 truncate max-w-[140px] font-semibold" title={a.asset_id}>
                        {a.asset_id.slice(0, 10)}...{a.asset_id.slice(-6)}
                      </td>
                      <td className="py-3 text-amber-300/90 truncate max-w-[140px]" title={a.commitment}>
                        {a.commitment.slice(0, 10)}...{a.commitment.slice(-6)}
                      </td>
                      <td className="py-3 text-blue-300 truncate max-w-[120px]" title={a.submitter}>
                        {a.submitter.slice(0, 8)}...{a.submitter.slice(-4)}
                      </td>
                      <td className="py-3 text-slate-300 font-semibold">
                        <a
                          href={`https://sepolia.etherscan.io/block/${a.block_number}`}
                          target="_blank"
                          rel="noreferrer"
                          className="hover:text-blue-400 hover:underline inline-flex items-center gap-1 text-slate-200"
                          title={`View Ethereum Block #${a.block_number} on Etherscan`}
                        >
                          #{a.block_number}
                          <ExternalLink className="w-2.5 h-2.5 opacity-60" />
                        </a>
                      </td>
                      <td className="py-3 text-slate-400 font-sans text-xs">
                        <div>{new Date(a.timestamp * 1000).toLocaleDateString()}</div>
                        <div className="text-[10px] text-slate-500">
                          {new Date(a.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </div>
                      </td>
                      <td className="py-3 text-right">
                        <a
                          href={a.etherscan_url || `https://sepolia.etherscan.io/tx/${a.tx_hash}`}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-emerald-400 hover:text-emerald-300 font-sans font-medium text-[11px] hover:underline"
                        >
                          Verify <ExternalLink className="w-3 h-3" />
                        </a>
                      </td>
                    </tr>
                  ))}
                  {anchorsList.length === 0 && (
                    <tr>
                      <td colSpan={6} className="py-6 text-center text-slate-500 font-sans">
                        No blockchain records anchored yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        <BlockchainAuditPanel />
      )}
    </div>
  );
};
