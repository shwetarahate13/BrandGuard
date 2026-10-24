import React, { useState } from "react";
import { Shield, Sparkles, UserCheck, ShieldAlert, CheckCircle2 } from "lucide-react";
import { api, setToken } from "../api";
import { User } from "../types";

interface LoginProps {
  onLoginSuccess: (user: User) => void;
}

export const Login: React.FC<LoginProps> = ({ onLoginSuccess }) => {
  const [email, setEmail] = useState("creator@nexora.dev");
  const [password, setPassword] = useState("Creator123!");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const demoAccounts = [
    {
      role: "Creator",
      name: "Janvi Thakre",
      email: "creator@nexora.dev",
      password: "Creator123!",
      desc: "Drafts and submits content, reviews findings, accepts/disputes diff fixes.",
      badgeColor: "bg-blue-50 text-blue-700 border-blue-200",
    },
    {
      role: "Brand Manager",
      name: "Shweta Rahate",
      email: "manager@nexora.dev",
      password: "Manager123!",
      desc: "Full overview across all teams, approves copy, tracks compliance trends.",
      badgeColor: "bg-purple-50 text-purple-700 border-purple-200",
    },
    {
      role: "Reviewer",
      name: "Elena Rostova",
      email: "reviewer@nexora.dev",
      password: "Reviewer123!",
      desc: "Verifies claims and legal wording, final sign-off on sensitive copy.",
      badgeColor: "bg-emerald-50 text-emerald-700 border-emerald-200",
    },
    {
      role: "Admin",
      name: "Admin Nexora",
      email: "admin@nexora.dev",
      password: "Admin123!",
      desc: "Manages guidelines, approved facts, terminology registry, and vector indexes.",
      badgeColor: "bg-stone-100 text-stone-700 border-stone-300",
    },
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await api.login(email, password);
      setToken(res.access_token);
      const user = await api.getMe();
      onLoginSuccess(user);
    } catch (err: any) {
      setError(err.message || "Login failed. Please verify credentials.");
    } finally {
      setLoading(false);
    }
  };

  const handleQuickFill = (acc: (typeof demoAccounts)[0]) => {
    setEmail(acc.email);
    setPassword(acc.password);
    setError(null);
  };

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center p-4">
      <div className="max-w-4xl w-full grid md:grid-cols-2 gap-8 bg-white border border-stone-200 rounded-2xl shadow-xl overflow-hidden p-8">
        {/* Left: Login Form */}
        <div className="flex flex-col justify-center">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 rounded-lg bg-stone-900 text-amber-400 flex items-center justify-center shadow">
              <Shield className="w-4 h-4" />
            </div>
            <h1 className="text-xl font-bold text-stone-900">BrandGuard Sign In</h1>
          </div>
          <p className="text-xs text-stone-500 mb-6">
            Pre-publication brand governance platform • Team Nexora
          </p>

          {error && (
            <div className="mb-4 p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-700">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-stone-700 mb-1">Email Address</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-stone-700 mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-3 py-2 text-sm border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 bg-stone-900 hover:bg-stone-800 text-white rounded-lg text-sm font-semibold shadow transition-all disabled:opacity-50"
            >
              {loading ? "Signing in..." : "Sign In to BrandGuard"}
            </button>
          </form>

          <div className="mt-6 pt-4 border-t border-stone-100 text-[11px] text-stone-400 text-center">
            Session secured with JWT + bcrypt password hashing.
          </div>
        </div>

        {/* Right: Judge Demo Quick-Fill Buttons */}
        <div className="bg-stone-50 border border-stone-200/80 rounded-xl p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-1.5 mb-2 text-amber-800">
              <Sparkles className="w-4 h-4 text-amber-600" />
              <h2 className="text-xs font-bold uppercase tracking-wider">Judge Demo Quick Fill</h2>
            </div>
            <p className="text-xs text-stone-600 mb-4">
              Select any role to test role-based permissions and governance workflows:
            </p>

            <div className="space-y-2.5">
              {demoAccounts.map((acc) => (
                <button
                  key={acc.email}
                  type="button"
                  onClick={() => handleQuickFill(acc)}
                  className={`w-full text-left p-3 rounded-lg border transition-all text-xs hover:border-amber-400 hover:bg-white ${
                    email === acc.email
                      ? "bg-white border-amber-500 ring-2 ring-amber-100"
                      : "bg-stone-100/60 border-stone-200"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-semibold text-stone-900">{acc.name}</span>
                    <span className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border ${acc.badgeColor}`}>
                      {acc.role}
                    </span>
                  </div>
                  <p className="text-[11px] text-stone-500 leading-snug">{acc.desc}</p>
                </button>
              ))}
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-stone-200 text-[11px] text-stone-500 flex items-center gap-2">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
            <span>Click any role above and click <strong>Sign In</strong> to explore.</span>
          </div>
        </div>
      </div>
    </div>
  );
};
