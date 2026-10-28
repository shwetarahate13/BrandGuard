import React, { useEffect, useState } from "react";
import { BadgeCheck, Download, ExternalLink, RotateCcw, ShieldAlert } from "lucide-react";
import { api } from "../api";
import { Badge, Button, Card, EmptyState } from "../components/ui";
import { Skeleton } from "../components/Skeleton";
import { CertificateInfo, User } from "../types";

interface CertificateLibraryProps {
  user: User;
  navigate: (path: string) => void;
}

const statusTone = (status: string): "success" | "warning" | "danger" | "neutral" => {
  if (status === "valid") return "success";
  if (status === "superseded") return "warning";
  if (status === "revoked" || status === "tampered") return "danger";
  return "neutral";
};

export const CertificateLibrary: React.FC<CertificateLibraryProps> = ({ user, navigate }) => {
  const [certificates, setCertificates] = useState<CertificateInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revokeId, setRevokeId] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

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

  const download = async (certificateId: string) => {
    setDownloadingId(certificateId);
    setError(null);
    try {
      await api.downloadCertificate(certificateId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to download this certificate.");
    } finally {
      setDownloadingId(null);
    }
  };

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
      {loading ? (
        <div className="space-y-3" aria-label="Loading certificates" aria-busy="true">
          {[0, 1].map((item) => <Skeleton key={item} className="h-36 rounded-xl" />)}
        </div>
      ) : error && certificates.length === 0 ? (
        <EmptyState title="Certificates could not be loaded" description="Check your connection or access, then try again." action={<Button variant="secondary" onClick={() => void load()}><RotateCcw className="h-4 w-4" /> Try again</Button>} />
      ) : certificates.length === 0 ? (
        <Card>
          <EmptyState title="No certificates are available" description="Approved submissions will appear here when you are allowed to access them." />
        </Card>
      ) : <div className="space-y-4">
        {certificates.map((certificate) => (
          <Card key={certificate.certificate_id} className="p-5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-base font-bold text-stone-900">{certificate.title}</h2>
                  <Badge tone={statusTone(certificate.status)} className="uppercase tracking-wide">{certificate.status}</Badge>
                </div>
                <p className="mt-2 break-all font-mono text-xs text-stone-500">{certificate.certificate_id} · Version {certificate.approved_version}</p>
                <p className="mt-2 text-xs text-stone-600">
                  Approved by {certificate.approver.name} ({certificate.approver.role})
                  {certificate.approved_at ? ` · ${new Date(certificate.approved_at).toLocaleString()}` : ""}
                </p>
                <p className="mt-3 break-all font-mono text-[10px] text-stone-500">SHA-256 {certificate.content_hash}</p>
              </div>
              <div className="flex shrink-0 flex-wrap gap-2">
                <Button variant="primary" loading={downloadingId === certificate.certificate_id} onClick={() => void download(certificate.certificate_id)}>
                  <Download className="h-4 w-4" /> {downloadingId === certificate.certificate_id ? "Preparing PDF…" : "Download PDF"}
                </Button>
                <Button variant="secondary" onClick={() => navigate(`/verify?certificate_id=${encodeURIComponent(certificate.certificate_id)}`)}>
                  <ExternalLink className="h-4 w-4" /> Verify
                </Button>
                {canRevoke && certificate.status === "valid" && <Button variant="danger" onClick={() => { setRevokeId(revokeId === certificate.certificate_id ? null : certificate.certificate_id); setReason(""); }}>
                  <ShieldAlert className="h-4 w-4" /> Revoke
                </Button>}
              </div>
            </div>
            {revokeId === certificate.certificate_id && <form onSubmit={submitRevocation} className="mt-5 rounded-xl border border-rose-200 bg-rose-50/60 p-4">
              <label htmlFor="revocation-reason" className="block text-sm font-bold text-rose-900">Required revocation reason</label>
              <textarea id="revocation-reason" required maxLength={5000} value={reason} onChange={(event) => setReason(event.target.value)}
                className="mt-2 min-h-24 w-full rounded-lg border border-stone-300 bg-white p-3 text-base text-stone-800 outline-none focus:ring-2 focus:ring-rose-400" />
              <div className="mt-3 flex flex-wrap gap-2">
                <Button variant="danger" loading={saving} disabled={!reason.trim()}>{saving ? "Recording…" : "Record revocation"}</Button>
                <Button type="button" variant="secondary" onClick={() => setRevokeId(null)}>Cancel</Button>
              </div>
            </form>}
            <details className="mt-4 border-t border-stone-100 pt-3">
              <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 text-sm font-semibold text-stone-600">
                <RotateCcw className="h-4 w-4" /> Certificate metadata
              </summary>
              <dl className="grid gap-3 pb-1 text-sm sm:grid-cols-2">
                <div><dt className="font-bold text-stone-600">AI engine and mode</dt><dd className="mt-1 text-stone-700">{certificate.ai_engine} · {certificate.ai_mode}</dd></div>
                <div><dt className="font-bold text-stone-600">Approval chain hash</dt><dd className="mt-1 break-all font-mono text-xs text-stone-700">{certificate.audit_chain_head_hash}</dd></div>
              </dl>
            </details>
          </Card>
        ))}
      </div>}
      {!loading && certificates.length > 0 && <p className="flex items-center gap-2 text-xs text-stone-600"><BadgeCheck className="h-4 w-4 text-emerald-700" /> Certificates contain approval metadata, not the approved copy.</p>}
    </div>
  );
};
