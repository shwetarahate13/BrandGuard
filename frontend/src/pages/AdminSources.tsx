import React, { useEffect, useState } from "react";
import {
  BookOpen,
  CheckCircle,
  Plus,
  RefreshCw,
  Layers,
  Image as ImageIcon,
  SpellCheck,
} from "lucide-react";
import { api } from "../api";
import { GuidelineDoc, ApprovedFact, Term, Asset } from "../types";
import { EmptyState } from "../components/ui";
import { useToast } from "../components/Toast";

interface AdminSourcesProps { canManage?: boolean; }

export const AdminSources: React.FC<AdminSourcesProps> = ({ canManage = false }) => {
  const [activeTab, setActiveTab] = useState<"guidelines" | "facts" | "terms" | "assets" | "brand_words">("guidelines");
  const [guidelines, setGuidelines] = useState<GuidelineDoc[]>([]);
  const [facts, setFacts] = useState<ApprovedFact[]>([]);
  const [terms, setTerms] = useState<Term[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [brandWords, setBrandWords] = useState<string[]>([]);
  const [brandWordsInput, setBrandWordsInput] = useState("");
  const [brandWordsSaved, setBrandWordsSaved] = useState<string | null>(null);
  const [ruleDisputes, setRuleDisputes] = useState<{ threshold: number; rules: Record<string, number>; suppressed: string[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reindexing, setReindexing] = useState(false);
  const [reindexMsg, setReindexMsg] = useState<string | null>(null);
  const [savingSource, setSavingSource] = useState(false);
  const { showToast } = useToast();

  // New guideline form
  const [showAddGuideline, setShowAddGuideline] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newText, setNewText] = useState("");

  // New fact form
  const [showAddFact, setShowAddFact] = useState(false);
  const [newStatement, setNewStatement] = useState("");
  const [newNote, setNewNote] = useState("");
  const [newValidTo, setNewValidTo] = useState("");

  // New term form
  const [showAddTerm, setShowAddTerm] = useState(false);
  const [newPreferred, setNewPreferred] = useState("");
  const [newAvoid, setNewAvoid] = useState("");
  const [newTermNote, setNewTermNote] = useState("");

  const loadAll = async () => {
    try {
      setLoading(true);
      setLoadError(null);
      const [g, f, t, a, settings, disputes] = await Promise.all([
        api.getGuidelines(),
        api.getFacts(),
        api.getTerms(),
        api.getAssets(),
        canManage ? api.getSystemSettings() : Promise.resolve(null),
        canManage ? api.getWritingRuleDisputes() : Promise.resolve(null),
      ]);
      setGuidelines(g);
      setFacts(f);
      setTerms(t);
      setAssets(a);
      if (settings) setBrandWords(settings.brand_words || []);
      if (disputes) setRuleDisputes(disputes);
    } catch (err) {
      console.error("Failed to load sources:", err);
      setLoadError(err instanceof Error ? err.message : "Unable to load approved sources.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  const handleReindex = async () => {
    setReindexing(true);
    setReindexMsg(null);
    try {
      const res = await api.reindexSources();
      setReindexMsg(`Indexed ${res.indexed_count} approved sources for retrieval.`);
      setTimeout(() => setReindexMsg(null), 5000);
    } catch (err: any) {
      setReindexMsg(`Index refresh failed: ${err.message}`);
    } finally {
      setReindexing(false);
    }
  };

  const handleCreateGuideline = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || !newText.trim()) return;
    setSavingSource(true);
    try {
      await api.createGuideline(newTitle.trim(), newText.trim());
      setShowAddGuideline(false);
      setNewTitle("");
      setNewText("");
      await loadAll();
      showToast("Guideline document added.", "success");
    } catch (err: any) {
      showToast(`Could not save the guideline. ${err.message}`, "error");
    } finally {
      setSavingSource(false);
    }
  };

  const handleCreateFact = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newStatement.trim()) return;
    setSavingSource(true);
    try {
      await api.createFact({
        statement: newStatement.trim(),
        source_note: newNote.trim() || undefined,
        valid_to: newValidTo ? new Date(newValidTo).toISOString() : undefined,
      });
      setShowAddFact(false);
      setNewStatement("");
      setNewNote("");
      setNewValidTo("");
      await loadAll();
      showToast("Approved fact added.", "success");
    } catch (err: any) {
      showToast(`Could not save the approved fact. ${err.message}`, "error");
    } finally {
      setSavingSource(false);
    }
  };

  const handleCreateTerm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPreferred.trim()) return;
    setSavingSource(true);
    try {
      const avoidList = newAvoid.split(",").map((s) => s.trim()).filter(Boolean);
      await api.createTerm({
        preferred: newPreferred.trim(),
        avoid: avoidList,
        note: newTermNote.trim() || undefined,
      });
      setShowAddTerm(false);
      setNewPreferred("");
      setNewAvoid("");
      setNewTermNote("");
      await loadAll();
      showToast("Terminology rule added.", "success");
    } catch (err: any) {
      showToast(`Could not save the terminology rule. ${err.message}`, "error");
    } finally {
      setSavingSource(false);
    }
  };

  const saveBrandWords = async () => {
    const words = Array.from(new Set(brandWordsInput.split(/[,\n]/).map((word) => word.trim()).filter(Boolean)));
    setSavingSource(true);
    try {
      const saved = await api.updateSystemSettings({ brand_words: words });
      setBrandWords(saved.brand_words || words);
      setBrandWordsInput("");
      setBrandWordsSaved("Brand words saved.");
      window.setTimeout(() => setBrandWordsSaved(null), 3000);
    } catch (err) {
      setBrandWordsSaved(err instanceof Error ? err.message : "Unable to save brand words.");
    } finally {
      setSavingSource(false);
    }
  };

  const resetWritingRuleDisputes = async () => {
    setSavingSource(true);
    try {
      await api.resetWritingRuleDisputes();
      setRuleDisputes({ threshold: 3, rules: {}, suppressed: [] });
    } catch (err) {
      setBrandWordsSaved(err instanceof Error ? err.message : "Unable to reset grammar-rule disputes.");
    } finally {
      setSavingSource(false);
    }
  };

  const isExpired = (validTo?: string) => {
    if (!validTo) return false;
    return new Date(validTo) < new Date();
  };

  return (
    <div className="sources-page max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Header & Reindex Button */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-stone-200">
        <div>
          <h1 className="text-2xl font-bold text-stone-900 tracking-tight">Approved Brand Sources</h1>
          <p className="text-sm text-stone-500 mt-1">
            Ground-truth repository of voice guidelines, certified facts, terminology, and assets.
          </p>
        </div>

        {canManage && <button
          onClick={handleReindex}
          disabled={reindexing}
          className="ui-button ui-button--primary"
        >
          <RefreshCw className={`w-3.5 h-3.5 text-amber-400 ${reindexing ? "animate-spin" : ""}`} />
          {reindexing ? "Refreshing search index…" : "Refresh search index"}
        </button>}
      </div>

      {reindexMsg && (
        <div role="status" className={`p-3 rounded-xl text-sm font-medium ${reindexMsg.includes("failed") ? "bg-rose-50 border border-rose-200 text-rose-800" : "bg-emerald-50 border border-emerald-200 text-emerald-800"}`}>
          {reindexMsg}
        </div>
      )}

      {loading && (
        <div role="status" className="text-center py-4 text-xs text-stone-500 animate-pulse">
          Loading approved brand sources...
        </div>
      )}
      {loadError && (
        <div role="alert" className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800">
          <span>Could not load approved sources: {loadError}</span>
          <button onClick={loadAll} className="ml-3 underline font-semibold">Try again</button>
        </div>
      )}

      {/* Tabs */}
      <div role="tablist" aria-label="Approved source categories" className="ui-tabs">
        {[
          { id: "guidelines", label: `Guidelines (${guidelines.length})`, icon: BookOpen },
          { id: "facts", label: `Approved Facts (${facts.length})`, icon: CheckCircle },
          { id: "terms", label: `Terminology (${terms.length})`, icon: Layers },
          { id: "assets", label: `Brand Assets (${assets.length})`, icon: ImageIcon },
          ...(canManage ? [{ id: "brand_words", label: `Brand words (${brandWords.length})`, icon: SpellCheck }] : []),
        ].map((t) => {
          const Icon = t.icon;
          const active = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id as any)}
              type="button"
              role="tab"
              aria-selected={active}
              aria-controls={`source-panel-${t.id}`}
              id={`source-tab-${t.id}`}
              className={`ui-tab flex items-center gap-1.5 py-3 px-4 text-xs font-semibold border-b-2 transition-colors ${
                active
                  ? "border-stone-900 text-stone-900"
                  : "border-transparent text-stone-500 hover:text-stone-800"
              }`}
            >
              <Icon className="w-4 h-4" />
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Tab 1: Guidelines */}
      {activeTab === "guidelines" && !loading && !loadError && (
        <div id="source-panel-guidelines" role="tabpanel" aria-labelledby="source-tab-guidelines" className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-sm font-bold text-stone-800">Brand Voice & Claims Policy Docs</h2>
            {canManage && <button
              onClick={() => setShowAddGuideline(!showAddGuideline)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-stone-900 text-white rounded-lg text-xs font-medium"
            >
              <Plus className="w-3.5 h-3.5 text-amber-400" />
              New guideline
            </button>}
          </div>

          {canManage && showAddGuideline && (
            <form onSubmit={handleCreateGuideline} className="bg-white border border-stone-200 rounded-xl p-5 shadow-sm space-y-4">
              <h3 className="font-bold text-xs uppercase tracking-wider text-stone-700">Import Guideline Document</h3>
              <p className="text-xs text-stone-500">
                Paste markdown or text with headers (e.g. <code>## Tone and Voice</code>). The system will automatically split it into reviewable clauses for citation.
              </p>
              <div>
                <label htmlFor="source-guideline-title" className="block text-sm font-semibold text-stone-700 mb-1">Document title</label>
                <input
                  id="source-guideline-title"
                  type="text"
                  placeholder="e.g. Aurelia Foods Brand Guidelines"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  required
                  className="w-full px-3 py-3 text-base border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div>
                <label htmlFor="source-guideline-content" className="block text-sm font-semibold text-stone-700 mb-1">Document content</label>
                <textarea
                  id="source-guideline-content"
                  rows={6}
                  placeholder="Paste guideline text..."
                  value={newText}
                  onChange={(e) => setNewText(e.target.value)}
                  required
                  className="w-full p-3 text-base border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowAddGuideline(false)}
                  className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingSource}
                  className="ui-button ui-button--primary"
                >
                  {savingSource ? "Saving…" : "Save and split clauses"}
                </button>
              </div>
            </form>
          )}

          <div className="space-y-4">
            {guidelines.length === 0 ? <EmptyState title="No guideline documents yet" description={canManage ? "Add the approved voice, claims, and accessibility rules your team should follow." : "Ask an administrator to add the approved brand guidelines."} action={canManage ? <button type="button" className="ui-button ui-button--primary" onClick={() => setShowAddGuideline(true)}>Add guideline document</button> : undefined} /> : guidelines.map((doc) => (
              <div key={doc.id} className="bg-white border border-stone-200 rounded-xl p-6 shadow-sm space-y-4">
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-bold text-stone-900 text-base">{doc.title}</h3>
                    {doc.description && <p className="text-xs text-stone-500 mt-0.5">{doc.description}</p>}
                  </div>
                  <span className="text-xs bg-stone-100 text-stone-700 font-semibold px-2 py-0.5 rounded border border-stone-200">
                    {doc.clauses?.length || 0} Clauses
                  </span>
                </div>

                <div className="grid gap-2.5 pt-2">
                  {doc.clauses?.map((c) => (
                    <div key={c.id} className="p-3 bg-stone-50 rounded-lg border border-stone-200/80 text-xs">
                      <div className="flex items-center gap-2 font-bold text-stone-800 mb-1">
                        {c.code && (
                          <span className="font-mono text-[10px] bg-amber-100 text-amber-900 px-1.5 py-0.2 rounded border border-amber-300">
                            {c.code}
                          </span>
                        )}
                        <span>{c.title}</span>
                      </div>
                      <p className="text-stone-600 leading-relaxed font-sans">{c.text}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === "brand_words" && canManage && !loading && !loadError && (
        <section id="source-panel-brand_words" role="tabpanel" aria-labelledby="source-tab-brand_words" className="max-w-3xl bg-white border border-stone-200 rounded-xl p-5 space-y-4">
          <div>
            <h2 className="text-sm font-bold text-stone-800">Brand words</h2>
            <p className="text-xs text-stone-500 mt-1">Add approved names and spellings that the writing assistant should leave unchanged.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {brandWords.length ? brandWords.map((word) => <span key={word} className="rounded-full bg-stone-100 border border-stone-200 px-3 py-1 text-xs text-stone-700">{word}</span>) : <span className="text-xs text-stone-500">No extra brand words yet.</span>}
          </div>
          <label htmlFor="source-brand-words" className="block text-sm font-semibold text-stone-700">Add or replace list <span className="font-normal text-stone-500">(comma or line separated)</span></label>
          <textarea id="source-brand-words" rows={3} value={brandWordsInput} onChange={(event) => setBrandWordsInput(event.target.value)} placeholder="Aurelia, Golden Oat Elixir" className="w-full rounded-lg border border-stone-300 p-3 text-base" />
          <div className="flex items-center justify-between">
            <span role="status" className="text-xs text-stone-600">{brandWordsSaved}</span>
            <button type="button" onClick={saveBrandWords} disabled={savingSource || !brandWordsInput.trim()} className="ui-button ui-button--primary">{savingSource ? "Saving…" : "Save brand words"}</button>
          </div>
          <div className="border-t border-stone-200 pt-4">
            <div className="flex items-center justify-between gap-3">
              <div><h3 className="text-xs font-bold text-stone-800">Disputed grammar rules</h3><p className="mt-1 text-[11px] text-stone-500">A rule is suppressed after {ruleDisputes?.threshold || 3} distinct disputes. Reset clears these rule counters.</p></div>
              <button type="button" onClick={resetWritingRuleDisputes} disabled={savingSource || !ruleDisputes?.rules || Object.keys(ruleDisputes.rules).length === 0} className="ui-button ui-button--quiet">{savingSource ? "Resetting…" : "Reset rule disputes"}</button>
            </div>
            {ruleDisputes && <div className="mt-3 flex flex-wrap gap-2">{Object.entries(ruleDisputes.rules).length ? Object.entries(ruleDisputes.rules).map(([rule, count]) => <span key={rule} className={`rounded-full border px-3 py-1 text-xs ${ruleDisputes.suppressed.includes(rule) ? "border-rose-200 bg-rose-50 text-rose-800" : "border-stone-200 bg-stone-50 text-stone-700"}`}>{rule}: {count} disputes{ruleDisputes.suppressed.includes(rule) ? " · suppressed" : ""}</span>) : <span className="text-xs text-stone-500">No grammar rule disputes recorded.</span>}</div>}
          </div>
        </section>
      )}

      {/* Tab 2: Approved Facts */}
      {activeTab === "facts" && !loading && !loadError && (
        <div id="source-panel-facts" role="tabpanel" aria-labelledby="source-tab-facts" className="space-y-4">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-sm font-bold text-stone-800">Approved Truth Ledger ({facts.length} Facts)</h2>
              <p className="text-[11px] text-stone-500">Includes active facts and expired entries for testing outdated info detection.</p>
            </div>
            {canManage && <button
              onClick={() => setShowAddFact(!showAddFact)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-stone-900 text-white rounded-lg text-xs font-medium"
            >
              <Plus className="w-3.5 h-3.5 text-amber-400" />
              New fact
            </button>}
          </div>

          {canManage && showAddFact && (
            <form onSubmit={handleCreateFact} className="bg-white border border-stone-200 rounded-xl p-5 shadow-sm space-y-4">
              <h3 className="font-bold text-xs uppercase tracking-wider text-stone-700">Add Approved Fact</h3>
              <div>
                <label htmlFor="source-fact-statement" className="block text-sm font-semibold text-stone-700 mb-1">Statement</label>
                <input
                  id="source-fact-statement"
                  type="text"
                  placeholder="e.g. As of 2024, our Portland kitchen operates on 85% certified solar energy."
                  value={newStatement}
                  onChange={(e) => setNewStatement(e.target.value)}
                  required
                  className="w-full px-3 py-3 text-base border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="source-fact-note" className="block text-sm font-semibold text-stone-700 mb-1">Source note or certificate number</label>
                  <input
                    id="source-fact-note"
                    type="text"
                    placeholder="e.g. 2024 Green Energy Audit"
                    value={newNote}
                    onChange={(e) => setNewNote(e.target.value)}
                    className="w-full px-3 py-2 text-xs border border-stone-300 rounded-lg"
                  />
                </div>
                <div>
                  <label htmlFor="source-fact-valid-to" className="block text-sm font-semibold text-stone-700 mb-1">Valid through (optional expiry)</label>
                  <input
                    id="source-fact-valid-to"
                    type="date"
                    value={newValidTo}
                    onChange={(e) => setNewValidTo(e.target.value)}
                    className="w-full px-3 py-2 text-xs border border-stone-300 rounded-lg"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowAddFact(false)}
                  className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingSource}
                  className="ui-button ui-button--primary"
                >
                  {savingSource ? "Saving…" : "Add fact"}
                </button>
              </div>
            </form>
          )}

          <div className="bg-white border border-stone-200 rounded-xl divide-y divide-stone-100 shadow-sm overflow-hidden">
            {facts.length === 0 ? <EmptyState title="No approved facts yet" description={canManage ? "Add current product or company facts with a source and expiry date." : "Ask an administrator to add approved facts for this workspace."} action={canManage ? <button type="button" className="ui-button ui-button--primary" onClick={() => setShowAddFact(true)}>Add approved fact</button> : undefined} /> : facts.map((fact) => {
              const expired = isExpired(fact.valid_to);
              return (
                <div key={fact.id} className="p-4 flex items-start justify-between gap-4 hover:bg-stone-50/50">
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-stone-900">{fact.statement}</p>
                    <div className="flex items-center gap-2 text-[11px] text-stone-400">
                      {fact.source_note && <span>Source: {fact.source_note}</span>}
                      {fact.valid_to && (
                        <span>
                          • Expiration: {new Date(fact.valid_to).toLocaleDateString()}
                        </span>
                      )}
                    </div>
                  </div>
                  <div>
                    {expired ? (
                      <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-rose-50 text-rose-700 border border-rose-200">
                        Expired Fact
                      </span>
                    ) : (
                      <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                        Active Truth
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Tab 3: Terms */}
      {activeTab === "terms" && !loading && !loadError && (
        <div id="source-panel-terms" role="tabpanel" aria-labelledby="source-tab-terms" className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-sm font-bold text-stone-800">Approved Terminology Registry</h2>
            {canManage && <button
              onClick={() => setShowAddTerm(!showAddTerm)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-stone-900 text-white rounded-lg text-xs font-medium"
            >
              <Plus className="w-3.5 h-3.5 text-amber-400" />
              New term
            </button>}
          </div>

          {canManage && showAddTerm && (
            <form onSubmit={handleCreateTerm} className="bg-white border border-stone-200 rounded-xl p-5 shadow-sm space-y-4">
              <h3 className="font-bold text-xs uppercase tracking-wider text-stone-700">Add Terminology Rule</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="source-term-preferred" className="block text-sm font-semibold text-stone-700 mb-1">Preferred term</label>
                  <input
                    id="source-term-preferred"
                    type="text"
                    placeholder="e.g. patrons"
                    value={newPreferred}
                    onChange={(e) => setNewPreferred(e.target.value)}
                    required
                    className="w-full px-3 py-2 text-xs border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>
                <div>
                  <label htmlFor="source-term-avoid" className="block text-sm font-semibold text-stone-700 mb-1">Terms to avoid (comma-separated)</label>
                  <input
                    id="source-term-avoid"
                    type="text"
                    placeholder="e.g. users, consumers, buyers"
                    value={newAvoid}
                    onChange={(e) => setNewAvoid(e.target.value)}
                    required
                    className="w-full px-3 py-2 text-xs border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowAddTerm(false)}
                  className="px-3 py-1.5 text-xs text-stone-600 hover:bg-stone-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingSource}
                  className="ui-button ui-button--primary"
                >
                  {savingSource ? "Saving…" : "Save term"}
                </button>
              </div>
            </form>
          )}

          <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-4">
            {terms.length === 0 ? <EmptyState title="No terminology rules yet" description={canManage ? "Add preferred terms and wording to avoid in reviews." : "Ask an administrator to add the approved terminology list."} action={canManage ? <button type="button" className="ui-button ui-button--primary" onClick={() => setShowAddTerm(true)}>Add terminology rule</button> : undefined} /> : terms.map((t) => (
              <div key={t.id} className="bg-white border border-stone-200 rounded-xl p-4 shadow-sm space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-emerald-800 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded text-xs">
                    Use: {t.preferred}
                  </span>
                </div>
                <div className="text-xs text-stone-500">
                  <span className="font-semibold text-rose-700">Avoid:</span>{" "}
                  {Array.isArray(t.avoid) ? t.avoid.join(", ") : t.avoid}
                </div>
                {t.note && <p className="text-[11px] text-stone-400 italic">{t.note}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 4: Assets */}
      {activeTab === "assets" && !loading && !loadError && (
        <div id="source-panel-assets" role="tabpanel" aria-labelledby="source-tab-assets" className="space-y-4">
          <h2 className="text-sm font-bold text-stone-800">Approved Brand Assets ({assets.length})</h2>
          <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-4">
            {assets.length === 0 ? <EmptyState title="No approved assets yet" description="Brand assets added by an administrator will appear here." /> : assets.map((asset) => (
              <div key={asset.id} className="bg-white border border-stone-200 rounded-xl p-4 shadow-sm space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-stone-900 text-xs">{asset.name}</span>
                  <span className="text-[10px] uppercase font-bold px-1.5 py-0.2 rounded bg-stone-100 text-stone-600 border">
                    {asset.kind}
                  </span>
                </div>
                <p className="text-[11px] font-mono text-stone-400 truncate">{asset.file_path || "Standard Asset"}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
