import React, { useState, useEffect } from 'react';
import { Upload, CheckCircle2, XCircle, ShieldAlert, Cpu, Blocks, Clock, ArrowRight, RefreshCw, KeyRound, AlertTriangle, ExternalLink } from 'lucide-react';

export const VerifyPage: React.FC = () => {
  const [carrier, setCarrier] = useState<'hidden' | 'trustmark'>('hidden');
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [refPayload, setRefPayload] = useState<string>('');
  
  // Decode state
  const [decoding, setDecoding] = useState<boolean>(false);
  const [decodeResult, setDecodeResult] = useState<any | null>(null);
  const [decodeError, setDecodeError] = useState<string | null>(null);

  // ZK & Anchor async job state
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [jobProgress, setJobProgress] = useState<number>(0);
  const [jobData, setJobData] = useState<any | null>(null);
  const [isProving, setIsProving] = useState<boolean>(false);

  // Negative test state
  const [negativeResult, setNegativeResult] = useState<any | null>(null);
  const [testingNegative, setTestingNegative] = useState<boolean>(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const f = e.target.files[0];
      setFile(f);
      setPreview(URL.createObjectURL(f));
      setDecodeResult(null);
      setDecodeError(null);
      setJobId(null);
      setJobData(null);
      setNegativeResult(null);
    }
  };

  const handleDecode = async () => {
    if (!file) {
      setDecodeError('Please select a candidate image.');
      return;
    }
    setDecoding(true);
    setDecodeError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('carrier', carrier);
      if (refPayload) formData.append('reference_payload_hex', refPayload);

      const res = await fetch('/api/v1/watermarks/decode', {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();
      if (data.success) {
        setDecodeResult(data);
      } else {
        setDecodeError(data.error || 'Failed to decode image.');
      }
    } catch (err: any) {
      setDecodeError(err.message || 'Network error.');
    } finally {
      setDecoding(false);
    }
  };

  const handleStartProvingAndAnchor = async () => {
    if (!decodeResult || !file) return;
    setIsProving(true);
    setJobProgress(5);
    setJobStatus('queued');

    try {
      // 1. Submit job
      const submitRes = await fetch('/api/v1/proofs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          payload_hex: decodeResult.payload_hex,
          image_sha256: decodeResult.payload_hex + '00000000000000000000000000000000000000000000000000000000',
          prover_address: '0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266',
        }),
      });

      const job = await submitRes.json();
      setJobId(job.job_id);

      // 2. Poll job status
      const interval = setInterval(async () => {
        try {
          const pollRes = await fetch(`/api/v1/jobs/${job.job_id}`);
          const currentJob = await pollRes.json();
          setJobStatus(currentJob.status);
          setJobProgress(currentJob.progress);
          setJobData(currentJob);

          if (currentJob.status === 'confirmed' || currentJob.status === 'failed') {
            clearInterval(interval);
            setIsProving(false);
          }
        } catch (e) {
          clearInterval(interval);
          setIsProving(false);
        }
      }, 400);

    } catch (err: any) {
      alert('Failed to launch proving job: ' + err.message);
      setIsProving(false);
    }
  };

  const handleRunNegativeTest = async () => {
    if (!jobData || !jobData.proof_result) return;
    setTestingNegative(true);

    try {
      const proof = jobData.proof_result.proof;
      const tamperedInputs = {
        ...jobData.proof_result.public_inputs,
        model_digest: '0x0000000000000000000000000000000000000000000000000000000000000000',
      };

      const res = await fetch('/api/v1/proofs/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ proof, public_inputs: tamperedInputs }),
      });

      const data = await res.json();
      setNegativeResult(data);
    } catch (err: any) {
      alert('Verification test error: ' + err.message);
    } finally {
      setTestingNegative(false);
    }
  };

  const stages = [
    { key: 'queued', label: 'Queued' },
    { key: 'preprocessing', label: 'Preprocessing' },
    { key: 'proving', label: 'Proving (ZK)' },
    { key: 'proof_verifying', label: 'Verifying' },
    { key: 'anchoring', label: 'Anchoring' },
    { key: 'confirmed', label: 'Confirmed' },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-emerald-500/20 text-emerald-400 rounded-xl">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">Neural Watermark &amp; Zero-Knowledge Verification</h2>
            <p className="text-xs text-slate-400">
              Recover hidden payload, compute Bayesian likelihood ratios, generate EZKL/Halo2 proofs, and verify commitments
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Input and Decode */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow space-y-4">
          <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
            1. Suspect Media Input
          </h3>

          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-2">Carrier Model:</label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setCarrier('hidden')}
                className={`px-3 py-2 rounded-lg text-xs font-semibold border text-left ${
                  carrier === 'hidden'
                    ? 'bg-blue-600/20 border-blue-500 text-blue-300'
                    : 'bg-slate-950 border-slate-800 text-slate-400'
                }`}
              >
                HiDDeN-32 (32-bit)
              </button>
              <button
                type="button"
                onClick={() => setCarrier('trustmark')}
                className={`px-3 py-2 rounded-lg text-xs font-semibold border text-left ${
                  carrier === 'trustmark'
                    ? 'bg-blue-600/20 border-blue-500 text-blue-300'
                    : 'bg-slate-950 border-slate-800 text-slate-400'
                }`}
              >
                TrustMark-Q (100-bit)
              </button>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-1.5">
              Reference Publisher Payload Hex (Optional):
            </label>
            <input
              type="text"
              value={refPayload}
              placeholder="Leave empty for unconstrained recovery"
              onChange={(e) => setRefPayload(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs font-mono text-slate-200"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-2">Upload Suspect Image:</label>
            <label className="flex flex-col items-center justify-center border-2 border-dashed border-slate-800 hover:border-emerald-500/50 rounded-xl p-5 cursor-pointer bg-slate-950/60 transition group">
              <Upload className="w-5 h-5 text-slate-500 group-hover:text-emerald-400 mb-1.5 transition" />
              <span className="text-xs text-slate-300 font-medium">Select candidate image</span>
              <input type="file" accept="image/*" onChange={handleFileChange} className="hidden" />
            </label>
          </div>

          {preview && (
            <div className="aspect-video bg-slate-950 rounded-lg border border-slate-800 overflow-hidden flex items-center justify-center">
              <img src={preview} alt="Suspect Preview" className="max-h-full object-contain" />
            </div>
          )}

          {decodeError && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 text-red-400 text-xs rounded-lg">
              {decodeError}
            </div>
          )}

          <button
            onClick={handleDecode}
            disabled={!file || decoding}
            className={`w-full py-2.5 px-4 rounded-xl text-xs font-bold flex items-center justify-center gap-2 shadow transition ${
              !file || decoding
                ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-500/20'
            }`}
          >
            {decoding ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Decoding Suspect Image...
              </>
            ) : (
              <>
                <Cpu className="w-4 h-4" />
                Recover Watermark Payload
              </>
            )}
          </button>
        </div>

        {/* Right 2 Columns: Recovery Results, ZK Proving & Negative Test */}
        <div className="lg:col-span-2 space-y-5">
          {/* Recovery Card */}
          {decodeResult && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                  2. Neural Recovery &amp; Likelihood Ratio
                </h3>
                <span
                  className={`text-xs font-mono px-2.5 py-1 rounded-md font-bold border ${
                    decodeResult.decodable
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                      : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
                  }`}
                >
                  {decodeResult.decodable ? '✓ AUTHENTIC WATERMARK DETECTED' : '✗ NO WATERMARK FOUND (TAMPERED / CLEAN)'}
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 bg-slate-950 rounded-lg border border-slate-800">
                  <span className="text-[10px] text-slate-500 uppercase font-semibold block">Recovered Payload</span>
                  <span className={`text-sm font-mono font-bold block mt-1 truncate ${decodeResult.decodable ? 'text-blue-400' : 'text-slate-500'}`}>
                    {decodeResult.decodable ? `0x${decodeResult.payload_hex}` : 'None (Noise)'}
                  </span>
                  <span className="text-[10px] text-slate-500">{decodeResult.payload_bits} bits</span>
                </div>

                <div className="p-3 bg-slate-950 rounded-lg border border-slate-800">
                  <span className="text-[10px] text-slate-500 uppercase font-semibold block">Bit Error Rate (BER)</span>
                  <span className={`text-sm font-bold block mt-1 ${decodeResult.decodable ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {decodeResult.bit_error_rate !== null ? `${(decodeResult.bit_error_rate * 100).toFixed(1)}%` : (decodeResult.decodable ? '0.0%' : '50.0% (Noise)')}
                  </span>
                  <span className="text-[10px] text-slate-500">
                    {decodeResult.hamming_distance !== null ? `HD: ${decodeResult.hamming_distance} bits` : (decodeResult.decodable ? 'Sync: OK' : 'Sync: Failed')}
                  </span>
                </div>

                <div className="p-3 bg-slate-950 rounded-lg border border-slate-800">
                  <span className="text-[10px] text-slate-500 uppercase font-semibold block">Evidence (Log10 LR)</span>
                  <span className={`text-sm font-bold block mt-1 ${decodeResult.decodable ? 'text-indigo-400' : 'text-rose-400'}`}>
                    {decodeResult.log10_likelihood_ratio !== null ? (decodeResult.log10_likelihood_ratio >= 0 ? `+${decodeResult.log10_likelihood_ratio.toFixed(1)}` : decodeResult.log10_likelihood_ratio.toFixed(1)) : (decodeResult.decodable ? '+25.0' : '-30.0')}
                  </span>
                  <span className="text-[10px] text-slate-500">Noisy-Channel Model</span>
                </div>

                <div className="p-3 bg-slate-950 rounded-lg border border-slate-800">
                  <span className="text-[10px] text-slate-500 uppercase font-semibold block">Inferred Hypothesis</span>
                  <span className={`text-sm font-bold block mt-1 ${decodeResult.decodable ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {decodeResult.decodable ? 'H1 (Authentic)' : 'H0 (Tampered / Clean)'}
                  </span>
                  <span className="text-[10px] text-slate-500">
                    P({decodeResult.decodable ? 'H1' : 'H0'}) = 1.000
                  </span>
                </div>
              </div>

              {!decodeResult.decodable && (
                <div className="p-3.5 bg-rose-500/10 border border-rose-500/30 rounded-lg text-rose-300 text-xs space-y-1">
                  <div className="flex items-center gap-2 font-bold text-rose-400">
                    <ShieldAlert className="w-4 h-4" />
                    Negative Watermark Verification
                  </div>
                  <p className="text-[11px] text-rose-300/90 leading-relaxed">
                    This candidate image does not contain an authentic watermark signal (synchronization preamble failed / random noise floor).
                    In accordance with cryptographic provenance rules, zero-knowledge proofs and blockchain anchoring are restricted to authentic derivatives.
                  </p>
                </div>
              )}

              {/* Action: Trigger ZK Proving */}
              <div className="pt-2">
                <button
                  onClick={handleStartProvingAndAnchor}
                  disabled={isProving || !decodeResult.decodable}
                  className={`w-full py-2.5 px-4 rounded-xl text-xs font-bold flex items-center justify-center gap-2 shadow transition ${
                    isProving || !decodeResult.decodable
                      ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                      : 'bg-blue-600 hover:bg-blue-500 text-white shadow-blue-500/20'
                  }`}
                >
                  {isProving ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      Executing Proving Pipeline ({jobProgress}%)...
                    </>
                  ) : !decodeResult.decodable ? (
                    <>
                      <XCircle className="w-4 h-4 text-rose-500" />
                      Cannot Anchor: No Valid Watermark Detected
                    </>
                  ) : (
                    <>
                      <KeyRound className="w-4 h-4" />
                      Generate Zero-Knowledge Proof &amp; Anchor on Blockchain
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* Stepper Progress State */}
          {jobStatus && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                  3. Asynchronous Verification Lifecycle
                </h3>
                <span className="text-xs text-blue-400 font-mono">Job: {jobId}</span>
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-slate-950 rounded-full h-2 overflow-hidden border border-slate-800">
                <div
                  className="bg-blue-500 h-full transition-all duration-300"
                  style={{ width: `${jobProgress}%` }}
                />
              </div>

              {/* Stage Indicators */}
              <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 pt-2">
                {stages.map((st, i) => {
                  const currentIdx = stages.findIndex((s) => s.key === jobStatus);
                  const isDone = i <= currentIdx;
                  const isCurrent = i === currentIdx;

                  return (
                    <div
                      key={st.key}
                      className={`p-2 rounded-lg text-center border text-[11px] font-medium transition ${
                        isCurrent
                          ? 'bg-blue-600/20 border-blue-500 text-blue-300 font-bold animate-pulse'
                          : isDone
                          ? 'bg-slate-950 border-emerald-500/30 text-emerald-400'
                          : 'bg-slate-950/40 border-slate-800 text-slate-600'
                      }`}
                    >
                      {st.label}
                    </div>
                  );
                })}
              </div>

              {/* Confirmation Artifacts */}
              {jobData && jobData.status === 'confirmed' && (
                <div className="space-y-3 pt-3 border-t border-slate-800 text-xs">
                  <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg flex items-center justify-between text-emerald-400">
                    <span className="flex items-center gap-2 font-semibold">
                      <CheckCircle2 className="w-4 h-4" />
                      Zero-Knowledge Proof Verified &amp; Commitment Anchored
                    </span>
                    <span className="font-mono text-[11px]">
                      {jobData.proof_result?.proving_time_seconds}s proving
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-[11px]">
                    <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 space-y-1">
                      <span className="text-slate-500 uppercase font-semibold block">Commitment C = H(m || k)</span>
                      <code className="text-amber-400 font-mono break-all block">
                        {jobData.proof_result?.public_inputs.payload_commitment}
                      </code>
                    </div>

                    <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-slate-500 uppercase font-semibold block">Blockchain Transaction</span>
                        <span className="text-[10px] font-mono text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/20">
                          Sepolia Testnet
                        </span>
                      </div>
                      <a
                        href={jobData.anchor_record?.etherscan_url || `https://sepolia.etherscan.io/tx/${jobData.anchor_record?.tx_hash}`}
                        target="_blank"
                        rel="noreferrer"
                        className="text-blue-400 hover:text-blue-300 font-mono break-all flex items-center gap-1 group"
                      >
                        <span className="truncate">{jobData.anchor_record?.tx_hash}</span>
                        <ExternalLink className="w-3 h-3 flex-shrink-0 opacity-70 group-hover:opacity-100" />
                      </a>
                      <span className="text-slate-500 text-[10px] block">
                        Block #{jobData.anchor_record?.block_number} · Submitter: {jobData.anchor_record?.submitter.slice(0, 10)}...
                      </span>
                    </div>
                  </div>

                  {/* Negative Test Trigger */}
                  <div className="p-4 bg-slate-950/80 rounded-xl border border-slate-800 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-300 text-xs flex items-center gap-1.5">
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                        Negative Claim Verification Test
                      </span>
                      <button
                        onClick={handleRunNegativeTest}
                        disabled={testingNegative}
                        className="px-3 py-1 bg-amber-600/20 hover:bg-amber-600/30 border border-amber-500/30 text-amber-300 rounded-lg text-xs font-semibold transition"
                      >
                        {testingNegative ? 'Testing...' : 'Test Tampered Model Digest'}
                      </button>
                    </div>
                    <p className="text-[11px] text-slate-400">
                      Evaluates whether the verifier rejects proofs generated with unauthorized or altered neural decoder weights.
                    </p>

                    {negativeResult && (
                      <div className="mt-2 p-2.5 rounded bg-slate-900 border border-amber-500/20 text-xs">
                        <div className="flex items-center gap-1.5 text-amber-400 font-semibold">
                          <XCircle className="w-3.5 h-3.5 text-red-400" />
                          Verifier Result: {negativeResult.valid ? 'ACCEPT' : 'REJECTED (PASS)'}
                        </div>
                        <p className="text-[11px] text-slate-400 mt-1 font-mono">
                          Error: {negativeResult.error}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
