import React, { useEffect, useState } from "react";
import { Download, ShieldCheck, ShieldX } from "lucide-react";
import { api } from "../api";
import { AuditIntegrityReport } from "../types";

export const IntegrityCheck: React.FC = () => {
  const [report, setReport] = useState<AuditIntegrityReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getAuditIntegrity().then(setReport).catch((err) => setError(err instanceof Error ? err.message : "Unable to run the audit integrity check.")).finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-8 sm:px-6 lg:px-8">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div><p className="text-xs font-bold uppercase tracking-[0.18em] text-amber-800">Administrator tools</p><h1 className="mt-2 text-2xl font-bold tracking-tight text-stone-900">Audit Integrity Check</h1><p className="mt-2 text-sm text-stone-600">Recomputes every audit chain and compares it with the stored chain head.</p></div>
        {report && <button onClick={() => void api.downloadAuditIntegrity().catch((err) => setError(err.message))} className="inline-flex items-center justify-center gap-2 rounded-lg bg-stone-900 px-4 py-2.5 text-xs font-bold text-white hover:bg-stone-700"><Download className="h-4 w-4" /> Export results</button>}
      </header>
      {error && <div role="alert" className="rounded-lg border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</div>}
      {loading ? <p className="py-12 text-center text-sm text-stone-500">Checking audit chains…</p> : report && <>
        <div className="grid gap-3 sm:grid-cols-4">
          {[ ["Chains checked", report.total_chains], ["Valid chains", report.valid_chains], ["Invalid chains", report.invalid_chains], ["Entries checked", report.total_entries] ].map(([label, value]) => <div key={label} className="rounded-xl border border-stone-200 bg-white p-4 shadow-sm"><p className="text-[10px] font-bold uppercase tracking-wide text-stone-500">{label}</p><p className="mt-2 text-2xl font-extrabold text-stone-900">{value}</p></div>)}
        </div>
        <p className="text-[11px] text-stone-500">Checked {new Date(report.checked_at).toLocaleString()}</p>
        <div className="overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm">
          <div className="border-b border-stone-200 px-5 py-4"><h2 className="text-sm font-bold text-stone-900">Chain results</h2></div>
          {report.chains.length === 0 ? <p className="p-6 text-center text-sm text-stone-500">No audit entries have been recorded yet.</p> : <div className="divide-y divide-stone-100">
            {report.chains.map((chain) => <article key={chain.scope_id} className="p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex min-w-0 items-start gap-3">{chain.valid ? <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-700" /> : <ShieldX className="mt-0.5 h-5 w-5 shrink-0 text-rose-700" />}<div className="min-w-0"><h3 className="text-sm font-bold text-stone-900">{chain.submission_id ? `Submission ${chain.submission_id}` : "Workspace events"}</h3><p className="mt-1 text-xs text-stone-600">{chain.entry_count} audit entr{chain.entry_count === 1 ? "y" : "ies"} · {chain.valid ? "Valid" : "Integrity issue detected"}</p></div></div>
                <code className="max-w-full break-all text-[10px] text-stone-500">{chain.head_hash || "(empty chain)"}</code>
              </div>
              {chain.errors.length > 0 && <ul className="mt-3 list-inside list-disc rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-800">{chain.errors.map((item, index) => <li key={`${chain.scope_id}-${index}`}>{item}</li>)}</ul>}
            </article>)}
          </div>}
        </div>
      </>}
    </div>
  );
};
