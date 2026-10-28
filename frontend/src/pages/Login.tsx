import React, { useState } from "react";
import { Shield } from "lucide-react";
import { api, setToken } from "../api";
import { User } from "../types";

interface LoginProps {
  onLoginSuccess: (user: User) => void;
  demoMode: boolean;
}

const DEMO_ACCOUNTS: Array<{ role: string; email: string; password: string }> = [
  { role: "Admin", email: "admin@nexora.dev", password: "AdminDemo2026!" },
  { role: "Manager", email: "manager@nexora.dev", password: "ManagerDemo2026!" },
  { role: "Reviewer", email: "reviewer@nexora.dev", password: "ReviewerDemo2026!" },
  { role: "Creator", email: "creator@nexora.dev", password: "CreatorDemo2026!" },
];

export const Login: React.FC<LoginProps> = ({ onLoginSuccess, demoMode }) => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const signIn = async (loginEmail: string, loginPassword: string) => {
    setLoading(true);
    setError(null);

    try {
      const res = await api.login(loginEmail, loginPassword);
      setToken(res.access_token);
      const user = await api.getMe();
      onLoginSuccess(user);
    } catch (err: any) {
      setError(err.message || "Login failed. Please verify credentials.");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await signIn(email, password);
  };

  const handleDemoSignIn = async (account: (typeof DEMO_ACCOUNTS)[number]) => {
    setEmail(account.email);
    setPassword(account.password);
    await signIn(account.email, account.password);
  };

  return (
    <div className="login-page min-h-[calc(100vh-4rem)] flex items-center justify-center p-4">
      <div className={`login-card w-full bg-white border border-stone-200 rounded-2xl shadow-xl p-6 sm:p-8 ${demoMode ? "max-w-4xl" : "max-w-md"}`}>
        <div className={`grid grid-cols-1 gap-8 ${demoMode ? "md:grid-cols-2" : ""}`}>
          <div className="flex flex-col justify-center">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 rounded-lg bg-stone-900 text-amber-400 flex items-center justify-center shadow">
              <Shield className="w-4 h-4" />
            </div>
            <h1 className="text-xl font-bold text-stone-900">BrandGuard Sign In</h1>
          </div>
          <p className="text-sm text-stone-500 mb-6">
            Review campaign content against approved brand standards before publishing.
          </p>

          {error && (
            <div role="alert" className="mb-4 p-3 bg-rose-50 border border-rose-200 rounded-lg text-sm text-rose-700">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="login-email" className="block text-sm font-semibold text-stone-700 mb-1">Email address</label>
              <input
                id="login-email"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-3 py-3 text-base border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
              />
            </div>

            <div>
              <label htmlFor="login-password" className="block text-sm font-semibold text-stone-700 mb-1">Password</label>
              <input
                id="login-password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-3 py-3 text-base border border-stone-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="ui-button ui-button--primary w-full"
              aria-live="polite"
            >
              {loading ? "Signing in..." : "Sign In to BrandGuard"}
            </button>
          </form>

          <div className="mt-6 pt-4 border-t border-stone-100 text-[11px] text-stone-400 text-center">
            Sign in with the account provided by your workspace administrator.
          </div>
          </div>

          {demoMode && (
            <section aria-labelledby="demo-accounts-title" className="login-demo rounded-xl border border-amber-200 bg-amber-50/70 p-5">
              <div className="mb-4">
                <h2 id="demo-accounts-title" className="text-base font-bold text-stone-900">Demo accounts</h2>
                <p className="mt-1 text-xs leading-relaxed text-stone-600">
                  Use these throwaway accounts to explore each role. Each button fills the login form and signs in.
                </p>
              </div>
              <div className="space-y-3">
                {DEMO_ACCOUNTS.map((account) => (
                    <div key={account.role} className="login-demo__account rounded-lg border border-stone-200 bg-white p-3">
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <h3 className="text-sm font-bold text-stone-900">{account.role}</h3>
                      <button
                        type="button"
                        disabled={loading}
                        onClick={() => void handleDemoSignIn(account)}
                        className="ui-button ui-button--quiet shrink-0"
                        aria-label={`Fill / Sign in as ${account.role}`}
                      >
                        {loading ? "Signing in..." : "Fill / Sign in"}
                      </button>
                    </div>
                    <dl className="grid grid-cols-[4.5rem_1fr] gap-x-2 gap-y-1 text-[11px]">
                      <dt className="font-semibold text-stone-500">Username</dt>
                      <dd className="break-all font-mono text-stone-700">{account.email}</dd>
                      <dt className="font-semibold text-stone-500">Password</dt>
                      <dd className="break-all font-mono text-stone-700">{account.password}</dd>
                    </dl>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
};
