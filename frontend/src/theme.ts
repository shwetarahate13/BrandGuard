export interface ThemeStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export interface ThemeRoot {
  classList: { toggle(name: string, force?: boolean): unknown };
}

const STORAGE_KEY = "brandguard:dark-mode";

function getStorage(storage?: ThemeStorage): ThemeStorage | undefined {
  if (storage) return storage;
  return typeof window === "undefined" ? undefined : window.localStorage;
}

export function readDarkMode(storage?: ThemeStorage): boolean {
  try {
    return getStorage(storage)?.getItem(STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

export function saveDarkMode(enabled: boolean, storage?: ThemeStorage): void {
  try {
    getStorage(storage)?.setItem(STORAGE_KEY, enabled ? "true" : "false");
  } catch {
    // Private browsing or disabled storage should not prevent theme switching.
  }
}

export function applyDarkMode(enabled: boolean, root?: ThemeRoot): void {
  const target = root || (typeof document === "undefined" ? undefined : document.documentElement);
  target?.classList.toggle("dark", enabled);
}
