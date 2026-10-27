import React, { useEffect, useState } from "react";
import { AlertTriangle, BadgeCheck, ClipboardCheck, Search, ShieldCheck } from "lucide-react";
import { api } from "../api";
import { CertificateInfo, PublishedCopyResult } from "../types";

const outcomeClasses: Record<string, string> = {
  valid: "border-emerald-300 bg-emerald-50 text-emerald-900",
  superseded: "border-amber-300 bg-amber-50 text-amber-900",
  revoked: "border-rose-300 bg-rose-50 text-rose-900",
  tampered: "border-rose-400 bg-rose-50 text-rose-950",
};

export const VerifyCertificate: React.FC = () => {
  const [certificateId, setCertificateId] = useState(() => new URLSearchParams(window.location.search).get("certificate_id") || "");
  const [certificate, setCertificate] = useState<CertificateInfo | null>(null);
  const [copyText, setCopyText] = useState("");
  const [copyResult, setCopyResult] = useState<PublishedCopyResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [checkingCopy, setCheckingCopy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const verify = async (id: string) => {
    if (!id.trim()) return;
    setLoading(true);
    setError(null);
    setCertificate(null);
    setCopyResult(null);
    try {
      const result = await api.verifyCertificate(id.trim());
      setCertificate(result);
      setCertificateId(result.certificate_id);
      const url = new URL(window.location.href);
      url.searchParams.set("certificate_id", result.certificate_id);
      window.history.replaceState({}, "", url.toString());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to verify this certificate.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const initialId = new URLSearchParams(window.location.search).get("certificate_id");
    if (initialId) void verify(initialId);
  }, []);

  const submitSearch = (event: React.FormEvent) => {
    event.preventDefault();
    void verify(certificateId);
  };

  const submitCopyCheck = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!certificate || !copyText) return;
    setCheckingCopy(true);
    setError(null);
    try {
      setCopyResult(await api.verifyPublishedCopy(certificate.certificate_id, copyText));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to compare this copy.");
    } finally {
      setCheckingCopy(false);
    }
  };

  const status = certificate?.status || "";
  return (
    <div className="mx-auto max-w-4xl space-y-7 px-4 py-10 sm:px-6 lg:px-8">
      <header className="text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-stone-900 text-amber-400"><ShieldCheck className="h-6 w-6" /></div>
        <p className="mt-4 text-xs font-bold uppercase tracking-[0.2em] text-amber-800">Public verification</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight text-stone-900">Verify an approval certificate</h1>
        <p className="mx-auto mt-3 max-w-2xl text-sm leading-relaxed text-stone-600">Check the approval record, audit chain, and approved content hash. This page shows metadata only and never reveals the approved content.</p>
      </header>

      <form onSubmit={submitSearch} className="mx-auto flex max-w-2xl flex-col gap-2 rounded-2xl border border-stone-200 bg-white p-4 shadow-sm sm:flex-row">
        <label htmlFor="certificate-id" className="sr-only">Certificate ID</label>
        <input id="certificate-id" value={certificateId} onChange={(event) => setCertificateId(event.target.value)} placeholder="Enter certificate ID (e.g. BG-…)" className="min-w-0 flex-1 rounded-lg border border-stone-300 px-3 py-2.5 text-sm outline-none focus:ring-2 focus:ring-amber-500" />
        <button disabled={loading || !certificateId.trim()} className="inline-flex items-center justify-center gap-2 rounded-lg bg-stone-900 px-4 py-2.5 text-sm font-bold text-white disabled:opacity-50"><Search className="h-4 w-4" />{loading ? "Checking…" : "Verify"}</button>
      </form>

      {error && <div role="alert" className="mx-auto max-w-2xl rounded-lg border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</div>}

      {certificate && <>
        <section className={`mx-auto max-w-3xl rounded-2xl border p-5 shadow-sm ${outcomeClasses[status] || outcomeClasses.tampered}`} aria-live="polite">
          <div className="flex items-start gap-3">
            {status === "valid" ? <BadgeCheck className="mt-0.5 h-6 w-6 shrink-0" /> : <AlertTriangle className="mt-0.5 h-6 w-6 shrink-0" />}
            <div>
              <h2 className="text-lg font-extrabold">{status === "valid" ? "Valid" : status === "superseded" ? "Superseded" : status === "revoked" ? "Revoked" : "Tampered"}</h2>
              <p className="mt-1 text-sm">{status === "valid" ? "The approval event, audit chain, and approved content hash are consistent." : status === "superseded" ? "A newer approved version exists for this submission." : status === "revoked" ? "This certificate was revoked. Its reason is recorded in the protected audit log." : "The certificate, content hash, or audit chain failed integrity checks."}</p>
            </div>
          </div>
        </section>

        <section className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
          <h2 className="text-sm font-bold text-stone-900">Approval metadata</h2>
          <dl className="mt-4 grid gap-x-6 gap-y-4 sm:grid-cols-2">
            <div><dt className="text-[10px] font-bold uppercase tracking-wide text-stone-500">Certificate</dt><dd className="mt-1 font-mono text-xs text-stone-800">{certificate.certificate_id}</dd></div>
            <div><dt className="text-[10px] font-bold uppercase tracking-wide text-stone-500">Title</dt><dd className="mt-1 text-sm font-semibold text-stone-800">{certificate.title}</dd></div>
            <div><dt className="text-[10px] font-bold uppercase tracking-wide text-stone-500">Approved version</dt><dd className="mt-1 text-sm text-stone-800">v{certificate.approved_version}</dd></div>
            <div><dt className="text-[10px] font-bold uppercase tracking-wide text-stone-500">Approver</dt><dd className="mt-1 text-sm text-stone-800">{certificate.approver.name} · {certificate.approver.role}</dd></div>
            <div><dt className="text-[10px] font-bold uppercase tracking-wide text-stone-500">Approved at</dt><dd className="mt-1 text-sm text-stone-800">{certificate.approved_at ? new Date(certificate.approved_at).toLocaleString() : "Not recorded"}</dd></div>
            <div><dt className="text-[10px] font-bold uppercase tracking-wide text-stone-500">AI engine / mode</dt><dd className="mt-1 text-sm text-stone-800">{certificate.ai_engine} · {certificate.ai_mode}</dd></div>
            <div className="sm:col-span-2"><dt className="text-[10px] font-bold uppercase tracking-wide text-stone-500">Approved content SHA-256</dt><dd className="mt-1 break-all font-mono text-[11px] text-stone-700">{certificate.content_hash}</dd></div>
            <div className="sm:col-span-2"><dt className="text-[10px] font-bold uppercase tracking-wide text-stone-500">Audit chain head at approval</dt><dd className="mt-1 break-all font-mono text-[11px] text-stone-700">{certificate.audit_chain_head_hash}</dd></div>
            <div><dt className="text-[10px] font-bold uppercase tracking-wide text-stone-500">Audit chain check</dt><dd className="mt-1 text-sm text-stone-800">{certificate.audit_chain_valid ? "Passed" : "Failed"}</dd></div>
            <div><dt className="text-[10px] font-bold uppercase tracking-wide text-stone-500">Content hash check</dt><dd className="mt-1 text-sm text-stone-800">{certificate.content_hash_valid ? "Passed" : "Failed"}</dd></div>
          </dl>
        </section>

        <section className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
          <div className="flex items-start gap-3"><ClipboardCheck className="mt-0.5 h-5 w-5 text-amber-700" /><div><h2 className="text-sm font-bold text-stone-900">Compare a published copy</h2><p className="mt-1 text-xs leading-relaxed text-stone-600">Paste the published text to compare it with the approved version. The pasted text is checked in this request and is not returned by the verification API.</p></div></div>
          <form onSubmit={submitCopyCheck} className="mt-4 space-y-3">
            <label htmlFor="published-copy" className="sr-only">Published copy</label>
            <textarea id="published-copy" value={copyText} onChange={(event) => setCopyText(event.target.value)} maxLength={500000} placeholder="Paste the published copy here" className="min-h-40 w-full rounded-xl border border-stone-300 p-3 text-sm text-stone-800 outline-none focus:ring-2 focus:ring-amber-500" />
            <button disabled={checkingCopy || !copyText} className="rounded-lg bg-amber-700 px-4 py-2.5 text-xs font-bold text-white disabled:opacity-50">{checkingCopy ? "Comparing…" : "Compare with approved version"}</button>
          </form>
          {copyResult && <div className={`mt-4 rounded-lg border px-4 py-3 text-sm font-bold ${copyResult.copy_result === "Match" ? "border-emerald-300 bg-emerald-50 text-emerald-900" : "border-amber-300 bg-amber-50 text-amber-900"}`} role="status">
            {copyResult.copy_result}: {copyResult.message}<span className="mt-1 block text-[10px] font-normal">Comparison scope: {copyResult.comparison_scope.replace(/_/g, " ")}</span>
          </div>}
        </section>
      </>}
    </div>
  );
};
