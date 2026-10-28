import React, { useEffect, useState } from "react";
import { Download, RotateCcw, ShieldCheck, ShieldX } from "lucide-react";
import { api } from "../api";
import { Badge, Button, Card, EmptyState, Stat } from "../components/ui";
import { Skeleton } from "../components/Skeleton";
import { AuditIntegrityReport } from "../types";

export const IntegrityCheck: React.FC = () => {
  const [report, setReport] = useState<AuditIntegrityReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  const runCheck = async () => {
    setLoading(true);
    setError(null);
    try {
      setReport(await api.getAuditIntegrity());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to run the audit integrity check.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void runCheck(); }, []);

  const exportReport = async () => {
    setExporting(true);
    setError(null);
    try {
      await api.downloadAuditIntegrity();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to export the audit integrity report.");
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-8 sm:px-6 lg:px-8">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-amber-800">Administrator tools</p>
          <h1 className="mt-2 text-2xl font-bold tracking-tight text-stone-900">Audit Integrity Check</h1>
          <p className="mt-2 max-w-2xl text-sm text-stone-600">Recomputes every audit chain and compares it with the stored chain head.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" loading={loading} onClick={() => void runCheck()}><RotateCcw className="h-4 w-4" /> Run check again</Button>
          {report && <Button loading={exporting} onClick={() => void exportReport()}><Download className="h-4 w-4" /> Export results</Button>}
        </div>
      </header>

      {error && <div role="alert" className="rounded-lg border border-rose-300 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</div>}
      {loading ? (
        <div className="space-y-4" aria-label="Checking audit integrity" aria-busy="true">
          <div className="grid gap-3 sm:grid-cols-4">{[0, 1, 2, 3].map((item) => <Skeleton key={item} className="h-24 rounded-xl" />)}</div>
          <Skeleton className="h-48 rounded-xl" />
        </div>
      ) : !report ? (
        <Card><EmptyState title="Integrity check did not finish" description="The audit service could not return a report. Retry the check when the service is available." action={<Button variant="secondary" onClick={() => void runCheck()}><RotateCcw className="h-4 w-4" /> Retry check</Button>} /></Card>
      ) : <>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Chains checked" value={report.total_chains} />
          <Stat label="Valid chains" value={report.valid_chains} />
          <Stat label="Invalid chains" value={report.invalid_chains} />
          <Stat label="Entries checked" value={report.total_entries} />
        </div>
        <p className="text-sm text-stone-600" role="status">Checked {new Date(report.checked_at).toLocaleString()}</p>
        <Card className="overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-200 px-5 py-4">
            <div><h2 className="text-base font-bold text-stone-900">Chain results</h2><p className="mt-1 text-sm text-stone-600">Each result shows a chain summary and its stored head hash.</p></div>
            <Badge tone={report.invalid_chains > 0 ? "danger" : "success"}>{report.invalid_chains > 0 ? `${report.invalid_chains} issue${report.invalid_chains === 1 ? "" : "s"}` : "All chains valid"}</Badge>
          </div>
          {report.chains.length === 0 ? (
            <EmptyState title="No audit entries yet" description="Chain results will appear here after workspace actions are recorded." />
          ) : <div className="divide-y divide-stone-100">
            {report.chains.map((chain) => <article key={chain.scope_id} className="p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div className="flex min-w-0 items-start gap-3">
                  {chain.valid ? <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-700" aria-hidden="true" /> : <ShieldX className="mt-0.5 h-5 w-5 shrink-0 text-rose-700" aria-hidden="true" />}
                  <div className="min-w-0">
                    <h3 className="text-sm font-bold text-stone-900">{chain.submission_id ? `Submission ${chain.submission_id}` : "Workspace events"}</h3>
                    <p className="mt-1 text-sm text-stone-600">{chain.entry_count} audit entr{chain.entry_count === 1 ? "y" : "ies"}</p>
                    <Badge className="mt-2" tone={chain.valid ? "success" : "danger"}>{chain.valid ? "Valid" : "Integrity issue detected"}</Badge>
                  </div>
                </div>
                <code className="max-w-full break-all rounded-md bg-stone-100 px-2 py-1 font-mono text-xs text-stone-700">{chain.head_hash || "(empty chain)"}</code>
              </div>
              {chain.errors.length > 0 && <ul className="mt-3 list-inside list-disc rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-800">{chain.errors.map((item, index) => <li key={`${chain.scope_id}-${index}`}>{item}</li>)}</ul>}
            </article>)}
          </div>}
        </Card>
      </>}
    </div>
  );
};
