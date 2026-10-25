import React, { useState, useEffect } from 'react';
import { Upload, Cpu, Download, ArrowRight, ShieldCheck, RefreshCw, CheckCircle, Image as ImageIcon, Wallet, AlertCircle, LogOut } from 'lucide-react';
import { connectMetaMask, switchMetaMaskAccount, anchorWithMetaMask, getConnectedAccount } from '../services/web3';

interface EmbedPageProps {
  onProceedToVerify?: (imageFile: File, payloadHex: string) => void;
}

// Helper to generate a unique random payload that has never been used on another image
const generateFreshPayload = (carrierType: 'pureconv' | 'hidden' | 'trustmark'): string => {
  let usedSet: Set<string> = new Set();
  try {
    const stored = localStorage.getItem('used_watermark_payloads');
    if (stored) usedSet = new Set(JSON.parse(stored));
  } catch {
    usedSet = new Set();
  }

  let candidate = '';
  let attempts = 0;
  do {
    attempts++;
    if (carrierType === 'pureconv' || carrierType === 'hidden') {
      const array = new Uint32Array(1);
      window.crypto.getRandomValues(array);
      candidate = array[0].toString(16).padStart(8, '0');
    } else {
      const array = new Uint8Array(12);
      window.crypto.getRandomValues(array);
      const hexStr = Array.from(array, (b) => b.toString(16).padStart(2, '0')).join('');
      candidate = 'a5' + hexStr.slice(0, 23);
    }
  } while (usedSet.has(candidate.toLowerCase()) && attempts < 100);

  return candidate;
};

