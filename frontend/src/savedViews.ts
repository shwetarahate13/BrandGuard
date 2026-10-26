export type SavedViewRole = "creator" | "manager";

export interface DashboardSavedView {
  id: string;
  name: string;
  search: string;
  statusFilter: string;
  updatedAt: string;
}

interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

const storageKey = (userId: string, role: SavedViewRole) =>
  `brandguard:saved-views:${role}:${encodeURIComponent(userId)}`;

export function readSavedViews(
  userId: string,
  role: SavedViewRole,
  storage: StorageLike = window.localStorage,
): DashboardSavedView[] {
  try {
    const parsed: unknown = JSON.parse(storage.getItem(storageKey(userId, role)) || "[]");
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item): item is DashboardSavedView =>
      !!item &&
      typeof item.id === "string" &&
      typeof item.name === "string" &&
      typeof item.search === "string" &&
      typeof item.statusFilter === "string" &&
      typeof item.updatedAt === "string",
    );
  } catch {
    return [];
  }
}

export function saveDashboardView(
  userId: string,
  role: SavedViewRole,
  values: Pick<DashboardSavedView, "name" | "search" | "statusFilter">,
  storage: StorageLike = window.localStorage,
): DashboardSavedView[] {
  const name = values.name.trim();
  if (!name) throw new Error("Enter a name for this saved view.");
  if (name.length > 60) throw new Error("Saved view names must be 60 characters or fewer.");

  const views = readSavedViews(userId, role, storage);
  const existing = views.find((view) => view.name.toLocaleLowerCase() === name.toLocaleLowerCase());
  const saved: DashboardSavedView = {
    id: existing?.id || `view-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    name,
    search: values.search,
    statusFilter: values.statusFilter,
    updatedAt: new Date().toISOString(),
  };
  const next = existing
    ? views.map((view) => view.id === existing.id ? saved : view)
    : [...views, saved];
  storage.setItem(storageKey(userId, role), JSON.stringify(next));
  return next;
}

export function deleteDashboardView(
  userId: string,
  role: SavedViewRole,
  id: string,
  storage: StorageLike = window.localStorage,
): DashboardSavedView[] {
  const next = readSavedViews(userId, role, storage).filter((view) => view.id !== id);
  storage.setItem(storageKey(userId, role), JSON.stringify(next));
  return next;
}
