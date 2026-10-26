import { UserRole } from "./types";

export interface OnboardingStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

const STORAGE_PREFIX = "brandguard:onboarding-seen:";

export function onboardingKey(userId: string, role: UserRole): string {
  return `${STORAGE_PREFIX}${encodeURIComponent(userId)}:${role}`;
}

export function hasSeenOnboarding(
  userId: string,
  role: UserRole,
  storage?: OnboardingStorage,
): boolean {
  try {
    const target = storage ?? (typeof window === "undefined" ? undefined : window.localStorage);
    return target?.getItem(onboardingKey(userId, role)) === "true";
  } catch {
    return false;
  }
}

export function markOnboardingSeen(
  userId: string,
  role: UserRole,
  storage?: OnboardingStorage,
): void {
  try {
    const target = storage ?? (typeof window === "undefined" ? undefined : window.localStorage);
    target?.setItem(onboardingKey(userId, role), "true");
  } catch {
    // Keep the tips usable even when browser storage is unavailable.
  }
}
