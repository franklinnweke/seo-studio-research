"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import type { Session, User } from "@supabase/supabase-js";

import { isSupabaseConfigured, supabase } from "@/lib/supabase";

type AuthContextValue = {
  user: User | null;
  session: Session | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const publicRoutes = new Set(["/login"]);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(Boolean(supabase));

  useEffect(() => {
    if (!supabase) {
      return;
    }

    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
      setLoading(false);
    });

    return () => subscription.unsubscribe();
  }, []);

  useEffect(() => {
    if (loading || !isSupabaseConfigured) return;
    const isPublicRoute = publicRoutes.has(pathname);

    if (!session && !isPublicRoute) {
      router.replace("/login");
      return;
    }

    if (session && isPublicRoute) {
      router.replace("/");
    }
  }, [loading, pathname, router, session]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user: session?.user ?? null,
      session,
      loading,
      async signIn(email: string, password: string) {
        if (!supabase) throw new Error("Supabase is not configured.");
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
      },
      async signOut() {
        if (!supabase) return;
        await supabase.auth.signOut();
        router.replace("/login");
      },
    }),
    [loading, router, session],
  );

  if (!isSupabaseConfigured) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f6f7f9] px-5">
        <div className="w-full max-w-md rounded-lg border border-[#dfe3e8] bg-white p-6">
          <h1 className="text-lg font-semibold text-[#151923]">Supabase env required</h1>
          <p className="mt-2 text-sm leading-6 text-[#667085]">
            Add NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY to
            frontend/.env.local, then restart the frontend server.
          </p>
        </div>
      </div>
    );
  }

  if (loading || (!session && !publicRoutes.has(pathname))) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f6f7f9] text-sm text-[#667085]">
        Loading session...
      </div>
    );
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return value;
}
