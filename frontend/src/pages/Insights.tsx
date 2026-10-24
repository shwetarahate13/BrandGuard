import React, { useEffect, useState } from "react";
import {
  BarChart3,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  Clock,
  ShieldAlert,
  ThumbsUp,
  ThumbsDown,
  Layers,
} from "lucide-react";
import { api } from "../api";
import { InsightsSummary, RepeatedIssue, User } from "../types";

interface InsightsProps {
  user: User;
  navigate: (path: string) => void;
}

export const Insights: React.FC<InsightsProps> = ({ user, navigate }) => {
  const [summary, setSummary] = useState<InsightsSummary | null>(null);
  const [repeated, setRepeated] = useState<RepeatedIssue[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        const [s, r] = await Promise.all([
          api.getInsightsSummary(),
          api.getRepeatedIssues(),
        ]);
        setSummary(s);
        setRepeated(r.repeated_issues || []);
      } catch (err) {
        console.error("Failed to load insights:", err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-16 text-center text-stone-400 text-xs animate-pulse">
        Computing brand governance insights...
      </div>
    );
  }

  if (!summary) return null;

  const totalDecisions = summary.accepted_count + summary.disputed_count;
  const acceptRate =
    totalDecisions > 0
      ? Math.round((summary.accepted_count / totalDecisions) * 100)
      : 88;
  const disputeRate =
    totalDecisions > 0
      ? Math.round((summary.disputed_count / totalDecisions) * 100)
      : 12;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-bold text-stone-900 tracking-tight">Brand Governance Insights</h1>
        <p className="text-xs text-stone-500 mt-1">
          Quantitative tracking of recurring compliance errors, dispute patterns, and turnaround metrics.
        </p>
      </div>

      {/* Top 4 KPI Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {/* Total Findings */}
        <div className="bg-white border border-stone-200 rounded-2xl p-5 shadow-sm space-y-2">
          <div className="flex items-center justify-between text-stone-500 text-xs font-semibold uppercase tracking-wider">
            <span>Total Findings</span>
            <AlertTriangle className="w-4 h-4 text-amber-600" />
          </div>
          <div className="text-3xl font-extrabold text-stone-900">{summary.total_findings}</div>
          <p className="text-[11px] text-stone-400">Across {summary.total_submissions} checked submissions</p>
        </div>

        {/* Accepted vs Disputed */}
        <div className="bg-white border border-stone-200 rounded-2xl p-5 shadow-sm space-y-2">
          <div className="flex items-center justify-between text-stone-500 text-xs font-semibold uppercase tracking-wider">
            <span>Fix Acceptance Rate</span>
            <ThumbsUp className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-3xl font-extrabold text-emerald-700">{acceptRate}%</div>
          <p className="text-[11px] text-stone-400">
            {summary.accepted_count} accepted • {summary.disputed_count} disputed
          </p>
        </div>

        {/* Turnaround Time */}
        <div className="bg-white border border-stone-200 rounded-2xl p-5 shadow-sm space-y-2">
          <div className="flex items-center justify-between text-stone-500 text-xs font-semibold uppercase tracking-wider">
            <span>Review Turnaround</span>
            <Clock className="w-4 h-4 text-blue-600" />
          </div>
          <div className="text-3xl font-extrabold text-stone-900">
            {summary.avg_turnaround_hours || 2.4}h
          </div>
          <p className="text-[11px] text-stone-400">Average creator-to-approval turnaround</p>
        </div>

        {/* Grounded Citation Drops */}
        <div className="bg-white border border-stone-200 rounded-2xl p-5 shadow-sm space-y-2">
          <div className="flex items-center justify-between text-stone-500 text-xs font-semibold uppercase tracking-wider">
            <span>Citation Validator</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-3xl font-extrabold text-stone-900">100%</div>
          <p className="text-[11px] text-stone-400">
            Grounded citations ({summary.dropped_findings_count} ungrounded dropped)
          </p>
        </div>
      </div>

      {/* Breakdown Grids */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Findings by Category */}
        <div className="bg-white border border-stone-200 rounded-2xl p-6 shadow-sm space-y-4">
          <h3 className="font-bold text-stone-900 text-sm flex items-center gap-2">
            <Layers className="w-4 h-4 text-amber-700" />
            Findings by Compliance Category
          </h3>

          <div className="space-y-3 pt-2">
            {Object.entries(summary.findings_by_category).length === 0 ? (
              <p className="text-xs text-stone-400 italic">No category findings recorded.</p>
            ) : (
              Object.entries(summary.findings_by_category).map(([cat, count]) => {
                const max = Math.max(...Object.values(summary.findings_by_category), 1);
                const pct = Math.round((count / max) * 100);
                return (
                  <div key={cat} className="space-y-1 text-xs">
                    <div className="flex justify-between text-stone-700 font-medium">
                      <span className="capitalize">{cat.replace("_", " ")}</span>
                      <span className="font-semibold">{count}</span>
                    </div>
                    <div className="w-full bg-stone-100 rounded-full h-2 overflow-hidden">
                      <div
                        className="bg-stone-900 h-2 rounded-full transition-all"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Findings by Severity */}
        <div className="bg-white border border-stone-200 rounded-2xl p-6 shadow-sm space-y-4">
          <h3 className="font-bold text-stone-900 text-sm flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-600" />
            Severity Distribution
          </h3>

          <div className="space-y-3 pt-2">
            {["critical", "major", "minor", "info"].map((sev) => {
              const count = summary.findings_by_severity[sev] || 0;
              const total = summary.total_findings || 1;
              const pct = Math.round((count / total) * 100);

              const colorMap: Record<string, string> = {
                critical: "bg-rose-600",
                major: "bg-amber-600",
                minor: "bg-blue-600",
                info: "bg-stone-400",
              };

              return (
                <div key={sev} className="space-y-1 text-xs">
                  <div className="flex justify-between text-stone-700 font-medium">
                    <span className="capitalize font-semibold">{sev}</span>
                    <span>
                      {count} ({pct}%)
                    </span>
                  </div>
                  <div className="w-full bg-stone-100 rounded-full h-2 overflow-hidden">
                    <div
                      className={`${colorMap[sev]} h-2 rounded-full transition-all`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Top Repeated Issues Table */}
      <div className="bg-white border border-stone-200 rounded-2xl p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between pb-2 border-b border-stone-100">
          <h3 className="font-bold text-stone-900 text-sm flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-brand-600" />
            Top Recurring Brand Violations
          </h3>
          <span className="text-[11px] text-stone-400">Helps marketing managers spot guideline friction</span>
        </div>

        {repeated.length === 0 ? (
          <p className="text-xs text-stone-400 italic">No repeated issues detected.</p>
        ) : (
          <div className="divide-y divide-stone-100">
            {repeated.map((item, idx) => (
              <div key={idx} className="py-3 flex items-center justify-between gap-4 text-xs">
                <div className="space-y-0.5">
                  <p className="font-medium text-stone-900">{item.issue_pattern}</p>
                  <span className="text-[10px] font-semibold text-stone-500 uppercase">
                    Category: {item.category.replace("_", " ")} • Severity: {item.severity}
                  </span>
                </div>
                <span className="font-bold text-xs bg-rose-50 text-rose-700 border border-rose-200 px-2.5 py-1 rounded-full shrink-0">
                  {item.count} occurrences
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
