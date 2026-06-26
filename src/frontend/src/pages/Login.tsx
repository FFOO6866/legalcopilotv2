import { useState, type FormEvent } from "react";
import { useNavigate, Navigate } from "react-router-dom";
import { Mail, Lock, AlertCircle } from "lucide-react";
import { useAuthStore, useIsAuthenticated } from "@/stores/authStore";
import { ROUTES, APP_NAME } from "@/utils/constants";
import Button from "@/components/common/Button";

export default function Login() {
  const navigate = useNavigate();
  const isAuthenticated = useIsAuthenticated();
  const login = useAuthStore((state) => state.login);
  const isLoading = useAuthStore((state) => state.isLoading);
  const error = useAuthStore((state) => state.error);
  const clearError = useAuthStore((state) => state.clearError);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  if (isAuthenticated) {
    return <Navigate to={ROUTES.DASHBOARD} replace />;
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    clearError();
    try {
      await login(email, password);
      navigate(ROUTES.DASHBOARD, { replace: true });
    } catch {
      // Error is already set in the store
    }
  }

  return (
    <div
      className="min-h-dvh flex items-center justify-center px-4 py-12 bg-cover bg-center bg-no-repeat"
      style={{ backgroundImage: "url('/shophouse-bg.png')" }}
    >
      <div className="w-full max-w-md">
        <div className="rounded-2xl bg-white/95 backdrop-blur-sm shadow-2xl p-8">
          <div className="text-center mb-8">
            <img src="/revlaw-logo.png" alt="REV LAW" className="h-12 mx-auto mb-3" />
            <p className="text-sm text-gray-500 uppercase tracking-wider">{APP_NAME}</p>
            <h2 className="text-xl font-semibold text-gray-900 mt-4">
              Sign in to your account
            </h2>
          </div>

          {error && (
            <div className="flex items-start gap-2.5 rounded-lg bg-red-50 border border-red-200 px-4 py-3 mb-5">
              <AlertCircle size={16} className="text-red-500 shrink-0 mt-0.5" />
              <p className="text-sm text-red-600">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="login-email" className="text-sm font-medium text-gray-700">
                Email
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none text-gray-400">
                  <Mail size={16} />
                </div>
                <input
                  id="login-email"
                  type="email"
                  required
                  autoComplete="email"
                  placeholder="you@lawfirm.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 bg-white pl-9 pr-3 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                />
              </div>
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="login-password" className="text-sm font-medium text-gray-700">
                Password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none text-gray-400">
                  <Lock size={16} />
                </div>
                <input
                  id="login-password"
                  type="password"
                  required
                  autoComplete="current-password"
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 bg-white pl-9 pr-3 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                />
              </div>
            </div>

            <Button
              type="submit"
              variant="primary"
              size="lg"
              isLoading={isLoading}
              className="w-full mt-2"
            >
              Sign in
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
