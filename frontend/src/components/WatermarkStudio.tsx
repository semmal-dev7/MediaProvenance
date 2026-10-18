import React, { useState } from 'react';
import { Upload, ShieldCheck, AlertTriangle, Cpu, CheckCircle2, XCircle } from 'lucide-react';

export const WatermarkStudio: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [watermarkedImg, setWatermarkedImg] = useState<string | null>(null);
  const [payloadHex, setPayloadHex] = useState<string>('');
  const [psnr, setPsnr] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  
  // Suspect decode state
  const [suspectFile, setSuspectFile] = useState<File | null>(null);
  const [suspectPreview, setSuspectPreview] = useState<string | null>(null);
  const [refPayload, setRefPayload] = useState<string>('');
  const [decodeResult, setDecodeResult] = useState<any | null>(null);
  const [isDecoding, setIsDecoding] = useState<boolean>(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const f = e.target.files[0];
      setFile(f);
      setPreview(URL.createObjectURL(f));
    }
  };

  const handleSuspectChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const f = e.target.files[0];
      setSuspectFile(f);
      setSuspectPreview(URL.createObjectURL(f));
    }
  };

  const handleEncode = async () => {
    if (!file) return;
    setIsLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('carrier', 'trustmark');
      if (payloadHex) formData.append('payload_hex', payloadHex);

      const res = await fetch('/api/v1/watermark/encode', {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (data.success) {
        setWatermarkedImg(data.watermarked_image_base64);
        setPayloadHex(data.payload_hex);
        setPsnr(data.psnr_db);
        setRefPayload(data.payload_hex);
      } else {
        alert('Encoding failed: ' + data.error);
      }
    } catch (err: any) {
      alert('Error: ' + err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDecode = async () => {
    if (!suspectFile) return;
    setIsDecoding(true);
    try {
      const formData = new FormData();
      formData.append('file', suspectFile);
      formData.append('carrier', 'trustmark');
      if (refPayload) formData.append('reference_payload_hex', refPayload);

      const res = await fetch('/api/v1/watermark/decode', {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      setDecodeResult(data);
    } catch (err: any) {
      alert('Decode error: ' + err.message);
    } finally {
      setIsDecoding(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* SECTION 1: ENCODER */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 shadow-xl">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-blue-500/20 text-blue-400 rounded-lg">
            <Cpu className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">Neural Watermark Embedding</h2>
            <p className="text-sm text-slate-400">Carrier: Adobe Research TrustMark-Q (100-bit ResNet-50 payload)</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                1. Select Reference Image
              </label>
              <input
                type="file"
                accept="image/*"
                onChange={handleFileChange}
                className="block w-full text-sm text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-700 cursor-pointer"
              />
            </div>

            {preview && (
              <div className="h-52 bg-slate-900 rounded-lg border border-slate-700 overflow-hidden flex items-center justify-center">
                <img src={preview} alt="Reference preview" className="max-h-full object-contain" />
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                2. Watermark Payload (100-bit Hex, Optional)
              </label>
              <input
                type="text"
                placeholder="Leave blank to generate cryptographically random 100 bits"
                value={payloadHex}
                onChange={(e) => setPayloadHex(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-blue-500 font-mono"
              />
            </div>

            <button
              onClick={handleEncode}
              disabled={!file || isLoading}
              className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-medium rounded-lg shadow transition flex items-center justify-center gap-2"
            >
              <ShieldCheck className="w-4 h-4" />
              {isLoading ? 'Embedding Neural Watermark...' : 'Embed Watermark'}
            </button>
          </div>

          <div className="bg-slate-900/60 rounded-lg border border-slate-700 p-4 flex flex-col justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-3">
                Watermarked Output & Imperceptibility
              </h3>
              {watermarkedImg ? (
                <div className="space-y-3">
                  <div className="h-52 bg-slate-950 rounded-lg border border-slate-800 overflow-hidden flex items-center justify-center">
                    <img src={watermarkedImg} alt="Watermarked Output" className="max-h-full object-contain" />
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                    <div className="bg-slate-800 p-2 rounded">
                      <span className="text-slate-400 block">PSNR:</span>
                      <span className="text-emerald-400 font-bold">{psnr?.toFixed(2)} dB</span>
                    </div>
                    <div className="bg-slate-800 p-2 rounded truncate">
                      <span className="text-slate-400 block">Payload:</span>
                      <span className="text-blue-400">{payloadHex.slice(0, 16)}...</span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="h-64 flex flex-col items-center justify-center text-slate-500 text-sm">
                  <Upload className="w-8 h-8 mb-2 opacity-50" />
                  Embed a watermark to view output
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* SECTION 2: PROVENANCE INFERENCE & LIKELIHOOD RATIO */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-6 shadow-xl">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-emerald-500/20 text-emerald-400 rounded-lg">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">Suspect Image Provenance & Likelihood-Ratio Testing</h2>
            <p className="text-sm text-slate-400">Evaluates H1 (derivative) vs H0 (unrelated) vs H2 (undecodable)</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                1. Upload Suspect / Attacked Image
              </label>
              <input
                type="file"
                accept="image/*"
                onChange={handleSuspectChange}
                className="block w-full text-sm text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-emerald-600 file:text-white hover:file:bg-emerald-700 cursor-pointer"
              />
            </div>

            {suspectPreview && (
              <div className="h-44 bg-slate-900 rounded-lg border border-slate-700 overflow-hidden flex items-center justify-center">
                <img src={suspectPreview} alt="Suspect preview" className="max-h-full object-contain" />
              </div>
            )}

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                2. Reference Payload for Provenance Verification
              </label>
              <input
                type="text"
                placeholder="100-bit hex reference payload"
                value={refPayload}
                onChange={(e) => setRefPayload(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-emerald-500 font-mono"
              />
            </div>

            <button
              onClick={handleDecode}
              disabled={!suspectFile || isDecoding}
              className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-medium rounded-lg shadow transition flex items-center justify-center gap-2"
            >
              <ShieldCheck className="w-4 h-4" />
              {isDecoding ? 'Decoding & Computing Evidence...' : 'Verify Media Provenance'}
            </button>
          </div>

          <div className="bg-slate-900/60 rounded-lg border border-slate-700 p-5 flex flex-col justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">
                Bayesian Provenance Inference Output
              </h3>

              {decodeResult ? (
                <div className="space-y-4">
                  {/* Hypothesis Badge */}
                  <div className="flex items-center justify-between p-3 rounded-lg border border-slate-700 bg-slate-900">
                    <span className="text-xs uppercase font-bold text-slate-400">Inferred Hypothesis:</span>
                    <span
                      className={`px-3 py-1 rounded-full text-xs font-bold uppercase ${
                        decodeResult.inferred_hypothesis === 'H1'
                          ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                          : decodeResult.inferred_hypothesis === 'H0'
                          ? 'bg-red-500/20 text-red-400 border border-red-500/40'
                          : 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
                      }`}
                    >
                      {decodeResult.inferred_hypothesis === 'H1' && 'H1: Derivative Provenance Established'}
                      {decodeResult.inferred_hypothesis === 'H0' && 'H0: Unrelated Media (No Association)'}
                      {decodeResult.inferred_hypothesis === 'H2' && 'H2: Inconclusive / Undecodable'}
                    </span>
                  </div>

                  {/* Evidence Metrics */}
                  <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                    <div className="bg-slate-800 p-2.5 rounded">
                      <span className="text-slate-400 block mb-1">Hamming Distance:</span>
                      <span className="text-white text-sm font-bold">
                        {decodeResult.hamming_distance !== null ? `${decodeResult.hamming_distance} / 100` : 'N/A'}
                      </span>
                    </div>
                    <div className="bg-slate-800 p-2.5 rounded">
                      <span className="text-slate-400 block mb-1">Bit Error Rate (BER):</span>
                      <span className="text-white text-sm font-bold">
                        {decodeResult.bit_error_rate !== null ? `${(decodeResult.bit_error_rate * 100).toFixed(1)}%` : 'N/A'}
                      </span>
                    </div>
                    <div className="bg-slate-800 p-2.5 rounded">
                      <span className="text-slate-400 block mb-1">Log10(Likelihood Ratio):</span>
                      <span
                        className={`text-sm font-bold ${
                          (decodeResult.log10_likelihood_ratio || 0) > 0 ? 'text-emerald-400' : 'text-red-400'
                        }`}
                      >
                        {decodeResult.log10_likelihood_ratio !== null ? decodeResult.log10_likelihood_ratio.toFixed(2) : 'N/A'}
                      </span>
                    </div>
                    <div className="bg-slate-800 p-2.5 rounded">
                      <span className="text-slate-400 block mb-1">Posterior P(H1 | d):</span>
                      <span className="text-white text-sm font-bold">
                        {decodeResult.posterior_probability_h1 !== null
                          ? `${(decodeResult.posterior_probability_h1 * 100).toFixed(1)}%`
                          : 'N/A'}
                      </span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="h-56 flex flex-col items-center justify-center text-slate-500 text-sm">
                  <ShieldCheck className="w-8 h-8 mb-2 opacity-50" />
                  Upload a suspect image to run Bayesian inference
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
