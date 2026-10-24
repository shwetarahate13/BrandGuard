import React, { useEffect, useState } from "react";
import {
  Database,
  BookOpen,
  CheckCircle,
  FileText,
  Upload,
  Plus,
  Trash2,
  RefreshCw,
  AlertCircle,
  Calendar,
  Layers,
  Image as ImageIcon,
} from "lucide-react";
import { api } from "../api";
import { GuidelineDoc, ApprovedFact, Term, Asset, User } from "../types";

interface AdminSourcesProps {
  user: User;
  navigate: (path: string) => void;
}

export const AdminSources: React.FC<AdminSourcesProps> = ({ user, navigate }) => {
  const [activeTab, setActiveTab] = useState<"guidelines" | "facts" | "terms" | "assets">("guidelines");
  const [guidelines, setGuidelines] = useState<GuidelineDoc[]>([]);
  const [facts, setFacts] = useState<ApprovedFact[]>([]);
  const [terms, setTerms] = useState<Term[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [reindexing, setReindexing] = useState(false);
  const [reindexMsg, setReindexMsg] = useState<string | null>(null);

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
      const [g, f, t, a] = await Promise.all([
        api.getGuidelines(),
        api.getFacts(),
        api.getTerms(),
        api.getAssets(),
      ]);
      setGuidelines(g);
      setFacts(f);
      setTerms(t);
      setAssets(a);
    } catch (err) {
      console.error("Failed to load sources:", err);
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
      setReindexMsg(`Successfully indexed ${res.indexed_count} sources into ChromaDB vector store.`);
      setTimeout(() => setReindexMsg(null), 5000);
    } catch (err: any) {
      setReindexMsg(`Reindex failed: ${err.message}`);
    } finally {
      setReindexing(false);
    }
  };

  const handleCreateGuideline = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim() || !newText.trim()) return;
    try {
      await api.createGuideline(newTitle.trim(), newText.trim());
      setShowAddGuideline(false);
      setNewTitle("");
      setNewText("");
      await loadAll();
    } catch (err: any) {
      alert(`Error creating guideline: ${err.message}`);
    }
  };

  const handleCreateFact = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newStatement.trim()) return;
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
    } catch (err: any) {
      alert(`Error creating fact: ${err.message}`);
    }
  };

  const handleCreateTerm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPreferred.trim()) return;
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
    } catch (err: any) {
      alert(`Error creating term: ${err.message}`);
    }
  };

  const isExpired = (validTo?: string) => {
    if (!validTo) return false;
    return new Date(validTo) < new Date();
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Header & Reindex Button */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-stone-200">
        <div>
          <h1 className="text-2xl font-bold text-stone-900 tracking-tight">Approved Brand Sources</h1>
          <p className="text-xs text-stone-500 mt-1">
            Ground-truth repository of voice guidelines, certified facts, terminology, and assets.
          </p>
        </div>

        <button
          onClick={handleReindex}
          disabled={reindexing}
          className="inline-flex items-center gap-2 px-4 py-2 bg-stone-900 hover:bg-stone-800 text-white rounded-lg text-xs font-semibold shadow-sm transition-all disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 text-amber-400 ${reindexing ? "animate-spin" : ""}`} />
          {reindexing ? "Indexing ChromaDB..." : "Re-index Chroma Vector Store"}
        </button>
      </div>

      {reindexMsg && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs font-medium">
          {reindexMsg}
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-stone-200 gap-2">
        {[
          { id: "guidelines", label: `Guidelines (${guidelines.length})`, icon: BookOpen },
          { id: "facts", label: `Approved Facts (${facts.length})`, icon: CheckCircle },
          { id: "terms", label: `Terminology (${terms.length})`, icon: Layers },
          { id: "assets", label: `Brand Assets (${assets.length})`, icon: ImageIcon },
        ].map((t) => {
          const Icon = t.icon;
          const active = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id as any)}
              className={`flex items-center gap-1.5 py-3 px-4 text-xs font-semibold border-b-2 transition-colors ${
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
      {activeTab === "guidelines" && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-sm font-bold text-stone-800">Brand Voice & Claims Policy Docs</h2>
            <button
              onClick={() => setShowAddGuideline(!showAddGuideline)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-stone-900 text-white rounded-lg text-xs font-medium"
            >
              <Plus className="w-3.5 h-3.5 text-amber-400" />
              Add Guideline Document
            </button>
          </div>

          {showAddGuideline && (
            <form onSubmit={handleCreateGuideline} className="bg-white border border-stone-200 rounded-xl p-5 shadow-sm space-y-4">
              <h3 className="font-bold text-xs uppercase tracking-wider text-stone-700">Import Guideline Document</h3>
              <p className="text-xs text-stone-500">
                Paste markdown or text with headers (e.g. <code>## Tone and Voice</code>). The system will automatically split it into reviewable clauses for citation.
              </p>
              <div>
                <label className="block text-xs font-semibold text-stone-700 mb-1">Document Title</label>
                <input
                  type="text"
                  placeholder="e.g. Aurelia Foods Brand Guidelines"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  required
                  className="w-full px-3 py-2 text-xs border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-stone-700 mb-1">Document Content</label>
                <textarea
                  rows={6}
                  placeholder="Paste guideline text..."
                  value={newText}
                  onChange={(e) => setNewText(e.target.value)}
                  required
                  className="w-full p-3 text-xs border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
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
                  className="px-4 py-1.5 bg-stone-900 text-white rounded-lg text-xs font-semibold"
                >
                  Save & Auto-Split Clauses
                </button>
              </div>
            </form>
          )}

          <div className="space-y-4">
            {guidelines.map((doc) => (
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

      {/* Tab 2: Approved Facts */}
      {activeTab === "facts" && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-sm font-bold text-stone-800">Approved Truth Ledger ({facts.length} Facts)</h2>
              <p className="text-[11px] text-stone-500">Includes active facts and expired entries for testing outdated info detection.</p>
            </div>
            <button
              onClick={() => setShowAddFact(!showAddFact)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-stone-900 text-white rounded-lg text-xs font-medium"
            >
              <Plus className="w-3.5 h-3.5 text-amber-400" />
              Add Fact
            </button>
          </div>

          {showAddFact && (
            <form onSubmit={handleCreateFact} className="bg-white border border-stone-200 rounded-xl p-5 shadow-sm space-y-4">
              <h3 className="font-bold text-xs uppercase tracking-wider text-stone-700">Add Approved Fact</h3>
              <div>
                <label className="block text-xs font-semibold text-stone-700 mb-1">Statement</label>
                <input
                  type="text"
                  placeholder="e.g. As of 2024, our Portland kitchen operates on 85% certified solar energy."
                  value={newStatement}
                  onChange={(e) => setNewStatement(e.target.value)}
                  required
                  className="w-full px-3 py-2 text-xs border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-stone-700 mb-1">Source Note / Certificate #</label>
                  <input
                    type="text"
                    placeholder="e.g. 2024 Green Energy Audit"
                    value={newNote}
                    onChange={(e) => setNewNote(e.target.value)}
                    className="w-full px-3 py-2 text-xs border border-stone-300 rounded-lg"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-stone-700 mb-1">Valid To Date (Optional Expiry)</label>
                  <input
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
                  className="px-4 py-1.5 bg-stone-900 text-white rounded-lg text-xs font-semibold"
                >
                  Add Fact
                </button>
              </div>
            </form>
          )}

          <div className="bg-white border border-stone-200 rounded-xl divide-y divide-stone-100 shadow-sm overflow-hidden">
            {facts.map((fact) => {
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
      {activeTab === "terms" && (
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-sm font-bold text-stone-800">Approved Terminology Registry</h2>
            <button
              onClick={() => setShowAddTerm(!showAddTerm)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-stone-900 text-white rounded-lg text-xs font-medium"
            >
              <Plus className="w-3.5 h-3.5 text-amber-400" />
              Add Term
            </button>
          </div>

          {showAddTerm && (
            <form onSubmit={handleCreateTerm} className="bg-white border border-stone-200 rounded-xl p-5 shadow-sm space-y-4">
              <h3 className="font-bold text-xs uppercase tracking-wider text-stone-700">Add Terminology Rule</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-stone-700 mb-1">Preferred Term</label>
                  <input
                    type="text"
                    placeholder="e.g. patrons"
                    value={newPreferred}
                    onChange={(e) => setNewPreferred(e.target.value)}
                    required
                    className="w-full px-3 py-2 text-xs border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-stone-700 mb-1">Avoided Terms (Comma-separated)</label>
                  <input
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
                  className="px-4 py-1.5 bg-stone-900 text-white rounded-lg text-xs font-semibold"
                >
                  Save Term
                </button>
              </div>
            </form>
          )}

          <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-4">
            {terms.map((t) => (
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
      {activeTab === "assets" && (
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-stone-800">Approved Brand Assets ({assets.length})</h2>
          <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-4">
            {assets.map((asset) => (
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
