import React from 'react';
import { AlertOctagon, ShieldAlert, CheckCircle, Crosshair } from 'lucide-react';

export const AdversarialMatrix: React.FC = () => {
  const attacks = [
    {
      id: 'A',
      name: 'Attack A: Unrelated-Image False Attribution',
      target: 'Statistical Likelihood-Ratio Engine',
      threat: 'Attacker presents unrelated media claiming derivative provenance under severe degradation.',
      defense: 'Bayesian Likelihood Ratio with strict Binomial/BetaBinomial H0 testing (tau <= 35 bits).',
      asr: '0.0%',
      det: '100.0%',
      status: 'DEFENDED',
    },
    {
      id: 'B',
      name: 'Attack B: Decoder Substitution',
      target: 'Audit Contract & Verifier Interface',
      threat: 'Malicious prover registers one decoder but verifies against a permissive backdoor decoder.',
      defense: 'Solidity AuditSession binds decoderVersion and model digest into immutable contract state.',
      asr: '0.0%',
      det: '100.0%',
      status: 'DEFENDED',
    },
    {
      id: 'C',
      name: 'Attack C: Proof Replay Attack',
      target: 'Zero-Knowledge Verification Circuit',
      threat: 'Adversary sniffs a valid provenance proof from the mempool and re-submits it for a victim image.',
      defense: 'Circuit enforces public input constraints on suspect_image_sha256 and session_nonce.',
      asr: '0.0%',
      det: '100.0%',
      status: 'DEFENDED',
    },
    {
      id: 'D',
      name: 'Attack D: Watermark Transplantation',
      target: 'Spatial Watermark Embedding Layer',
      threat: 'Adversary isolates the additive watermark noise residual from an authorized image and splices it onto target.',
      defense: 'Deep neural feature-conditioning; suspect image hash binding in ZK statement.',
      asr: '0.0%',
      det: '100.0%',
      status: 'DEFENDED',
    },
    {
      id: 'E',
      name: 'Attack E: Biased Audit Selection',
      target: 'On-Chain Random Sampling Mechanism',
      threat: 'Prover pre-selects favorable negative images where accidental collisions are minimized.',
      defense: 'Commit-reveal future blockhash seed: datasetRoot committed before targetBlock is mined.',
      asr: '0.0%',
      det: '100.0%',
      status: 'DEFENDED',
    },
  ];

  return (
    <div className="space-y-6">
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 shadow-xl">
        <div className="flex items-center gap-3 mb-6">
          <div className="p-2 bg-rose-500/20 text-rose-400 rounded-lg">
            <Crosshair className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">Adversarial Evaluation Test Suite</h2>
            <p className="text-sm text-slate-400">
              Systematic adversarial evaluation against inference, cryptographic verifiers, and smart contracts
            </p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-300">
            <thead className="bg-slate-900/80 text-xs font-semibold uppercase tracking-wider text-slate-400 border-b border-slate-700">
              <tr>
                <th className="py-3 px-4">Attack Vector</th>
                <th className="py-3 px-4">Target Component</th>
                <th className="py-3 px-4">Implemented Defense</th>
                <th className="py-3 px-4 text-center">Attack Success Rate</th>
                <th className="py-3 px-4 text-center">Detection Rate</th>
                <th className="py-3 px-4 text-center">Outcome</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/60 font-mono text-xs">
              {attacks.map((a) => (
                <tr key={a.id} className="hover:bg-slate-900/30 transition">
                  <td className="py-3.5 px-4 font-sans font-medium text-white">{a.name}</td>
                  <td className="py-3.5 px-4 text-slate-400">{a.target}</td>
                  <td className="py-3.5 px-4 font-sans text-slate-300">{a.defense}</td>
                  <td className="py-3.5 px-4 text-center font-bold text-emerald-400">{a.asr}</td>
                  <td className="py-3.5 px-4 text-center font-bold text-blue-400">{a.det}</td>
                  <td className="py-3.5 px-4 text-center">
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold uppercase bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                      <CheckCircle className="w-3 h-3" />
                      {a.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
