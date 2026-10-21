import React, { useState, useEffect } from 'react';
import { Cpu, Blocks, CheckCircle2, Clock, ArrowRight } from 'lucide-react';

interface DashboardProps {
  onNavigate: (tab: string) => void;
}

export const DashboardPage: React.FC<DashboardProps> = ({ onNavigate }) => {
  const [anchors, setAnchors] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);

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
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  return (
    <div className="space-y-6">
      {/* Hero Banner */}
      <div className="bg-gradient-to-r from-slate-900 via-blue-950/40 to-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
        <div className="max-w-3xl">
          <h2 className="text-2xl font-bold text-white tracking-tight">
            ProvenanceLab Research Dashboard
          </h2>
          <p className="text-slate-300 text-sm mt-2 leading-relaxed">
            Demonstrating end-to-end integration of neural watermarking, zero-knowledge verifiable
            computation, and public Ethereum smart-contract anchoring for tamper-evident media authentication.
          </p>
        </div>

        {/* Quick Workflow Action Buttons */}
        <div className="flex flex-wrap gap-3 mt-6">
          <button
            onClick={() => onNavigate('embed')}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold shadow transition"
          >
            <Cpu className="w-4 h-4" />
            Embed Watermark
          </button>
          <button
            onClick={() => onNavigate('verify')}
            className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold shadow transition"
          >
            <CheckCircle2 className="w-4 h-4" />
            Verify Suspect Image
          </button>
          <button
            onClick={() => onNavigate('audit')}
            className="flex items-center gap-2 px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-xl text-xs font-semibold shadow transition"
          >
            <Blocks className="w-4 h-4" />
            Inspect Blockchain
          </button>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl shadow">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase">Anchored Assets</span>
            <Blocks className="w-4 h-4 text-amber-400" />
          </div>
          <span className="text-2xl font-bold text-white block mt-2">{anchors.length}</span>
          <span className="text-xs text-emerald-400 mt-1 block">Active in ProvenanceAnchor registry</span>
        </div>

        <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl shadow">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase">Proving Jobs</span>
            <Clock className="w-4 h-4 text-blue-400" />
          </div>
          <span className="text-2xl font-bold text-white block mt-2">{jobs.length}</span>
          <span className="text-xs text-blue-400 mt-1 block">Asynchronous ZK lifecycle jobs</span>
        </div>
      </div>

      {/* Recent Anchored Commitments */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
            <Blocks className="w-4 h-4 text-amber-400" />
            Recent On-Chain Commitments
          </h3>
          <button
            onClick={() => onNavigate('audit')}
            className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
          >
            View all <ArrowRight className="w-3 h-3" />
          </button>
        </div>

        <div className="space-y-3">
          {anchors.slice(0, 4).map((a, i) => (
            <div key={i} className="p-3 rounded-lg bg-slate-950/60 border border-slate-800 text-xs space-y-1">
              <div className="flex items-center justify-between">
                <span className="font-mono text-slate-300 font-semibold">
                  {a.asset_id.slice(0, 18)}...
                </span>
                <span className="text-slate-500 text-[10px]">
                  Block #{a.block_number}
                </span>
              </div>
              <div className="flex items-center justify-between text-slate-400">
                <span className="text-[11px] font-mono text-amber-400/90 truncate max-w-[200px]">
                  C: {a.commitment.slice(0, 20)}...
                </span>
                <span className="text-slate-500 text-[10px]">
                  {new Date(a.timestamp * 1000).toLocaleTimeString()}
                </span>
              </div>
            </div>
          ))}
          {anchors.length === 0 && (
            <p className="text-xs text-slate-500 text-center py-6">No commitments anchored yet.</p>
          )}
        </div>
      </div>
    </div>
  );
};
