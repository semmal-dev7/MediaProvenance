import React, { useState, useEffect } from 'react';
import { Upload, CheckCircle2, XCircle, ShieldAlert, Cpu, Blocks, Clock, ArrowRight, RefreshCw, KeyRound, AlertTriangle, ExternalLink, ShieldCheck } from 'lucide-react';
import { readRecordFromSepoliaFree, OnChainRecord } from '../services/web3';

export const VerifyPage: React.FC = () => {
  const [carrier, setCarrier] = useState<'pureconv' | 'hidden' | 'trustmark'>('pureconv');
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

  // Image Verifier (Zero Gas) State
  const [isVerifyingFree, setIsVerifyingFree] = useState<boolean>(false);
  const [onChainRecord, setOnChainRecord] = useState<OnChainRecord | null>(null);
  const [verifierError, setVerifierError] = useState<string | null>(null);

  const handleVerifyFreeOnChain = async () => {
    if (!decodeResult) return;
    setIsVerifyingFree(true);
    setVerifierError(null);
    setOnChainRecord(null);

    try {
      const assetId = decodeResult.image_sha256 || ('0x' + decodeResult.payload_hex.padEnd(64, '0'));
      const rec = await readRecordFromSepoliaFree(assetId);
      setOnChainRecord(rec);
    } catch (err: any) {
      setVerifierError(err.message || 'Error querying Sepolia contract state.');
    } finally {
      setIsVerifyingFree(false);
    }
  };

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

      if (!res.ok) {
        let errMsg = `Server returned status ${res.status}`;
        try {
          const errData = await res.json();
          if (errData.detail) errMsg = typeof errData.detail === 'string' ? errData.detail : JSON.stringify(errData.detail);
          else if (errData.error) errMsg = errData.error;
        } catch {
          // If body is not JSON (e.g. plain text 500 error), ignore parse error
        }
        setDecodeError(errMsg);
        return;
      }

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
          image_sha256: decodeResult.image_sha256 || ('0x' + decodeResult.payload_hex.padEnd(64, '0')),
          prover_address: '0xc3105176265bd16F86d0A3ff61f3aC0fE00e6007',
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
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => setCarrier('pureconv')}
                className={`px-2.5 py-2 rounded-lg text-xs font-semibold border text-left transition ${
                  carrier === 'pureconv'
                    ? 'bg-blue-600/20 border-blue-500 text-blue-300'
                    : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                }`}
              >
                <span className="block font-bold">PureConv-32</span>
                <span className="text-[10px] text-slate-500">Pure Neural · ZK</span>
              </button>
              <button
                type="button"
                onClick={() => setCarrier('hidden')}
                className={`px-2.5 py-2 rounded-lg text-xs font-semibold border text-left transition ${
                  carrier === 'hidden'
                    ? 'bg-blue-600/20 border-blue-500 text-blue-300'
                    : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                }`}
              >
                <span className="block font-bold">HiDDeN-32</span>
                <span className="text-[10px] text-slate-500">32-bit · Legacy</span>
              </button>
              <button
                type="button"
                onClick={() => setCarrier('trustmark')}
                className={`px-2.5 py-2 rounded-lg text-xs font-semibold border text-left transition ${
                  carrier === 'trustmark'
                    ? 'bg-blue-600/20 border-blue-500 text-blue-300'
                    : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                }`}
              >
                <span className="block font-bold">TrustMark-Q</span>
                <span className="text-[10px] text-slate-500">100-bit · High-Res</span>
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
                    decodeResult.watermark_detected && decodeResult.payload_matches === true
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                      : decodeResult.payload_matches === false
                      ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                      : decodeResult.payload_hex && (decodeResult.payload_matches === null || decodeResult.payload_matches === undefined)
                      ? 'bg-slate-800 border-slate-700 text-slate-300'
                      : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
                  }`}
                >
                  {decodeResult.watermark_detected && decodeResult.payload_matches === true
                    ? '✓ AUTHENTIC WATERMARK VERIFIED'
                    : decodeResult.payload_matches === false
                    ? '⚠ PAYLOAD MISMATCH (H0 UNRELATED)'
                    : decodeResult.payload_hex && (decodeResult.payload_matches === null || decodeResult.payload_matches === undefined)
                    ? 'ℹ UNVERIFIED CANDIDATE (NO REFERENCE CLAIM)'
                    : '✗ NO WATERMARK SIGNAL DETECTED'}
                </span>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-3 bg-slate-950 rounded-lg border border-slate-800">
                  <span className="text-[10px] text-slate-500 uppercase font-semibold block">Recovered Payload</span>
                  <span className={`text-sm font-mono font-bold block mt-1 truncate ${decodeResult.payload_hex ? 'text-blue-400' : 'text-slate-500'}`}>
                    {decodeResult.payload_hex ? `0x${decodeResult.payload_hex}` : 'None Detected'}
                  </span>
                  <span className="text-[10px] text-slate-500">
                    {decodeResult.payload_hex ? `${decodeResult.payload_bits} bits extracted` : (decodeResult.error ? 'No Signal' : 'Failed')}
                  </span>
                </div>

                <div className="p-3 bg-slate-950 rounded-lg border border-slate-800">
                  <span className="text-[10px] text-slate-500 uppercase font-semibold block">Bit Error Rate (BER)</span>
                  <span className={`text-sm font-bold block mt-1 ${
                    decodeResult.bit_error_rate !== null && decodeResult.bit_error_rate !== undefined
                      ? (decodeResult.bit_error_rate <= 0.25 ? 'text-emerald-400' : 'text-rose-400')
                      : 'text-slate-500'
                  }`}>
                    {decodeResult.bit_error_rate !== null && decodeResult.bit_error_rate !== undefined
                      ? `${(decodeResult.bit_error_rate * 100).toFixed(1)}%`
                      : 'N/A (Reference Required)'}
                  </span>
                  <span className="text-[10px] text-slate-500">
                    {decodeResult.hamming_distance !== null && decodeResult.hamming_distance !== undefined
                      ? `HD: ${decodeResult.hamming_distance} / ${decodeResult.payload_bits} bits (Measured)`
                      : 'Requires Reference Claim'}
                  </span>
                </div>

                <div className="p-3 bg-slate-950 rounded-lg border border-slate-800">
                  <span className="text-[10px] text-slate-500 uppercase font-semibold block">Evidence (Log10 LR)</span>
                  <span className={`text-sm font-bold block mt-1 ${
                    decodeResult.log10_likelihood_ratio !== null && decodeResult.log10_likelihood_ratio !== undefined
                      ? (decodeResult.log10_likelihood_ratio >= 0 ? 'text-indigo-400' : 'text-rose-400')
                      : 'text-slate-500'
                  }`}>
                    {decodeResult.log10_likelihood_ratio !== null && decodeResult.log10_likelihood_ratio !== undefined
                      ? (decodeResult.log10_likelihood_ratio >= 0 ? `+${decodeResult.log10_likelihood_ratio.toFixed(2)}` : decodeResult.log10_likelihood_ratio.toFixed(2))
                      : 'N/A'}
                  </span>
                  <span className="text-[10px] text-slate-500">
                    {decodeResult.posterior_probability_h1 !== null && decodeResult.posterior_probability_h1 !== undefined
                      ? `P(H1) = ${decodeResult.posterior_probability_h1.toFixed(3)}`
                      : 'Bayesian Evidence'}
                  </span>
                </div>

                <div className="p-3 bg-slate-950 rounded-lg border border-slate-800">
                  <span className="text-[10px] text-slate-500 uppercase font-semibold block">Inferred Hypothesis</span>
                  <span className={`text-sm font-bold block mt-1 ${
                    decodeResult.inferred_hypothesis === 'H1'
                      ? 'text-emerald-400'
                      : decodeResult.inferred_hypothesis === 'H0'
                      ? 'text-rose-400'
                      : 'text-amber-400'
                  }`}>
                    {decodeResult.inferred_hypothesis === 'H1'
                      ? 'H1 (Derivative)'
                      : decodeResult.inferred_hypothesis === 'H0'
                      ? 'H0 (Unrelated)'
                      : decodeResult.payload_hex
                      ? 'H2 (Unanchored Candidate)'
                      : 'H2 (Undecodable)'}
                  </span>
                  <span className="text-[10px] text-slate-500">
                    {decodeResult.posterior_probability_h1 !== null && decodeResult.posterior_probability_h1 !== undefined
                      ? `P(H1) = ${decodeResult.posterior_probability_h1.toFixed(3)}`
                      : 'Unconditioned'}
                  </span>
                </div>
              </div>

              {/* Status Diagnostic Bar */}
              <div className="p-3 bg-slate-950/70 rounded-lg border border-slate-800/80 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                <div>
                  <span className="text-slate-500 block text-[10px] uppercase font-semibold">Signal Detected:</span>
                  <span className={`font-mono font-bold ${
                    decodeResult.watermark_detected && decodeResult.payload_matches === true
                      ? 'text-emerald-400'
                      : decodeResult.payload_matches === false
                      ? 'text-rose-400'
                      : 'text-slate-400'
                  }`}>
                    {decodeResult.watermark_detected && decodeResult.payload_matches === true
                      ? 'YES (VERIFIED)'
                      : decodeResult.payload_matches === false
                      ? 'MISMATCH (H0)'
                      : 'UNVERIFIED (NO CLAIM)'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px] uppercase font-semibold">Payload Recovered:</span>
                  <span className={`font-mono font-bold ${decodeResult.payload_recovered ? 'text-emerald-400' : 'text-slate-400'}`}>
                    {decodeResult.payload_recovered ? 'YES' : 'NO'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px] uppercase font-semibold">Matches Reference:</span>
                  <span className={`font-mono font-bold ${
                    decodeResult.payload_matches === true
                      ? 'text-emerald-400'
                      : decodeResult.payload_matches === false
                      ? 'text-rose-400'
                      : 'text-slate-500'
                  }`}>
                    {decodeResult.payload_matches === true
                      ? 'MATCH (VERIFIED)'
                      : decodeResult.payload_matches === false
                      ? 'MISMATCH (H0)'
                      : 'UNANCHORED (H2)'}
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px] uppercase font-semibold">Diagnostic:</span>
                  <span className="text-slate-400 font-mono text-[11px] truncate block" title={decodeResult.failure_reason || decodeResult.error || 'Normal'}>
                    {decodeResult.mean_logit_magnitude
                      ? `RMS: ${decodeResult.rms_energy?.toFixed(2) || '0.00'} | CNN Act: ±${decodeResult.mean_logit_magnitude.toFixed(2)}`
                      : (decodeResult.failure_reason || (decodeResult.watermark_detected ? 'Authentic' : 'No Signal'))}
                  </span>
                </div>
              </div>

              {decodeResult.watermark_detected && decodeResult.payload_matches === true && (
                <div className="p-3.5 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-emerald-300 text-xs space-y-1">
                  <div className="flex items-center gap-2 font-bold text-emerald-400">
                    <CheckCircle2 className="w-4 h-4" />
                    Watermark Signal Detected &amp; Verified (Hypothesis H1)
                  </div>
                  <p className="text-[11px] text-emerald-200/90 leading-relaxed">
                    Extracted 32-bit payload <code className="font-mono text-white bg-emerald-950 px-1 py-0.5 rounded">0x{decodeResult.payload_hex}</code> with Bayesian log-likelihood ratio {decodeResult.log10_likelihood_ratio !== null ? (decodeResult.log10_likelihood_ratio >= 0 ? `+${decodeResult.log10_likelihood_ratio.toFixed(2)}` : decodeResult.log10_likelihood_ratio.toFixed(2)) : 'high'} and bit error rate {decodeResult.bit_error_rate !== null ? `${(decodeResult.bit_error_rate * 100).toFixed(1)}%` : '0.0%'}. Signal meets mathematical detection tolerance under hypothesis H1.
                  </p>
                </div>
              )}

              {!decodeResult.watermark_detected && decodeResult.payload_matches === false && (
                <div className="p-3.5 bg-rose-500/10 border border-rose-500/30 rounded-lg text-rose-300 text-xs space-y-1">
                  <div className="flex items-center gap-2 font-bold text-rose-400">
                    <ShieldAlert className="w-4 h-4" />
                    Watermark Rejection (Payload Mismatch)
                  </div>
                  <p className="text-[11px] text-rose-300/90 leading-relaxed">
                    {decodeResult.error || 'This candidate image does not match the claimed publisher reference payload.'}
                  </p>
                </div>
              )}

              {decodeResult.payload_hex && (decodeResult.payload_matches === null || decodeResult.payload_matches === undefined) && (
                <div className="p-3.5 bg-blue-500/10 border border-blue-500/30 rounded-lg text-blue-300 text-xs space-y-1">
                  <div className="flex items-center gap-2 font-bold text-blue-400">
                    <ShieldCheck className="w-4 h-4" />
                    Candidate Payload Extracted (Unanchored Claim)
                  </div>
                  <p className="text-[11px] text-blue-200/90 leading-relaxed">
                    Extracted candidate payload <code className="font-mono text-white bg-blue-950 px-1 py-0.5 rounded">0x{decodeResult.payload_hex}</code> from neural decoder. Provenance is currently unanchored (state H2). To authenticate, enter your expected Reference Payload above, or run an on-chain audit below.
                  </p>
                </div>
              )}

              {!decodeResult.payload_hex && (
                <div className="p-3.5 bg-rose-500/10 border border-rose-500/30 rounded-lg text-rose-300 text-xs space-y-1">
                  <div className="flex items-center gap-2 font-bold text-rose-400">
                    <ShieldAlert className="w-4 h-4" />
                    No Watermark Recovered
                  </div>
                  <p className="text-[11px] text-rose-300/90 leading-relaxed">
                    {decodeResult.error || 'No decodable watermark signal was recovered from this candidate image.'}
                  </p>
                </div>
              )}

              {/* Action: Image Verifier (Free Sepolia Read) & Proving Pipeline */}
              <div className="pt-2 space-y-3">
                <div className="p-3.5 bg-slate-950 rounded-xl border border-blue-500/30 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-blue-300 uppercase tracking-wide flex items-center gap-1.5">
                      <ShieldCheck className="w-4 h-4 text-blue-400" />
                      Image Verifier Role (Free / Zero Gas)
                    </span>
                    <span className="text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded font-mono font-bold">
                      Gas Fee: 0.00 ETH ($0.00)
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 leading-relaxed">
                    Verify this suspect image off-chain and read the publisher's registered commitment directly from the Ethereum Sepolia smart contract. No MetaMask wallet connection or gas payment required.
                  </p>

                  <button
                    onClick={handleVerifyFreeOnChain}
                    disabled={isVerifyingFree || !decodeResult.payload_hex}
                    className={`w-full py-2 px-3 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 transition ${
                      isVerifyingFree || !decodeResult.payload_hex
                        ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                        : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-sm'
                    }`}
                  >
                    {isVerifyingFree ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        Querying Sepolia Contract (Free)...
                      </>
                    ) : (
                      <>
                        <Blocks className="w-3.5 h-3.5" />
                        Audit On-Chain Record (Free / 0 Gas)
                      </>
                    )}
                  </button>

                  {verifierError && (
                    <div className="p-2 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
                      {verifierError}
                    </div>
                  )}

                  {onChainRecord && (
                    <div className="mt-2 p-3 bg-slate-900 border border-slate-800 rounded-lg text-xs space-y-2">
                      <div className="flex items-center justify-between font-bold">
                        <span className={onChainRecord.exists ? 'text-emerald-400 flex items-center gap-1' : 'text-amber-400 flex items-center gap-1'}>
                          {onChainRecord.exists ? <CheckCircle2 className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
                          {onChainRecord.exists ? 'Authentic Record Confirmed on Sepolia' : 'Not Yet Anchored On-Chain'}
                        </span>
                        <span className="text-[10px] text-slate-500 font-mono">Cost: 0 Gas</span>
                      </div>

                      {onChainRecord.exists ? (
                        <div className="text-[11px] text-slate-300 space-y-1 pt-1 border-t border-slate-800">
                          <div>
                            <span className="text-slate-500 font-semibold">Publisher Wallet: </span>
                            <code className="text-amber-300 font-mono break-all">{onChainRecord.submitter}</code>
                          </div>
                          <div>
                            <span className="text-slate-500 font-semibold">Registered Timestamp: </span>
                            <span>{onChainRecord.dateFormatted}</span>
                          </div>
                          <div>
                            <span className="text-slate-500 font-semibold">On-Chain Commitment: </span>
                            <code className="text-blue-300 font-mono break-all block mt-0.5">{onChainRecord.commitment}</code>
                          </div>
                          <div>
                            <span className="text-slate-500 font-semibold">Contract: </span>
                            <a
                              href="https://sepolia.etherscan.io/address/0x6D8C82dc761Ed9bac93ca99987b91614B90Ad43F"
                              target="_blank"
                              rel="noreferrer"
                              className="text-blue-400 hover:text-blue-300 inline-flex items-center gap-1 font-mono"
                            >
                              0x6D8C82...d43F <ExternalLink className="w-3 h-3" />
                            </a>
                          </div>
                        </div>
                      ) : (
                        <p className="text-[11px] text-slate-400">
                          No matching commitment found in ProvenanceAnchor.sol for this image hash.
                        </p>
                      )}
                    </div>
                  )}
                </div>

                {/* Alternative Automated Pipeline */}
                <button
                  onClick={handleStartProvingAndAnchor}
                  disabled={isProving || !decodeResult.payload_hex}
                  className={`w-full py-2.5 px-4 rounded-xl text-xs font-bold flex items-center justify-center gap-2 shadow transition ${
                    isProving || !decodeResult.payload_hex
                      ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                      : 'bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700'
                  }`}
                >
                  {isProving ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      Executing Proving Pipeline ({jobProgress}%)...
                    </>
                  ) : (
                    <>
                      <KeyRound className="w-4 h-4" />
                      Run Full ZK Benchmark &amp; Service Pipeline
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
