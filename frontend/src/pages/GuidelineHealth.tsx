import React, { useEffect, useMemo, useState } from "react";
import { AlertCircle, ArrowDown, ArrowUp, ArrowUpDown, RefreshCw } from "lucide-react";
import { api } from "../api";
import { GuidelineHealthClause } from "../types";
import { DiffViewer } from "../components/DiffViewer";

type SortKey = "dfi" | "title";

function riskBand(dfi: number) {
  if (dfi < 10) return { label: "Low", color: "bg-emerald-50 text-emerald-800 border-emerald-200" };
  if (dfi <= 30) return { label: "Moderate", color: "bg-amber-50 text-amber-800 border-amber-200" };
  return { label: "High", color: "bg-rose-50 text-rose-800 border-rose-200" };
}

export const GuidelineHealth: React.FC = () => {
  const [clauses, setClauses] = useState<GuidelineHealthClause[]>([]);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [sortKey, setSortKey] = useState<SortKey>("dfi");
  const [descending, setDescending] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState("");
  const [applying, setApplying] = useState(false);
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());
  const [notice, setNotice] = useState<string | null>(null);

  const loadHealth = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getGuidelineHealth();
      setClauses(data);
      setSelectedId((current) => current && data.some((clause) => clause.id === current)
        ? current
        : data[0]?.id || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load guideline health.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHealth();
  }, []);

  const sortedClauses = useMemo(() => [...clauses].sort((left, right) => {
    const comparison = sortKey === "dfi"
      ? left.dispute_friction_index - right.dispute_friction_index
      : (left.title || left.code || "").localeCompare(right.title || right.code || "");
    return descending ? -comparison : comparison;
  }), [clauses, sortKey, descending]);

  const selectedClause = clauses.find((clause) => clause.id === selectedId) || null;

  const recomputeHealth = async () => {
    try {
      setRecomputing(true);
      setError(null);
      const result = await api.recomputeGuidelineHealth();
      setNotice(result.message);
      await loadHealth();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to recompute guideline health.");
    } finally {
      setRecomputing(false);
    }
  };

  const changeSort = (key: SortKey) => {
    if (key === sortKey) setDescending((value) => !value);
    else {
      setSortKey(key);
      setDescending(key === "dfi");
    }
  };

  const startEditing = () => {
    if (!selectedClause?.proposed_revision) return;
    setEditText(selectedClause.proposed_revision);
    setEditing(true);
    setError(null);
  };

  const applyRevision = async (text: string) => {
    if (!selectedClause) return;
    if (text.includes("[ADD:")) {
      setError("Replace both offline template prompts before applying a guideline revision.");
      return;
    }
    try {
      setApplying(true);
      setError(null);
      await api.applyGuidelineRevision(selectedClause.id, text);
      setClauses((current) => current.map((clause) => clause.id === selectedClause.id
        ? { ...clause, text, proposed_revision: null, proposal_source: null }
        : clause));
      setEditing(false);
      setDismissedIds((current) => new Set(current).add(selectedClause.id));
      setNotice("Guideline revision applied and approved sources reindexed.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to apply this revision.");
    } finally {
      setApplying(false);
    }
  };

  const selectedRisk = selectedClause ? riskBand(selectedClause.dispute_friction_index) : null;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-stone-900 tracking-tight">Guideline Health</h1>
          <p className="text-xs text-stone-500 mt-1 max-w-2xl">
            Dispute friction shows how often findings tied to each clause are disputed. High-friction clauses receive a live LLM suggestion when configured, or a clearly labelled offline clarification template.
          </p>
        </div>
        <button
          onClick={recomputeHealth}
          disabled={loading || recomputing}
          className="inline-flex items-center gap-2 px-3 py-2 border border-stone-300 bg-white rounded-lg text-xs font-semibold text-stone-700 disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${recomputing ? "animate-spin" : ""}`} />
          {recomputing ? "Recomputing…" : "Recompute now"}
        </button>
      </div>

      {error && (
        <div role="alert" className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span className="flex-1">{error}</span>
          <button onClick={loadHealth} className="underline font-semibold">Try again</button>
        </div>
      )}
      {notice && <p role="status" className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-800">{notice}</p>}

      <div className="bg-white border border-stone-200 rounded-2xl shadow-sm overflow-hidden">
        {loading ? (
          <div role="status" className="text-center py-16 text-xs text-stone-400 animate-pulse">Loading clause health data…</div>
        ) : sortedClauses.length === 0 ? (
          <div className="text-center py-16 text-xs text-stone-500">No guideline clauses are available yet.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-stone-50 border-b border-stone-200 text-[10px] uppercase tracking-wider text-stone-500">
                <tr>
                  <th className="px-5 py-3">
                    <button onClick={() => changeSort("title")} className="inline-flex items-center gap-1.5 font-bold hover:text-stone-900">
                      Clause
                      {sortKey === "title" ? (descending ? <ArrowDown className="w-3 h-3" /> : <ArrowUp className="w-3 h-3" />) : <ArrowUpDown className="w-3 h-3" />}
                    </button>
                  </th>
                  <th className="px-5 py-3">Guideline</th>
                  <th className="px-5 py-3">
                    <button onClick={() => changeSort("dfi")} className="inline-flex items-center gap-1.5 font-bold hover:text-stone-900">
                      Dispute Friction
                      {sortKey === "dfi" ? (descending ? <ArrowDown className="w-3 h-3" /> : <ArrowUp className="w-3 h-3" />) : <ArrowUpDown className="w-3 h-3" />}
                    </button>
                  </th>
                  <th className="px-5 py-3">Risk</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100">
                {sortedClauses.map((clause) => {
                  const risk = riskBand(clause.dispute_friction_index);
                  const active = selectedId === clause.id;
                  return (
                    <tr
                      key={clause.id}
                      onClick={() => { setSelectedId(clause.id); setEditing(false); setError(null); setNotice(null); }}
                      className={`cursor-pointer transition-colors ${active ? "bg-amber-50/70" : "hover:bg-stone-50"}`}
                    >
                      <td className="px-5 py-4 min-w-64">
                        <p className="font-semibold text-stone-900">{clause.code ? `${clause.code} · ` : ""}{clause.title || "Untitled clause"}</p>
                        <p className="mt-1 text-[11px] text-stone-500 line-clamp-2">{clause.text}</p>
                      </td>
                      <td className="px-5 py-4 text-stone-600">{clause.doc_title}</td>
                      <td className="px-5 py-4 font-bold tabular-nums text-stone-900">{clause.dispute_friction_index.toFixed(1)}%</td>
                      <td className="px-5 py-4">
                        <span className={`inline-flex px-2 py-1 rounded-full border text-[10px] font-bold uppercase ${risk.color}`}>{risk.label}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selectedClause && selectedRisk && selectedClause.dispute_friction_index > 30 && (
        <section className="bg-white border border-rose-200 rounded-2xl p-5 sm:p-6 shadow-sm space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-[10px] uppercase tracking-wider font-bold text-rose-700">High friction clause</p>
              <h2 className="text-base font-bold text-stone-900 mt-1">{selectedClause.title || selectedClause.code || "Guideline clause"}</h2>
              <p className="text-[11px] text-stone-500 mt-1">{selectedClause.doc_title} · DFI {selectedClause.dispute_friction_index.toFixed(1)}%</p>
            </div>
            <span className={`inline-flex px-2 py-1 rounded-full border text-[10px] font-bold uppercase ${selectedRisk.color}`}>{selectedRisk.label} risk</span>
          </div>

          {selectedClause.dispute_clusters.length > 0 && (
            <div className="rounded-xl bg-stone-50 border border-stone-200 p-4 space-y-2">
              <h3 className="text-[10px] uppercase tracking-wider font-bold text-stone-600">Recurring dispute themes</h3>
              {selectedClause.dispute_clusters.slice(0, 3).map((cluster, index) => (
                <div key={`${index}-${cluster.examples[0] || "theme"}`} className="text-xs text-stone-700">
                  <span className="font-semibold">{cluster.count} dispute{cluster.count === 1 ? "" : "s"}:</span>{" "}
                  {cluster.examples.join(" · ")}
                </div>
              ))}
            </div>
          )}

          {dismissedIds.has(selectedClause.id) ? (
            <p className="text-xs text-stone-500">The current suggestion is dismissed for this session.</p>
          ) : selectedClause.proposed_revision ? (
            <div className="rounded-xl border border-stone-200 p-4 space-y-4">
              <div>
                <h3 className="text-xs font-bold text-stone-800">
                  {selectedClause.proposal_source === "offline_template" ? "Offline clarification template" : "Suggested wording"}
                </h3>
                <p className="text-[11px] text-stone-500 mt-1">
                  {selectedClause.proposal_source === "offline_template"
                    ? "This template preserves the approved rule and is not ready to apply. Replace both [ADD: ...] prompts, then review the wording."
                    : "Review the proposed change before applying it to the approved clause."}
                </p>
              </div>
              {editing ? (
                <textarea
                  rows={5}
                  value={editText}
                  onChange={(event) => setEditText(event.target.value)}
                  className="w-full p-3 text-xs border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                  aria-label="Edit proposed guideline wording"
                />
              ) : (
                <DiffViewer original={selectedClause.text} replacement={selectedClause.proposed_revision} />
              )}
              <div className="flex flex-wrap justify-end gap-2">
                {editing ? (
                  <>
                    <button onClick={() => setEditing(false)} disabled={applying} className="px-3 py-1.5 border border-stone-300 rounded-lg text-xs font-semibold text-stone-700">Cancel edit</button>
                    <button onClick={() => applyRevision(editText)} disabled={applying || !editText.trim()} className="px-3 py-1.5 bg-stone-900 rounded-lg text-xs font-semibold text-white disabled:opacity-50">{applying ? "Applying…" : "Apply edited wording"}</button>
                  </>
                ) : (
                  <>
                    <button onClick={() => setDismissedIds((current) => new Set(current).add(selectedClause.id))} className="px-3 py-1.5 border border-stone-300 rounded-lg text-xs font-semibold text-stone-700">Dismiss</button>
                    <button onClick={startEditing} className="px-3 py-1.5 border border-stone-300 rounded-lg text-xs font-semibold text-stone-700">Edit</button>
                    {selectedClause.proposal_source !== "offline_template" && (
                      <button onClick={() => applyRevision(selectedClause.proposed_revision || "")} disabled={applying} className="px-3 py-1.5 bg-stone-900 rounded-lg text-xs font-semibold text-white disabled:opacity-50">{applying ? "Applying…" : "Accept revision"}</button>
                    )}
                  </>
                )}
              </div>
            </div>
          ) : (
            <p className="text-xs text-stone-500">A wording proposal is unavailable for this clause.</p>
          )}
        </section>
      )}
    </div>
  );
};
