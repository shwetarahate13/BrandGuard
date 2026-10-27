import React, { useEffect, useState } from "react";
import { BadgeCheck, Download, ExternalLink, RotateCcw, ShieldAlert } from "lucide-react";
import { api } from "../api";
import { CertificateInfo, User } from "../types";

interface CertificateLibraryProps {
  user: User;
  navigate: (path: string) => void;
}

const statusStyle: Record<string, string> = {
  valid: "border-emerald-300 bg-emerald-50 text-emerald-800",
  superseded: "border-amber-300 bg-amber-50 text-amber-800",
  revoked: "border-rose-300 bg-rose-50 text-rose-800",
  tampered: "border-rose-300 bg-rose-50 text-rose-800",
};

export const CertificateLibrary: React.FC<CertificateLibraryProps> = ({ user, navigate }) => {
  const [certificates, setCertificates] = useState<CertificateInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revokeId, setRevokeId] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      setCertificates(await api.getCertificates());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load approval certificates.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const submitRevocation = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!revokeId || !reason.trim()) return;
    setSaving(true);
    try {
      await api.revokeCertificate(revokeId, reason.trim());
      setRevokeId(null);
      setReason("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to revoke this certificate.");
    } finally {
      setSaving(false);
    }
  };

  const canRevoke = user.role === "manager" || user.role === "admin";
  return (
    <div className="mx-auto max-w-5xl space-y-6 px-4 py-8 sm:px-6 lg:px-8">
      <header>
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-amber-800">Approval evidence</p>
        <h1 className="mt-2 text-2xl font-bold tracking-tight text-stone-900">Certificate Library</h1>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-stone-600">
          Download signed approval certificates and open the public verification record. Certificates show approval metadata and never expose the approved copy on the verification page.
        </p>
      </header>

      {error && <div role="alert" className="rounded-lg border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</div>}
      {loading ? <p className="py-12 text-center text-sm text-stone-500">Loading certificates…</p>
        : certificates.length === 0 ? <section className="rounded-2xl border border-dashed border-stone-300 bg-white px-6 py-12 text-center">
          <BadgeCheck className="mx-auto h-8 w-8 text-stone-400" />
          <h2 className="mt-3 text-sm font-bold text-stone-800">No certificates are available</h2>
          <p className="mt-1 text-xs text-stone-500">Approved submissions will appear here when you are allowed to access them.</p>
        </section> : <div className="space-y-4">
          {certificates.map((certificate) => (
            <article key={certificate.certificate_id} className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-base font-bold text-stone-900">{certificate.title}</h2>
                    <span className={`rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide ${statusStyle[certificate.status] || statusStyle.tampered}`}>
                      {certificate.status}
                    </span>
                  </div>
                  <p className="mt-2 font-mono text-xs text-stone-500">{certificate.certificate_id} · Version {certificate.approved_version}</p>
                  <p className="mt-2 text-xs text-stone-600">
                    Approved by {certificate.approver.name} ({certificate.approver.role})
                    {certificate.approved_at ? ` · ${new Date(certificate.approved_at).toLocaleString()}` : ""}
                  </p>
                  <p className="mt-3 break-all font-mono text-[10px] text-stone-500">SHA-256 {certificate.content_hash}</p>
                </div>
                <div className="flex shrink-0 flex-wrap gap-2">
                  <button onClick={() => void api.downloadCertificate(certificate.certificate_id).catch((err) => setError(err.message))}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-stone-900 px-3 py-2 text-xs font-bold text-white hover:bg-stone-700">
                    <Download className="h-3.5 w-3.5" /> Download PDF
                  </button>
                  <button onClick={() => navigate(`/verify?certificate_id=${encodeURIComponent(certificate.certificate_id)}`)}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-stone-300 px-3 py-2 text-xs font-bold text-stone-800 hover:bg-stone-50">
                    <ExternalLink className="h-3.5 w-3.5" /> Verify
                  </button>
                  {canRevoke && certificate.status === "valid" && <button onClick={() => { setRevokeId(revokeId === certificate.certificate_id ? null : certificate.certificate_id); setReason(""); }}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-rose-300 px-3 py-2 text-xs font-bold text-rose-800 hover:bg-rose-50">
                    <ShieldAlert className="h-3.5 w-3.5" /> Revoke
                  </button>}
                </div>
              </div>
              {revokeId === certificate.certificate_id && <form onSubmit={submitRevocation} className="mt-5 rounded-xl border border-rose-200 bg-rose-50/60 p-4">
                <label htmlFor="revocation-reason" className="block text-xs font-bold text-rose-900">Required revocation reason</label>
                <textarea id="revocation-reason" required maxLength={5000} value={reason} onChange={(event) => setReason(event.target.value)}
                  className="mt-2 min-h-20 w-full rounded-lg border border-rose-200 bg-white p-3 text-sm text-stone-800 outline-none focus:ring-2 focus:ring-rose-400" />
                <div className="mt-3 flex flex-wrap gap-2">
                  <button disabled={saving || !reason.trim()} className="rounded-lg bg-rose-700 px-3 py-2 text-xs font-bold text-white disabled:opacity-50">{saving ? "Recording…" : "Record revocation"}</button>
                  <button type="button" onClick={() => setRevokeId(null)} className="rounded-lg border border-stone-300 px-3 py-2 text-xs font-semibold text-stone-700">Cancel</button>
                </div>
              </form>}
              <details className="mt-4 border-t border-stone-100 pt-3">
                <summary className="flex cursor-pointer list-none items-center gap-2 text-[11px] font-semibold text-stone-500">
                  <RotateCcw className="h-3.5 w-3.5" /> Certificate metadata
                </summary>
                <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-2">
                  <div><dt className="font-bold text-stone-600">AI engine and mode</dt><dd className="mt-1 text-stone-700">{certificate.ai_engine} · {certificate.ai_mode}</dd></div>
                  <div><dt className="font-bold text-stone-600">Approval chain hash</dt><dd className="mt-1 break-all font-mono text-[10px] text-stone-700">{certificate.audit_chain_head_hash}</dd></div>
                </dl>
              </details>
            </article>
          ))}
        </div>}
    </div>
  );
};
