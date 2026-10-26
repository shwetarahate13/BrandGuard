import React, { useState } from "react";
import { Shield } from "lucide-react";
import { api, setToken } from "../api";
import { User } from "../types";

interface LoginProps {
  onLoginSuccess: (user: User) => void;
}

export const Login: React.FC<LoginProps> = ({ onLoginSuccess }) => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white border border-stone-200 rounded-2xl shadow-xl overflow-hidden p-8">
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
      </div>
    </div>
  );
};
