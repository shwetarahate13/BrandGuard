import React, { useEffect, useState } from "react";
import { Bookmark, Trash2 } from "lucide-react";
import { useToast } from "./Toast";
import {
  DashboardSavedView,
  deleteDashboardView,
  readSavedViews,
  saveDashboardView,
  SavedViewRole,
} from "../savedViews";

interface SavedViewsProps {
  userId: string;
  role: SavedViewRole;
  search: string;
  setSearch: (value: string) => void;
  statusFilter: string;
  setStatusFilter: (value: string) => void;
}

export const SavedViews: React.FC<SavedViewsProps> = ({
  userId,
  role,
  search,
  setSearch,
  statusFilter,
  setStatusFilter,
}) => {
  const [views, setViews] = useState<DashboardSavedView[]>(() => readSavedViews(userId, role));
  const [selectedId, setSelectedId] = useState("");
  const [name, setName] = useState("");
  const { showToast } = useToast();

  useEffect(() => {
    setViews(readSavedViews(userId, role));
    setSelectedId("");
    setName("");
  }, [userId, role]);

  const applyView = (id: string) => {
    setSelectedId(id);
    const view = views.find((item) => item.id === id);
    if (!view) return;
    setName(view.name);
    setSearch(view.search);
    setStatusFilter(view.statusFilter);
  };

  const saveView = () => {
    try {
      const next = saveDashboardView(userId, role, { name, search, statusFilter });
      const saved = next.find((view) => view.name.toLocaleLowerCase() === name.trim().toLocaleLowerCase());
      setViews(next);
      if (saved) setSelectedId(saved.id);
      showToast("Saved view updated", "success");
    } catch (error) {
      showToast(error instanceof Error ? error.message : "Could not save this view", "error");
    }
  };

  const removeView = () => {
    if (!selectedId) return;
    setViews(deleteDashboardView(userId, role, selectedId));
    setSelectedId("");
    setName("");
    showToast("Saved view deleted", "success");
  };

  return (
    <div className="flex flex-wrap items-center gap-2 pt-3" aria-label="Saved views">
      <Bookmark className="h-3.5 w-3.5 text-stone-500" aria-hidden="true" />
      <label className="sr-only" htmlFor={`${role}-saved-view`}>Saved views</label>
      <select
        id={`${role}-saved-view`}
        value={selectedId}
        onChange={(event) => applyView(event.target.value)}
        className="text-xs border border-stone-300 rounded-lg px-2 py-1.5 bg-white text-stone-700"
      >
        <option value="">Saved views…</option>
        {views.map((view) => <option key={view.id} value={view.id}>{view.name}</option>)}
      </select>
      <input
        aria-label="Saved view name"
        type="text"
        maxLength={60}
        placeholder="Name current search and filters"
        value={name}
        onChange={(event) => setName(event.target.value)}
        className="text-xs border border-stone-300 rounded-lg px-2.5 py-1.5 w-52"
      />
      <button
        type="button"
        onClick={saveView}
        className="text-xs font-semibold rounded-lg px-3 py-1.5 bg-stone-900 hover:bg-stone-800 text-white"
      >Save view</button>
      <button
        type="button"
        onClick={removeView}
        disabled={!selectedId}
        aria-label="Delete selected saved view"
        className="inline-flex items-center gap-1 text-xs font-semibold rounded-lg px-2.5 py-1.5 border border-stone-300 text-stone-600 hover:bg-stone-50 disabled:opacity-40 disabled:cursor-not-allowed"
      ><Trash2 className="h-3.5 w-3.5" />Delete</button>
      <span className="sr-only">Saved views are stored in this browser for your account.</span>
    </div>
  );
};
