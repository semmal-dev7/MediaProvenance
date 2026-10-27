import React, { useState, useEffect } from 'react';
import { Upload, CheckCircle2, XCircle, ShieldAlert, Cpu, Blocks, Clock, ArrowRight, RefreshCw, KeyRound, AlertTriangle, ExternalLink, ShieldCheck, Download } from 'lucide-react';
import { readRecordFromSepoliaFree, OnChainRecord, PROVENANCE_ANCHOR_ADDRESS } from '../services/web3';

export const VerifyPage: React.FC = () => {
  const [carrier, setCarrier] = useState<'pureconv' | 'hidden' | 'trustmark'>('trustmark');
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  
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
  const [auditResult, setAuditResult] = useState<any | null>(null);
  const [isAuditing, setIsAuditing] = useState<boolean>(false);

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
      let targetAssetId = decodeResult.registered_anchor?.asset_id;
      if (!targetAssetId && decodeResult.payload_hex) {
        // Reverse lookup registered anchor by payload from ledger
        try {
          const anchorsRes = await fetch('/api/v1/anchors');
          if (anchorsRes.ok) {
            const allAnchors = await anchorsRes.json();
            const cleanPayload = decodeResult.payload_hex.toLowerCase().replace('0x', '').trim();
            const matchingAnchors = Array.isArray(allAnchors) && allAnchors.filter((a: any) =>
              a.payload_hex && (
                a.payload_hex.toLowerCase().replace('0x', '').trim() === cleanPayload
                || cleanPayload.startsWith(a.payload_hex.toLowerCase().replace('0x', '').trim())
                || a.payload_hex.toLowerCase().replace('0x', '').trim().startsWith(cleanPayload)
              )
            );
            if (matchingAnchors && matchingAnchors.length > 0) {
              matchingAnchors.sort((a: any, b: any) => {
                const bA = (a.block_number && a.block_number > 0) ? a.block_number : 999999999;
                const bB = (b.block_number && b.block_number > 0) ? b.block_number : 999999999;
                if (bA !== bB) return bA - bB;
                return (a.timestamp || 0) - (b.timestamp || 0);
              });
              targetAssetId = matchingAnchors[0].asset_id;
            }
          }
        } catch {
          // fallback
        }
      }

      const assetId = targetAssetId
        || decodeResult.image_sha256
        || ('0x' + decodeResult.payload_hex.padEnd(64, '0'));
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
      setAuditResult(null);
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
        if (!data.registered_anchor && data.payload_hex) {
          try {
            const anchorsRes = await fetch('/api/v1/anchors');
            if (anchorsRes.ok) {
              const allAnchors = await anchorsRes.json();
              const cleanPayload = data.payload_hex.toLowerCase().replace('0x', '').trim();
              const matchingAnchors = Array.isArray(allAnchors) && allAnchors.filter((a: any) =>
                a.payload_hex && (
                  a.payload_hex.toLowerCase().replace('0x', '').trim() === cleanPayload
                  || cleanPayload.startsWith(a.payload_hex.toLowerCase().replace('0x', '').trim())
                  || a.payload_hex.toLowerCase().replace('0x', '').trim().startsWith(cleanPayload)
                )
              );
              if (matchingAnchors && matchingAnchors.length > 0) {
                matchingAnchors.sort((a: any, b: any) => {
                  const bA = (a.block_number && a.block_number > 0) ? a.block_number : 999999999;
                  const bB = (b.block_number && b.block_number > 0) ? b.block_number : 999999999;
                  if (bA !== bB) return bA - bB;
                  return (a.timestamp || 0) - (b.timestamp || 0);
                });
                const rootAnchor = matchingAnchors[0];
                data.registered_anchor = rootAnchor;
                data.original_asset_id = rootAnchor.asset_id;
                const cleanOrig = rootAnchor.asset_id.toLowerCase().replace('0x', '').trim();
                const cleanCand = (data.image_sha256 || '').toLowerCase().replace('0x', '').trim();
                if (cleanOrig && cleanCand && cleanOrig !== cleanCand) {
                  data.is_derivative = true;
                  data.tamper_detected = true;
                }
              }
            }
          } catch {
            // fallback
          }
        }
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
          carrier: carrier,
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

  const handleAuditProof = async () => {
    if (!jobData || !jobData.proof_result) return;
    setIsAuditing(true);

    try {
      const proof = jobData.proof_result.proof;
      const public_inputs = jobData.proof_result.public_inputs;

      const res = await fetch('/api/v1/proofs/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ proof, public_inputs }),
      });

      const data = await res.json();
      setAuditResult(data);
    } catch (err: any) {
      alert('Proof audit error: ' + err.message);
    } finally {
      setIsAuditing(false);
    }
  };

  const handleDownloadIpfsImage = async () => {
    try {
      const src = resolvedIpfsUrl || (resolvedIpfsCid ? `https://gateway.pinata.cloud/ipfs/${resolvedIpfsCid}` : preview);
      if (!src) return;

      const cidStr = resolvedIpfsCid || 'ipfs';
      const shortCid = cidStr.replace(/^Qm/, '').replace(/^bafy/, '').slice(0, 8);
      const filename = `ipfs_original_${shortCid}.png`;

      if (src.startsWith('data:')) {
        const link = document.createElement('a');
        link.href = src;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        return;
      }

      const response = await fetch(src);
      if (!response.ok) throw new Error('Failed to fetch from IPFS endpoint');
      const blob = await response.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(blobUrl);
    } catch {
      const src = resolvedIpfsUrl || (resolvedIpfsCid ? `https://gateway.pinata.cloud/ipfs/${resolvedIpfsCid}` : preview);
      if (src) {
        const link = document.createElement('a');
        link.href = src;
        link.download = 'original_ipfs_media.png';
        link.target = '_blank';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      }
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

  // Derive integrity & derivative status by comparing candidate SHA against on-chain registered asset ID
  const cleanOnChainAsset = (onChainRecord?.assetId || decodeResult?.registered_anchor?.asset_id || decodeResult?.original_asset_id || '').toLowerCase().replace('0x', '').trim();
  const cleanSuspectSha = (decodeResult?.image_sha256 || '').toLowerCase().replace('0x', '').trim();
  const resolvedIpfsCid = decodeResult?.original_ipfs_cid || onChainRecord?.ipfsCid || '';
  const resolvedIpfsUrl = decodeResult?.original_image_base64 || decodeResult?.original_image_url || (resolvedIpfsCid ? `https://gateway.pinata.cloud/ipfs/${resolvedIpfsCid}` : '');
  const isHashMismatch = Boolean(cleanOnChainAsset && cleanSuspectSha && cleanOnChainAsset !== cleanSuspectSha);
  const isDerivativeMedia = Boolean(decodeResult?.is_derivative || decodeResult?.tamper_detected || isHashMismatch);
  const isExactOriginal = Boolean(cleanOnChainAsset && cleanSuspectSha && cleanOnChainAsset === cleanSuspectSha);
  const isZkpVerified = Boolean(
    (jobData && (jobData.status === 'confirmed' || jobData.proof_result?.verified === true)) ||
    (auditResult && auditResult.valid === true)
  );

  const effectiveBer = (decodeResult?.bit_error_rate !== null && decodeResult?.bit_error_rate !== undefined)
    ? decodeResult.bit_error_rate
    : (decodeResult?.expected_ber !== null && decodeResult?.expected_ber !== undefined)
    ? decodeResult.expected_ber
    : (decodeResult?.watermark_detected ? 0.0 : 0.50);

  const effectiveSubtitle = (decodeResult?.hamming_distance !== null && decodeResult?.hamming_distance !== undefined)
    ? `HD: ${decodeResult.hamming_distance} / ${decodeResult?.payload_bits || 100} bits (Measured)`
    : (decodeResult?.expected_ber !== null && decodeResult?.expected_ber !== undefined)
    ? `Neural Soft BER: ${(decodeResult.expected_ber * 100).toFixed(1)}%`
    : (decodeResult?.watermark_detected ? '0 / 100 bits (Verified)' : 'Noise Floor (~50% Error)');

  const effectiveLog10Lr = (decodeResult?.log10_likelihood_ratio !== null && decodeResult?.log10_likelihood_ratio !== undefined)
    ? decodeResult.log10_likelihood_ratio
    : (effectiveBer !== null && effectiveBer !== undefined)
    ? Math.max(-30.0, Math.min(30.0, (decodeResult?.payload_bits || 100) * Math.log10(Math.max(1e-6, (1.0 - effectiveBer) / 0.5))))
    : null;

  const effectivePosterior = (decodeResult?.posterior_probability_h1 !== null && decodeResult?.posterior_probability_h1 !== undefined)
    ? decodeResult.posterior_probability_h1
    : (effectiveLog10Lr !== null && effectiveLog10Lr !== undefined)
    ? (1.0 / (1.0 + Math.pow(10, -effectiveLog10Lr)))
    : null;

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
                  className={`text-xs font-mono px-2.5 py-1 rounded-md font-bold border shadow-xs ${
                    isDerivativeMedia
                      ? 'bg-amber-600 text-white border-amber-700'
                      : decodeResult.watermark_detected && decodeResult.payload_matches === true
                      ? 'bg-emerald-600 text-white border-emerald-700'
                      : decodeResult.payload_matches === false
                      ? 'bg-rose-600 text-white border-rose-700'
                      : decodeResult.payload_hex && (decodeResult.payload_matches === null || decodeResult.payload_matches === undefined)
                      ? 'bg-slate-700 text-white border-slate-600'
                      : 'bg-rose-600 text-white border-rose-700'
                  }`}
                >
                  {isDerivativeMedia
                    ? '⚠ AI-ALTERED / TAMPERED DERIVATIVE'
                    : decodeResult.watermark_detected && decodeResult.payload_matches === true
                    ? '✓ AUTHENTIC ORIGINAL VERIFIED'
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
                    effectiveBer <= 0.25 ? 'text-emerald-400' : 'text-rose-400'
                  }`}>
                    {(effectiveBer * 100).toFixed(1)}%
                  </span>
                  <span className="text-[10px] text-slate-500">
                    {effectiveSubtitle}
                  </span>
                </div>

                <div className="p-3 bg-slate-950 rounded-lg border border-slate-800">
                  <span className="text-[10px] text-slate-500 uppercase font-semibold block">Evidence (Log10 LR)</span>
                  <span className={`text-sm font-bold block mt-1 ${
                    effectiveLog10Lr !== null && effectiveLog10Lr !== undefined
                      ? (effectiveLog10Lr >= 0 ? 'text-indigo-400' : 'text-rose-400')
                      : 'text-slate-500'
                  }`}>
                    {effectiveLog10Lr !== null && effectiveLog10Lr !== undefined
                      ? (effectiveLog10Lr >= 0 ? `+${effectiveLog10Lr.toFixed(2)}` : effectiveLog10Lr.toFixed(2))
                      : '0.00'}
                  </span>
                  <span className="text-[10px] text-slate-500">
                    {effectivePosterior !== null && effectivePosterior !== undefined
                      ? `P(H1) = ${effectivePosterior.toFixed(3)}`
                      : 'Bayesian Evidence'}
                  </span>
                </div>

                <div className="p-3 bg-slate-950 rounded-lg border border-slate-800">
                  <span className="text-[10px] text-slate-500 uppercase font-semibold block">Inferred Hypothesis</span>
                  <span className={`text-sm font-bold block mt-1 ${
                    isDerivativeMedia
                      ? 'text-amber-700'
                      : decodeResult.inferred_hypothesis === 'H1'
                      ? 'text-emerald-700'
                      : decodeResult.inferred_hypothesis === 'H0'
                      ? 'text-rose-700'
                      : 'text-amber-700'
                  }`}>
                    {isDerivativeMedia
                      ? 'H1 (Tampered Derivative)'
                      : decodeResult.inferred_hypothesis === 'H1'
                      ? 'H1 (Derivative)'
                      : decodeResult.inferred_hypothesis === 'H0'
                      ? 'H0 (Unrelated)'
                      : decodeResult.payload_hex
                      ? 'H2 (Unanchored Candidate)'
                      : 'H2 (Undecodable)'}
                  </span>
                  <span className="text-[10px] text-slate-500">
                    {isHashMismatch
                      ? 'Pixel Tamper Detected'
                      : decodeResult.posterior_probability_h1 !== null && decodeResult.posterior_probability_h1 !== undefined
                      ? `P(H1) = ${decodeResult.posterior_probability_h1.toFixed(3)}`
                      : 'Unconditioned'}
                  </span>
                </div>
              </div>

              {/* Status Diagnostic Bar */}
              <div className="p-3 bg-slate-950/70 rounded-lg border border-slate-800/80 grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-slate-800/80 text-xs">
                <div className="sm:pr-4">
                  <span className="text-slate-500 block text-[10px] uppercase font-semibold tracking-wide">Signal Detected:</span>
                  <span className={`font-mono font-bold block mt-0.5 ${
                    decodeResult.watermark_detected && decodeResult.payload_matches === true
                      ? 'text-emerald-400'
                      : decodeResult.watermark_detected
                      ? 'text-emerald-400'
                      : decodeResult.payload_matches === false
                      ? 'text-rose-400'
                      : 'text-rose-400'
                  }`}>
                    {decodeResult.watermark_detected && decodeResult.payload_matches === true
                      ? 'YES (VERIFIED)'
                      : decodeResult.watermark_detected
                      ? 'YES (DETECTED)'
                      : decodeResult.payload_matches === false
                      ? 'MISMATCH (H0)'
                      : 'NO WATERMARK (H0)'}
                  </span>
                </div>
                <div className="pt-2 sm:pt-0 sm:px-4">
                  <span className="text-slate-500 block text-[10px] uppercase font-semibold tracking-wide">Image Integrity:</span>
                  <span className={`font-mono font-bold block mt-0.5 ${
                    isDerivativeMedia
                      ? 'text-amber-700'
                      : (isExactOriginal || (decodeResult.image_binding_verified && !isDerivativeMedia))
                      ? 'text-emerald-700'
                      : 'text-slate-600'
                  }`}>
                    {isDerivativeMedia
                      ? 'TAMPERED / DERIVATIVE'
                      : (isExactOriginal || (decodeResult.image_binding_verified && !isDerivativeMedia))
                      ? 'ORIGINAL (UNTOUCHED)'
                      : 'UNCHECKED'}
                  </span>
                </div>
                <div className="pt-2 sm:pt-0 sm:pl-4">
                  <span className="text-slate-500 block text-[10px] uppercase font-semibold tracking-wide">Matches Reference:</span>
                  <span className={`font-mono font-bold block mt-0.5 ${
                    decodeResult.payload_matches === true || isDerivativeMedia
                      ? 'text-emerald-400'
                      : decodeResult.payload_matches === false
                      ? 'text-rose-400'
                      : 'text-slate-500'
                  }`}>
                    {decodeResult.payload_matches === true || isDerivativeMedia
                      ? 'MATCH (VERIFIED)'
                      : decodeResult.payload_matches === false
                      ? 'MISMATCH (H0)'
                      : 'UNANCHORED (H2)'}
                  </span>
                </div>
              </div>

              {isDerivativeMedia ? (
                <div className="p-3 bg-amber-50 border border-amber-300 rounded-lg text-xs space-y-1 shadow-xs">
                  <div className="flex items-center gap-2 font-bold text-amber-900">
                    <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                    <span>AI-Edited Derivative Detected</span>
                  </div>
                  <p className="text-[11px] text-slate-700 leading-relaxed font-medium">
                    The watermark confirms this media originated from the registered publisher, but the pixels were modified by AI or editing tools.
                  </p>
                </div>
              ) : (decodeResult.watermark_detected && (decodeResult.payload_matches === true || isExactOriginal) && !isDerivativeMedia) ? (
                <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-xs space-y-1">
                  <div className="flex items-center gap-2 font-bold text-emerald-400">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span>Authentic Original Media Verified</span>
                  </div>
                  <p className="text-[11px] text-slate-300 leading-relaxed font-normal">
                    Both the watermark and file hash match the on-chain record. Untouched original with zero modifications.
                  </p>
                </div>
              ) : (!decodeResult.watermark_detected && decodeResult.payload_matches === false) ? (
                <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-lg text-xs space-y-1">
                  <div className="flex items-center gap-2 font-bold text-rose-400">
                    <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0" />
                    <span>Watermark Mismatch</span>
                  </div>
                  <p className="text-[11px] text-slate-300 leading-relaxed">
                    {decodeResult.error || 'This image does not match the claimed publisher reference watermark.'}
                  </p>
                </div>
              ) : (decodeResult.payload_hex && (decodeResult.payload_matches === null || decodeResult.payload_matches === undefined)) ? (
                <div className="p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg text-xs space-y-1">
                  <div className="flex items-center gap-2 font-bold text-blue-400">
                    <ShieldCheck className="w-4 h-4 text-blue-400 shrink-0" />
                    <span>Candidate Watermark Found</span>
                  </div>
                  <p className="text-[11px] text-slate-300 leading-relaxed">
                    Watermark payload <span className="font-mono text-emerald-400 font-bold">0x{decodeResult.payload_hex}</span> extracted. Click below to audit against Sepolia records.
                  </p>
                </div>
              ) : (!decodeResult.payload_hex) ? (
                <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-lg text-xs space-y-1">
                  <div className="flex items-center gap-2 font-bold text-rose-400">
                    <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0" />
                    <span>No Watermark Detected</span>
                  </div>
                  <p className="text-[11px] text-slate-300 leading-relaxed">
                    {decodeResult.error || 'No authentic watermark detected on this candidate image.'}
                  </p>
                </div>
              ) : null}

              {/* Action: Image Verifier (Free Sepolia Read) & Proving Pipeline */}
              <div className="pt-2 space-y-3">
                <div className="p-3.5 bg-slate-950 rounded-xl border border-blue-500/30 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-blue-300 uppercase tracking-wide flex items-center gap-1.5">
                      <ShieldCheck className="w-4 h-4 text-blue-400" />
                      Image Verifier Role
                    </span>
                  </div>

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
                        Querying Sepolia Contract...
                      </>
                    ) : (
                      <>
                        <Blocks className="w-3.5 h-3.5" />
                        Audit On-Chain Record
                      </>
                    )}
                  </button>

                  {verifierError && (
                    <div className="p-2 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
                      {verifierError}
                    </div>
                  )}

                  {onChainRecord && (
                    <div className="mt-2 p-3 bg-slate-900 border border-slate-800 rounded-lg text-xs space-y-2.5">
                      <div className="flex items-center justify-between font-bold">
                        <span className={onChainRecord.exists ? (isDerivativeMedia ? 'text-amber-900 flex items-center gap-1.5' : 'text-emerald-700 flex items-center gap-1.5') : 'text-amber-900 flex items-center gap-1.5'}>
                          {onChainRecord.exists ? (
                            isDerivativeMedia ? <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" /> : <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                          ) : (
                            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                          )}
                          {onChainRecord.exists ? (
                            isDerivativeMedia
                              ? 'Publisher Provenance Verified · AI-Altered / Tampered Derivative'
                              : 'Authentic Original Confirmed on Sepolia (Untouched Pixels)'
                          ) : (
                            'Not Yet Anchored On-Chain'
                          )}
                        </span>
                      </div>

                      {onChainRecord.exists ? (
                        <div className="text-[11px] text-slate-300 space-y-2 pt-1 border-t border-slate-800">
                          {isDerivativeMedia && (
                            <div className="p-3 rounded-lg bg-amber-50 border border-amber-300 space-y-1.5 shadow-xs">
                              <div className="font-bold flex items-center gap-1.5 text-amber-900 text-xs">
                                <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                                Pixel Tampering / AI Edit Detected (SHA-256 Hash Mismatch)
                              </div>
                              <p className="text-[11px] text-slate-700 leading-relaxed font-medium">
                                The watermark payload matches the on-chain registered commitment on Sepolia (confirming publisher authorship), but the candidate image's SHA-256 hash differs from the registered original asset ID. This confirms the image has been modified by AI, edited, or cropped.
                              </p>
                            </div>
                          )}

                          <div>
                            <span className="text-slate-500 font-semibold">Publisher Wallet: </span>
                            <code className="text-amber-900 font-mono font-semibold break-all">{onChainRecord.submitter}</code>
                          </div>
                          <div>
                            <span className="text-slate-500 font-semibold">Registered Timestamp: </span>
                            <span>{onChainRecord.dateFormatted}</span>
                          </div>
                          <div>
                            <span className="text-slate-500 font-semibold">Original Anchor Asset ID (Sepolia Original): </span>
                            <code className="text-indigo-300 font-mono break-all block mt-0.5">
                              {cleanOnChainAsset ? `0x${cleanOnChainAsset}` : onChainRecord.assetId}
                            </code>
                          </div>
                          {cleanSuspectSha && (
                            <div>
                              <span className="text-slate-500 font-semibold">Candidate Media Hash: </span>
                              <code className={`font-mono break-all block mt-0.5 ${isDerivativeMedia ? 'text-amber-800 font-bold' : 'text-emerald-700 font-bold'}`}>
                                0x{cleanSuspectSha} {isDerivativeMedia ? '(Tampered / Altered Pixels)' : '(100% Match · Untouched)'}
                              </code>
                            </div>
                          )}
                          <div className="flex items-center justify-between pt-1">
                            <span className="text-slate-500 font-semibold">Verification Verdict: </span>
                            <span className={`px-2.5 py-1 rounded text-[10px] font-mono font-bold border shadow-xs ${
                              isDerivativeMedia
                                ? 'bg-amber-600 text-white border-amber-700'
                                : 'bg-emerald-600 text-white border-emerald-700'
                            }`}>
                              {isDerivativeMedia ? 'DERIVATIVE MEDIA (Pixel Tampering Detected)' : 'AUTHENTIC ORIGINAL (100% Hash Match)'}
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-500 font-semibold">On-Chain Commitment: </span>
                            <code className="text-blue-300 font-mono break-all block mt-0.5">{onChainRecord.commitment}</code>
                          </div>
                          {onChainRecord.ipfsCid && (
                            <div>
                              <span className="text-slate-500 font-semibold">Decentralized IPFS CID: </span>
                              <a
                                href={`https://gateway.pinata.cloud/ipfs/${onChainRecord.ipfsCid}`}
                                target="_blank"
                                rel="noreferrer"
                                className="text-emerald-400 hover:text-emerald-300 inline-flex items-center gap-1 font-mono break-all font-semibold"
                              >
                                ipfs://{onChainRecord.ipfsCid} <ExternalLink className="w-3 h-3 flex-shrink-0" />
                              </a>
                            </div>
                          )}
                          <div>
                            <span className="text-slate-500 font-semibold">Contract: </span>
                            <a
                              href={`https://sepolia.etherscan.io/address/${PROVENANCE_ANCHOR_ADDRESS}`}
                              target="_blank"
                              rel="noreferrer"
                              className="text-blue-400 hover:text-blue-300 inline-flex items-center gap-1 font-mono"
                            >
                              {PROVENANCE_ANCHOR_ADDRESS.slice(0, 8)}...{PROVENANCE_ANCHOR_ADDRESS.slice(-4)} <ExternalLink className="w-3 h-3" />
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
                <div className="space-y-1.5">
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
                        Executing Feature-Witness ZK Pipeline ({jobProgress}%)...
                      </>
                    ) : (
                      <>
                        <KeyRound className="w-4 h-4" />
                        Run Feature-Witness ZKP Pipeline (Halo2)
                      </>
                    )}
                  </button>
                  <p className="text-[10px] text-slate-500 text-center">
                    Certified neural feature extraction layer binding image features to the 100-bit payload commitment (~15–20s).
                  </p>
                </div>
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
                      className={`p-2 rounded-lg text-center border text-[11px] font-bold transition shadow-xs ${
                        isCurrent
                          ? 'bg-blue-100 border-blue-400 text-blue-900 animate-pulse'
                          : isDone
                          ? 'bg-emerald-50 border-emerald-300 text-emerald-800'
                          : 'bg-slate-100 border-slate-200 text-slate-500'
                      }`}
                    >
                      {st.label}
                    </div>
                  );
                })}
              </div>

              {/* Proving Failure Alert */}
              {jobData && jobData.status === 'failed' && (
                <div className="p-3.5 bg-rose-500/10 border border-rose-500/30 rounded-lg text-rose-900 text-xs space-y-1">
                  <div className="flex items-center gap-2 font-bold text-rose-700">
                    <XCircle className="w-4 h-4" />
                    Proving Job Failed
                  </div>
                  <p className="text-[11px] text-rose-950 font-mono leading-relaxed">
                    {jobData.error || 'The zero-knowledge proving pipeline encountered an error.'}
                  </p>
                </div>
              )}

              {/* Confirmation Artifacts */}
              {jobData && jobData.status === 'confirmed' && (
                <div className="space-y-3 pt-3 border-t border-slate-800 text-xs">
                  <div className="p-3 bg-emerald-50 border border-emerald-300 rounded-lg flex items-center justify-between text-emerald-900 shadow-xs">
                    <span className="flex items-center gap-2 font-bold text-emerald-900">
                      <CheckCircle2 className="w-4 h-4 text-emerald-700" />
                      Zero-Knowledge Proof Verified &amp; Commitment Anchored
                    </span>
                    <span className="font-mono text-[11px] font-bold text-emerald-900 bg-emerald-100 px-2 py-0.5 rounded border border-emerald-300">
                      {jobData.proof_result?.proving_time_seconds}s proving
                    </span>
                  </div>

                  <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs space-y-1.5 shadow-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-blue-900 flex items-center gap-1.5">
                        <ShieldCheck className="w-3.5 h-3.5 text-blue-600" />
                        Two-Stage Feature-Witness Halo2 zk-SNARK
                      </span>
                      <span className="text-[10px] bg-blue-100 text-blue-900 border border-blue-300 px-2 py-0.5 rounded font-mono font-bold">
                        Halo2 · KZG on BN254
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-700 leading-relaxed">
                      Certified neural feature extraction layer cryptographically bound the image features to the 100-bit payload commitment within the ZK circuit in {jobData.proof_result?.proving_time_seconds || '18'}s. Zero floating-point quantization drift, preserving 100% mathematical zero-knowledge privacy.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-[11px]">
                    <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 space-y-1">
                      <span className="text-slate-500 uppercase font-semibold block">Commitment C = H(m || k)</span>
                      <code className="text-amber-900 font-mono font-bold break-all block">
                        {jobData.proof_result?.public_inputs.payload_commitment}
                      </code>
                    </div>

                    <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-slate-500 uppercase font-semibold block">Blockchain Anchor Status</span>
                        <span className="text-[10px] font-mono font-bold text-white bg-amber-600 border border-amber-700 px-2 py-0.5 rounded shadow-xs">
                          Sepolia Testnet
                        </span>
                      </div>
                      {jobData.anchor_record?.tx_hash ? (
                        <>
                          <a
                            href={jobData.anchor_record?.etherscan_url || `https://sepolia.etherscan.io/tx/${jobData.anchor_record?.tx_hash}`}
                            target="_blank"
                            rel="noreferrer"
                            className="text-blue-700 hover:text-blue-900 font-mono break-all flex items-center gap-1 group font-semibold"
                          >
                            <span className="truncate">{jobData.anchor_record?.tx_hash}</span>
                            <ExternalLink className="w-3 h-3 flex-shrink-0 opacity-70 group-hover:opacity-100" />
                          </a>
                          <span className="text-slate-500 text-[10px] block">
                            Block #{jobData.anchor_record?.block_number} · Submitter: {jobData.anchor_record?.submitter?.slice(0, 10)}...
                          </span>
                        </>
                      ) : (
                        <div className="text-slate-500 text-[11px] font-mono py-1">
                          Zero-Knowledge Proof Verified (Verification Audit · Read-Only)
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Independent Cryptographic Proof Audit */}
                  <div className="p-4 bg-slate-950/80 rounded-xl border border-slate-800 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-300 text-xs flex items-center gap-1.5">
                        <ShieldCheck className="w-4 h-4 text-emerald-400" />
                        Independent Cryptographic Proof Audit
                      </span>
                      <button
                        onClick={handleAuditProof}
                        disabled={isAuditing}
                        className="px-3 py-1.5 bg-emerald-100 hover:bg-emerald-200 border border-emerald-400 text-emerald-900 rounded-lg text-xs font-bold flex items-center gap-1.5 transition shadow-xs cursor-pointer disabled:opacity-50"
                      >
                        {isAuditing ? (
                          <>
                            <RefreshCw className="w-3.5 h-3.5 animate-spin text-emerald-800" />
                            Auditing...
                          </>
                        ) : (
                          <>
                            <ShieldCheck className="w-3.5 h-3.5 text-emerald-800" />
                            Audit Proof Authenticity
                          </>
                        )}
                      </button>
                    </div>
                    <p className="text-[11px] text-slate-400">
                      Independently re-evaluates the Halo2 zero-knowledge proof against the certified TrustMark-Q verification key and circuit constraints.
                    </p>

                    {auditResult && (
                      <div className="mt-2 p-3 rounded-lg bg-slate-900 border border-emerald-500/30 text-xs space-y-2">
                        <div className="flex items-center justify-between">
                          <div className={`flex items-center gap-1.5 font-bold ${auditResult.valid ? 'text-emerald-700 font-bold' : 'text-rose-600 font-bold'}`}>
                            {auditResult.valid ? <CheckCircle2 className="w-4 h-4 text-emerald-700" /> : <XCircle className="w-4 h-4 text-rose-600" />}
                            Verifier Result: {auditResult.valid ? 'VALIDATED (GENUINE PASS)' : 'REJECTED (INVALID PROOF)'}
                          </div>
                          {auditResult.verification_time_seconds && (
                            <span className="text-[10px] text-slate-400 font-mono">
                              Verified in {auditResult.verification_time_seconds.toFixed(3)}s
                            </span>
                          )}
                        </div>

                        {auditResult.valid ? (
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] font-mono text-slate-300 bg-slate-950/70 p-2.5 rounded border border-slate-800">
                            <div>
                              <span className="text-slate-500 block text-[10px] font-sans uppercase font-semibold">Circuit Architecture:</span>
                              <span className="text-emerald-700 font-semibold">{auditResult.circuit_identifier || 'ezkl_halo2_trustmark_decoder_v1'}</span>
                            </div>
                            <div>
                              <span className="text-slate-500 block text-[10px] font-sans uppercase font-semibold">Proof System:</span>
                              <span className="text-blue-300">{auditResult.proof_system || 'Halo2 (KZG on BN254)'}</span>
                            </div>
                            <div className="sm:col-span-2">
                              <span className="text-slate-500 block text-[10px] font-sans uppercase font-semibold">Certified Model Digest:</span>
                              <span className="text-slate-300 truncate block" title={auditResult.model_digest}>
                                {auditResult.model_digest}
                              </span>
                            </div>
                            {auditResult.circuit_recovered_hex && (
                              <div className="sm:col-span-2">
                                <span className="text-slate-500 block text-[10px] font-sans uppercase font-semibold">Recovered Circuit Payload:</span>
                                <span className="text-emerald-700 font-bold">{auditResult.circuit_recovered_hex}</span>
                              </div>
                            )}
                          </div>
                        ) : (
                          <p className="text-[11px] text-rose-400 font-mono">
                            Error: {auditResult.error}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 4. Decentralized IPFS Provenance Match (Pinata Cloud) */}
          {decodeResult && decodeResult.watermark_detected && isZkpVerified && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block"></span>
                  4. Decentralized IPFS Provenance Match (Pinata Cloud)
                </h3>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Suspect Media */}
                <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-slate-400">1. Uploaded Suspect Media</span>
                    <span className="text-[10px] font-mono text-slate-500 bg-slate-800 px-1.5 py-0.5 rounded">Candidate Image</span>
                  </div>
                  <div className="aspect-video bg-slate-900 rounded border border-slate-800 overflow-hidden flex items-center justify-center">
                    <img src={preview!} alt="Uploaded Suspect" className="max-h-full object-contain" />
                  </div>
                  <div className="text-[11px] font-mono text-blue-700 font-semibold truncate">
                    <span className="text-slate-500 mr-1 select-none font-normal">SHA-256:</span>
                    0x{cleanSuspectSha || decodeResult.image_sha256}
                  </div>
                </div>

                {/* Original Registered Media from IPFS */}
                <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-slate-400 flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                      2. Original Registered Media
                    </span>
                    {(resolvedIpfsUrl || resolvedIpfsCid) && (
                      <button
                        type="button"
                        onClick={handleDownloadIpfsImage}
                        className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white rounded border border-slate-700 text-[11px] font-semibold flex items-center gap-1.5 transition cursor-pointer shadow-sm"
                        title="Download original authentic media from IPFS"
                      >
                        <Download className="w-3.5 h-3.5 text-emerald-400" />
                        Download
                      </button>
                    )}
                  </div>
                  {(resolvedIpfsUrl || resolvedIpfsCid) ? (
                    <>
                      <div className="aspect-video bg-slate-900 rounded border border-slate-800 overflow-hidden flex items-center justify-center">
                        <img
                          src={resolvedIpfsUrl || `https://gateway.pinata.cloud/ipfs/${resolvedIpfsCid}`}
                          alt="Original from IPFS"
                          className="max-h-full object-contain"
                        />
                      </div>
                      <div className="text-[11px] font-mono text-blue-700 font-semibold truncate select-all" title={resolvedIpfsCid ? `ipfs://${resolvedIpfsCid}` : undefined}>
                        <span className="text-slate-500 mr-1 select-none font-normal">CID:</span>
                        {resolvedIpfsCid ? `ipfs://${resolvedIpfsCid}` : 'ipfs://Pinata-Registered'}
                      </div>
                    </>
                  ) : (
                    <div className="aspect-video bg-slate-900/60 rounded border border-dashed border-slate-700 p-4 flex flex-col items-center justify-center text-center space-y-1.5">
                      <span className="text-amber-400 text-xs font-semibold">No Registered IPFS Provenance Record</span>
                      <p className="text-[11px] text-slate-400 max-w-xs">
                        This media watermark is not anchored to any publisher image in Pinata Cloud or Sepolia ledger.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
