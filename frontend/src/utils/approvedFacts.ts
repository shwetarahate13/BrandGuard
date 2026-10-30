import { ApprovedFact } from "../types";

const valueKey = (value: string) => {
  const numeric = value.match(/\d[\d,]*(?:\.\d+)?/);
  if (!numeric) return value.trim().toLocaleLowerCase();
  const amount = Number(numeric[0].replace(/,/g, ""));
  if (!Number.isFinite(amount)) return value.trim().toLocaleLowerCase();
  const symbol = value.match(/[$€£]/)?.[0] || "";
  const percent = /%|\bpercent\b/i.test(value) ? "%" : "";
  return `${symbol}${amount}|${percent}`;
};

export const findActiveFactConflicts = (facts: ApprovedFact[], now = Date.now()) => {
  const active = facts.filter((fact): fact is ApprovedFact & { subject: string; value: string } =>
    Boolean(fact.subject?.trim() && fact.value?.trim())
    && (!fact.valid_from || new Date(fact.valid_from).getTime() <= now)
    && (!fact.valid_to || new Date(fact.valid_to).getTime() >= now)
  );
  const grouped = active.reduce<Record<string, ApprovedFact[]>>((groups, fact) => {
    const key = fact.subject.trim().toLocaleLowerCase();
    groups[key] = [...(groups[key] || []), fact];
    return groups;
  }, {});
  return Object.values(grouped).filter((group) => new Set(group.map((fact) =>
    `${valueKey(fact.value)}|${fact.unit?.trim().toLocaleLowerCase() || ""}`
  )).size > 1);
};