export const EmbedPage: React.FC<EmbedPageProps> = ({ onProceedToVerify }) => {
  const [carrier, setCarrier] = useState<'pureconv' | 'hidden' | 'trustmark'>('trustmark');
  const [payloadHex, setPayloadHex] = useState<string>(() => generateFreshPayload('trustmark'));
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [watermarkedImg, setWatermarkedImg] = useState<string | null>(null);
  const [embedResult, setEmbedResult] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // MetaMask Publisher State
  const [publisherAccount, setPublisherAccount] = useState<string | null>(null);
  const [isConnectingWallet, setIsConnectingWallet] = useState<boolean>(false);
  const [isPublishing, setIsPublishing] = useState<boolean>(false);
  const [publishStep, setPublishStep] = useState<string>('');
  const [publisherTxResult, setPublisherTxResult] = useState<any | null>(null);
  const [publisherTxError, setPublisherTxError] = useState<string | null>(null);

  // Check if MetaMask is already connected on mount & listen to account changes
  useEffect(() => {
    const isExplicitlyDisconnected = sessionStorage.getItem('wallet_disconnected') === 'true';
    if (!isExplicitlyDisconnected) {
      getConnectedAccount().then((addr) => {
        if (addr) setPublisherAccount(addr);
      });
    }

    if (typeof window !== 'undefined' && (window as any).ethereum) {
      const handleAccounts = (accounts: string[]) => {
        if (accounts && accounts.length > 0) {
          setPublisherAccount(accounts[0]);
          sessionStorage.removeItem('wallet_disconnected');
        } else {
          setPublisherAccount(null);
        }
      };
      const handleChain = () => {
        getConnectedAccount().then((addr) => setPublisherAccount(addr));
      };

      (window as any).ethereum.on('accountsChanged', handleAccounts);
      (window as any).ethereum.on('chainChanged', handleChain);
      return () => {
        (window as any).ethereum?.removeListener('accountsChanged', handleAccounts);
        (window as any).ethereum?.removeListener('chainChanged', handleChain);
      };
    }
  }, []);

  const handleConnectMetaMask = async (promptSelect: boolean = false) => {
    setIsConnectingWallet(true);
    setPublisherTxError(null);
    try {
      sessionStorage.removeItem('wallet_disconnected');
      // If promptSelect is true, use switchMetaMaskAccount to open account selector
      const { address } = promptSelect ? await switchMetaMaskAccount() : await connectMetaMask();
      setPublisherAccount(address);
    } catch (err: any) {
      setPublisherTxError(err.message || 'Failed to connect MetaMask');
    } finally {
      setIsConnectingWallet(false);
    }
  };

  const handleSwitchAccount = async () => {
    setIsConnectingWallet(true);
    setPublisherTxError(null);
    try {
      sessionStorage.removeItem('wallet_disconnected');
      const { address } = await switchMetaMaskAccount();
      setPublisherAccount(address);
    } catch (err: any) {
      setPublisherTxError(err.message || 'Account switch cancelled');
    } finally {
      setIsConnectingWallet(false);
    }
  };

  const handleDisconnectWallet = () => {
    sessionStorage.setItem('wallet_disconnected', 'true');
    setPublisherAccount(null);
    setPublisherTxResult(null);
    setPublisherTxError(null);
  };

  const handlePublishWithMetaMask = async () => {
    if (!embedResult) return;
    setIsPublishing(true);
    setPublisherTxError(null);
    setPublisherTxResult(null);

    try {
      setPublishStep('1/2 Generating EZKL Halo2/PLONKish + KZG Proof...');
      const genRes = await fetch('/api/v1/proofs/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          payload_hex: embedResult.payload_hex,
          image_sha256: embedResult.image_sha256,
          image_features: embedResult.image_features,
          carrier: carrier,
          prover_address: publisherAccount || '0x0000000000000000000000000000000000000000',
        }),
      });

      if (!genRes.ok) {
        const errText = await genRes.text();
        let errMsg = `Proof generation failed (${genRes.status})`;
        try {
          const errObj = JSON.parse(errText);
          errMsg = errObj.detail || errObj.error || errMsg;
        } catch {
          if (errText) errMsg = errText;
        }
        throw new Error(errMsg);
      }

      const genData = await genRes.json();
      if (!genData.success) {
        throw new Error(genData.error || 'Failed to generate ZK proof');
      }

      setPublishStep('2/2 Prompting MetaMask to submit transaction...');
      const txRes = await anchorWithMetaMask(genData.asset_id, genData.commitment);
      setPublisherTxResult(txRes);
    } catch (err: any) {
      setPublisherTxError(err.message || 'MetaMask transaction rejected or failed.');
    } finally {
      setIsPublishing(false);
      setPublishStep('');
    }
  };

  const handleGeneratePayload = () => {
    setPublisherTxResult(null);
    setPublisherTxError(null);
    setPayloadHex(generateFreshPayload(carrier));
  };

  const handleCarrierChange = (newCarrier: 'pureconv' | 'hidden' | 'trustmark') => {
    setCarrier(newCarrier);
    setPublisherTxResult(null);
    setPublisherTxError(null);
    setPayloadHex(generateFreshPayload(newCarrier));
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const f = e.target.files[0];
      setFile(f);
      setPreview(URL.createObjectURL(f));
      setWatermarkedImg(null);
      setEmbedResult(null);
      setPublisherTxResult(null);
      setPublisherTxError(null);
      setError(null);

      // Automatically generate a fresh, unique random payload for this new image
      const uniquePayload = generateFreshPayload(carrier);
      setPayloadHex(uniquePayload);

      // Whenever publisher selects an image, prompt them to connect with their wallet if not already connected
      if (!publisherAccount) {
        handleConnectMetaMask(true);
      }
    }
  };

  const handleEmbed = async () => {
    if (!publisherAccount) {
      setError('MetaMask wallet required: Please connect your MetaMask account to identify yourself as the publisher.');
      return;
    }
    if (!file) {
      setError('Please select an image file first.');
      return;
    }
    // Check if payload was already used on another image
    let usedSet: Set<string> = new Set();
    try {
      const stored = localStorage.getItem('used_watermark_payloads');
      if (stored) usedSet = new Set(JSON.parse(stored));
    } catch {}

    const cleanCurrent = payloadHex.toLowerCase().replace('0x', '').trim();
    if (usedSet.has(cleanCurrent)) {
      const fresh = generateFreshPayload(carrier);
      setPayloadHex(fresh);
      setError(`Payload 0x${cleanCurrent} has already been used on another image. A fresh unique payload (0x${fresh}) has been automatically generated.`);
      return;
    }

    setLoading(true);
    setError(null);
    setPublisherTxResult(null);
    setPublisherTxError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('carrier', carrier);
      formData.append('payload_hex', payloadHex);

      const res = await fetch('/api/v1/watermarks/embed', {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();
      if (data.success) {
        // Record this payload so it can never be reused for another image
        const cleanUsed = (data.payload_hex || payloadHex).toLowerCase().replace('0x', '').trim();
        usedSet.add(cleanUsed);
        try {
          localStorage.setItem('used_watermark_payloads', JSON.stringify(Array.from(usedSet)));
        } catch {}

        setWatermarkedImg(data.watermarked_image_base64);
        setEmbedResult(data);
      } else {
        setError(data.error || 'Failed to embed watermark.');
      }
    } catch (err: any) {
      setError(err.message || 'Network error occurred.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow">
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 bg-blue-500/20 text-blue-400 rounded-xl">
            <Cpu className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white">Embed Neural Watermark</h2>
          </div>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Configuration Controls */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow space-y-5">
          <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
            1. Carrier &amp; Payload Settings
          </h3>

          {/* Publisher MetaMask Account Status & Connect Button */}
          <div className={`p-4 rounded-xl border transition shadow-xs ${
            publisherAccount 
              ? 'bg-emerald-50 border-emerald-300' 
              : 'bg-amber-50 border-amber-300'
          }`}>
            <div className="flex items-center justify-between mb-2">
              <span className="flex items-center gap-1.5 text-xs font-bold text-slate-800">
                <Wallet className={`w-4 h-4 ${publisherAccount ? 'text-emerald-600' : 'text-amber-600'}`} />
                Publisher Identity
              </span>
              {publisherAccount ? (
                <span className="text-[10px] px-2.5 py-0.5 rounded-full font-mono font-bold bg-emerald-600 text-white border border-emerald-700 flex items-center gap-1 shadow-xs">
                  <CheckCircle className="w-3 h-3 text-white" /> Connected
                </span>
              ) : (
                <span className="text-[10px] px-2.5 py-0.5 rounded-full font-bold bg-amber-600 text-white border border-amber-700 shadow-xs">
                  Wallet Required
                </span>
              )}
            </div>

            {publisherAccount ? (
              <div className="space-y-2.5">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-[11px] text-slate-400">
                      Authenticated publisher address:
                    </p>
                    <span className="text-[10px] text-slate-500 font-mono">Sepolia Testnet</span>
                  </div>
                  <div className="font-mono text-xs text-emerald-900 bg-emerald-50 p-2 rounded-lg border border-emerald-300 break-all select-all flex items-center justify-between font-semibold">
                    <span>{publisherAccount}</span>
                  </div>
                </div>

                <div className="flex items-center gap-2 pt-0.5">
                  <button
                    type="button"
                    onClick={handleSwitchAccount}
                    disabled={isConnectingWallet}
                    className="flex-1 py-1.5 px-2.5 bg-slate-100 hover:bg-slate-200 text-slate-800 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 border border-slate-300 transition disabled:opacity-50 shadow-xs"
                    title="Choose a different MetaMask account"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 text-blue-600 ${isConnectingWallet ? 'animate-spin' : ''}`} />
                    Switch Wallet
                  </button>
                  <button
                    type="button"
                    onClick={handleDisconnectWallet}
                    className="py-1.5 px-3 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-xs font-bold transition flex items-center gap-1.5 shadow-xs"
                    title="Disconnect this wallet"
                  >
                    <LogOut className="w-3.5 h-3.5 text-white shrink-0" />
                    Disconnect
                  </button>
                </div>
              </div>
            ) : (
              <div className="space-y-2.5">
                <p className="text-[11px] text-slate-400 leading-snug">
                  Whenever you upload an image, connect your preferred MetaMask account so provenance is bound to your own wallet.
                </p>
                <button
                  type="button"
                  onClick={() => handleConnectMetaMask(true)}
                  disabled={isConnectingWallet}
                  className="w-full py-2.5 px-3 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 shadow transition disabled:opacity-50"
                >
                  <Wallet className="w-4 h-4" />
                  {isConnectingWallet ? 'Connecting Wallet...' : "Connect with User's Wallet"}
                </button>
              </div>
            )}
          </div>

          {/* Carrier Selection */}
          <div>
            <label className="block text-xs font-semibold text-slate-400 mb-2">
              Neural Watermark Carrier:
            </label>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => handleCarrierChange('pureconv')}
                className={`px-3 py-2.5 rounded-lg text-xs font-semibold border transition text-left ${
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
                onClick={() => handleCarrierChange('hidden')}
                className={`px-3 py-2.5 rounded-lg text-xs font-semibold border transition text-left ${
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
                onClick={() => handleCarrierChange('trustmark')}
                className={`px-3 py-2.5 rounded-lg text-xs font-semibold border transition text-left ${
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

          {/* Payload Hex Input */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-semibold text-slate-400">
                Payload Hex ({carrier === 'trustmark' ? '100 bits / 25 chars' : '32 bits / 8 chars'}):
              </label>
              <button
                type="button"
                onClick={handleGeneratePayload}
                className="text-[11px] text-blue-400 hover:text-blue-300 flex items-center gap-1"
              >
                <RefreshCw className="w-3 h-3" /> Random
              </button>
            </div>
            <input
              type="text"
              value={payloadHex}
              onChange={(e) => setPayloadHex(e.target.value.toLowerCase().replace(/[^0-9a-f]/g, ''))}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-blue-500"
              maxLength={carrier === 'trustmark' ? 25 : 8}
            />
          </div>

          {/* Image Uploader */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-semibold text-slate-400">
                Select Reference Image:
              </label>
              {!publisherAccount && (
                <button
                  type="button"
                  onClick={() => handleConnectMetaMask(true)}
                  className="text-[11px] text-amber-400 hover:text-amber-300 font-semibold flex items-center gap-1"
                >
                  <Wallet className="w-3 h-3" /> Connect wallet first
                </button>
              )}
            </div>

            {!publisherAccount && (
              <div className="mb-2.5 p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-[11px] flex items-center justify-between gap-2">
                <span>Please connect your wallet before uploading so your publisher identity is bound to the watermark.</span>
                <button
                  type="button"
                  onClick={() => handleConnectMetaMask(true)}
                  className="px-2 py-1 bg-amber-600 hover:bg-amber-500 text-white rounded text-[10px] font-bold shrink-0"
                >
                  Connect Wallet
                </button>
              </div>
            )}

            <label className="flex flex-col items-center justify-center border-2 border-dashed border-slate-800 hover:border-blue-500/50 rounded-xl p-6 cursor-pointer bg-slate-950/60 transition group">
              <Upload className="w-6 h-6 text-slate-500 group-hover:text-blue-400 mb-2 transition" />
              <span className="text-xs text-slate-300 font-medium">Click to select image</span>
              <span className="text-[10px] text-slate-500 mt-1">PNG, JPG, WebP</span>
              <input type="file" accept="image/*" onChange={handleFileChange} className="hidden" />
            </label>
            {file && (
              <p className="text-[11px] text-slate-400 mt-2 truncate">
                Selected: <span className="text-slate-200">{file.name}</span> ({(file.size / 1024).toFixed(1)} KB)
              </p>
            )}
          </div>

          {/* Error Notice */}
          {error && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-xs">
              {error}
            </div>
          )}

          {/* Embed Button */}
          <button
            onClick={handleEmbed}
            disabled={!file || loading || !publisherAccount}
            className={`w-full py-2.5 px-4 rounded-xl text-xs font-bold flex items-center justify-center gap-2 shadow transition ${
              !file || loading || !publisherAccount
                ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                : 'bg-blue-600 hover:bg-blue-500 text-white shadow-blue-500/20'
            }`}
          >
            {loading ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Embedding Watermark...
              </>
            ) : !publisherAccount ? (
              <>
                <Wallet className="w-4 h-4" />
                Connect MetaMask to Embed
              </>
            ) : (
              <>
                <ShieldCheck className="w-4 h-4" />
                Embed Neural Watermark
              </>
            )}
          </button>
        </div>

        {/* Right Columns: Previews and Metrics */}
        <div className="lg:col-span-2 space-y-5">
          {/* Visual Previews */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-4">
              2. Visual Imperceptibility Inspection
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Original Preview */}
              <div className="space-y-2">
                <span className="text-xs font-semibold text-slate-400 block">Original Image</span>
                <div className="aspect-square bg-slate-950 rounded-lg border border-slate-800 flex items-center justify-center overflow-hidden">
                  {preview ? (
                    <img src={preview} alt="Original" className="w-full h-full object-contain" />
                  ) : (
                    <div className="text-center text-slate-600 p-4">
                      <ImageIcon className="w-8 h-8 mx-auto mb-2 opacity-40" />
                      <span className="text-xs">No image loaded</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Watermarked Preview */}
              <div className="space-y-2">
                <span className="text-xs font-semibold text-slate-400 block">Watermarked Image (I_w)</span>
                <div className="aspect-square bg-slate-950 rounded-lg border border-slate-800 flex items-center justify-center overflow-hidden">
                  {watermarkedImg ? (
                    <img src={watermarkedImg} alt="Watermarked" className="w-full h-full object-contain" />
                  ) : (
                    <div className="text-center text-slate-600 p-4">
                      <ShieldCheck className="w-8 h-8 mx-auto mb-2 opacity-40" />
                      <span className="text-xs">Awaiting watermark embedding</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Quality Metrics */}
          {embedResult && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow space-y-4">
              <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                3. Perceptual Quality &amp; Cryptographic Manifest
              </h3>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="bg-slate-950/70 p-3 rounded-lg border border-slate-800">
                  <span className="text-[10px] text-slate-500 uppercase font-semibold block">PSNR Metric</span>
                  <span className="text-lg font-bold text-emerald-400 block mt-1">
                    {embedResult.psnr_db ? `${embedResult.psnr_db.toFixed(2)} dB` : 'N/A'}
                  </span>
                  <span className="text-[10px] text-slate-400">Target: &gt; 30 dB</span>
                </div>

                <div className="bg-slate-950/70 p-3 rounded-lg border border-slate-800">
                  <span className="text-[10px] text-slate-500 uppercase font-semibold block">Inference Time</span>
                  <span className="text-lg font-bold text-blue-400 block mt-1">
                    {(embedResult.elapsed_seconds * 1000).toFixed(1)} ms
                  </span>
                  <span className="text-[10px] text-slate-400">CPU Execution</span>
                </div>

                <div className="bg-slate-950/70 p-3 rounded-lg border border-slate-800">
                  <span className="text-[10px] text-slate-500 uppercase font-semibold block">Payload Bits</span>
                  <span className="text-lg font-bold text-white block mt-1">
                    {embedResult.payload_bits}
                  </span>
                  <span className="text-[10px] text-slate-400 font-mono">0x{embedResult.payload_hex}</span>
                </div>

                <div className="bg-slate-950/70 p-3 rounded-lg border border-slate-800">
                  <span className="text-[10px] text-slate-500 uppercase font-semibold block">Carrier Engine</span>
                  <span className="text-lg font-bold text-white block mt-1 truncate">
                    {embedResult.carrier_name}
                  </span>
                  <span className="text-[10px] text-slate-400">{embedResult.carrier_version}</span>
                </div>
              </div>

              {/* SHA256 Hash Box */}
              <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 text-xs">
                <span className="text-slate-400 block mb-1 font-semibold text-[11px]">
                  Content SHA-256 Digest (Asset ID):
                </span>
                <code className="text-blue-300 font-mono text-[11px] break-all select-all">
                  0x{embedResult.image_sha256}
                </code>
              </div>

              {/* Actions */}
              <div className="flex flex-wrap gap-3 pt-2">
                <a
                  href={watermarkedImg!}
                  download={`watermarked_${embedResult.payload_hex}.png`}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition"
                >
                  <Download className="w-3.5 h-3.5" />
                  Download Watermarked PNG
                </a>
                {onProceedToVerify && (
                  <button
                    onClick={() => onProceedToVerify(file!, embedResult.payload_hex)}
                    className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition"
                  >
                    Test Verification Flow <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>

              {/* Image Publisher (MetaMask Anchoring Card) */}
              <div className="mt-4 p-4 rounded-xl border border-amber-300 bg-amber-50 space-y-3 shadow-xs">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="p-1.5 rounded-lg bg-amber-100 text-amber-700">
                      <ShieldCheck className="w-4 h-4" />
                    </span>
                    <div>
                      <h4 className="text-xs font-bold text-amber-900 uppercase tracking-wide">
                        Image Publisher Role
                      </h4>
                      <p className="text-[11px] text-slate-700">
                        Generate zero-knowledge proof and anchor commitment to Sepolia.
                      </p>
                    </div>
                  </div>
                  {publisherAccount && (
                    <span className="text-[10px] font-mono bg-amber-100 border border-amber-300 text-amber-900 font-semibold px-2 py-0.5 rounded">
                      {publisherAccount.slice(0, 6)}...{publisherAccount.slice(-4)}
                    </span>
                  )}
                </div>

                {publisherTxError && (
                  <div className="p-2.5 rounded bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
                    {publisherTxError}
                  </div>
                )}

                {publisherTxResult ? (
                  <div className={`p-3 bg-slate-900 rounded-lg text-xs space-y-2 border ${
                    publisherTxResult.alreadyAnchored 
                      ? 'border-cyan-500/30' 
                      : 'border-emerald-500/30'
                  }`}>
                    <div className={`flex items-center justify-between font-bold ${
                      publisherTxResult.alreadyAnchored ? 'text-cyan-400' : 'text-emerald-400'
                    }`}>
                      <span className="flex items-center gap-1.5">
                        <CheckCircle className="w-4 h-4" />
                        {publisherTxResult.alreadyAnchored 
                          ? 'Asset Already Anchored On Sepolia (Immutable)' 
                          : 'Confirmed On-Chain on Sepolia!'}
                      </span>
                      {publisherTxResult.blockNumber > 0 && (
                        <span className="text-[11px] font-mono text-slate-400">
                          Block #{publisherTxResult.blockNumber}
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] text-slate-400 space-y-1">
                      {publisherTxResult.alreadyAnchored ? (
                        <div className="p-2 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20 text-[11px]">
                          This exact watermarked asset digest was previously anchored by an authorized publisher. In accordance with smart contract immutability rules (<code>!records[assetId].exists</code>), duplicate submissions are prevented to protect provenance integrity.
                        </div>
                      ) : (
                        <div>
                          <span className="text-slate-500 font-semibold">Tx Hash: </span>
                          <a
                            href={publisherTxResult.etherscanUrl}
                            target="_blank"
                            rel="noreferrer"
                            className="text-blue-400 hover:text-blue-300 font-mono break-all inline-flex items-center gap-1"
                          >
                            {publisherTxResult.txHash}
                          </a>
                        </div>
                      )}
                      <div>
                        <span className="text-slate-500 font-semibold">Original Publisher Address: </span>
                        <code className="text-slate-300 font-mono">{publisherTxResult.submitter}</code>
                      </div>
                      <div>
                        <span className="text-slate-500 font-semibold">Gas Used: </span>
                        <code className="text-slate-300 font-mono">
                          {publisherTxResult.gasUsed === '0' ? '0 gas (Pre-verified on-chain)' : `${Number(publisherTxResult.gasUsed).toLocaleString()} gas`}
                        </code>
                        <span className="text-slate-500 ml-1">
                          {publisherTxResult.gasUsed === '0' ? '(no gas spent)' : '(paid in SepoliaETH by publisher wallet)'}
                        </span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-wrap gap-2 pt-1">
                    {!publisherAccount ? (
                      <button
                        type="button"
                        onClick={() => handleConnectMetaMask(true)}
                        disabled={isConnectingWallet}
                        className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-xs font-bold flex items-center gap-1.5 shadow transition"
                      >
                        {isConnectingWallet ? 'Connecting...' : 'Connect MetaMask (Sepolia)'}
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={handlePublishWithMetaMask}
                        disabled={isPublishing}
                        className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-xs font-bold flex items-center gap-1.5 shadow transition disabled:opacity-60"
                      >
                        {isPublishing ? (
                          <>
                            <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                            {publishStep || 'Publishing Proof & Anchor...'}
                          </>
                        ) : (
                          <>
                            <ShieldCheck className="w-3.5 h-3.5" />
                            Publish Proof &amp; Anchor
                          </>
                        )}
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
