"use client";

import { FormEvent, useState } from "react";
import { Loader2, LogIn, Sparkles } from "lucide-react";

import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      await signIn(email.trim(), password);
    } catch (signInError) {
      setError(signInError instanceof Error ? signInError.message : "Unable to sign in.");
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#f6f7f9] px-5">
      <section className="w-full max-w-md rounded-lg border border-[#dfe3e8] bg-white">
        <div className="border-b border-[#dfe3e8] px-6 py-5">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#1d4ed8] text-white">
              <Sparkles aria-hidden="true" size={20} />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-[#151923]">Sign in to seo-studio</h1>
              <p className="mt-1 text-sm text-[#667085]">Use your Supabase account credentials.</p>
            </div>
          </div>
        </div>

        <form onSubmit={onSubmit} className="space-y-4 p-6">
          <label className="block space-y-2">
            <span className="text-sm font-medium text-[#151923]">Email</span>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              required
              className="h-10 w-full rounded-md border border-[#dfe3e8] bg-white px-3 text-sm"
            />
          </label>

          <label className="block space-y-2">
            <span className="text-sm font-medium text-[#151923]">Password</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              required
              className="h-10 w-full rounded-md border border-[#dfe3e8] bg-white px-3 text-sm"
            />
          </label>

          {error ? (
            <div className="rounded-md border border-[#f2b8b5] bg-[#fff5f5] p-3 text-sm text-[#b42318]">
              {error}
            </div>
          ) : null}

          <button
            type="submit"
            disabled={loading || !email.trim() || !password}
            className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-[#1d4ed8] px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-[#98a2b3]"
          >
            {loading ? <Loader2 aria-hidden="true" className="animate-spin" size={16} /> : <LogIn aria-hidden="true" size={16} />}
            Sign in
          </button>
        </form>
      </section>
    </main>
  );
}
