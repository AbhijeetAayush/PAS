import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { Session, SupabaseClient } from "@supabase/supabase-js";
import { createClient } from "@supabase/supabase-js";
import { api } from "./api";

type AuthValue = {
  ready: boolean;
  session: Session | null;
  client: SupabaseClient | null;
  error: string;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<string>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [client, setClient] = useState<SupabaseClient | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    api<{ supabaseUrl: string; supabaseAnonKey: string }>("/config/public")
      .then((config) => {
        if (!active) return;
        const supabase = createClient(config.supabaseUrl, config.supabaseAnonKey);
        setClient(supabase);
        return supabase.auth.getSession().then(({ data }) => {
          if (!active) return;
          setSession(data.session);
          supabase.auth.onAuthStateChange((_event, next) => setSession(next));
        });
      })
      .catch((err: Error) => {
        if (active) setError(err.message);
      })
      .finally(() => {
        if (active) setReady(true);
      });
    return () => {
      active = false;
    };
  }, []);

  const value = useMemo<AuthValue>(
    () => ({
      ready,
      session,
      client,
      error,
      async signIn(email, password) {
        if (!client) throw new Error("Login is not ready");
        const { error: authError } = await client.auth.signInWithPassword({ email, password });
        if (authError) throw new Error(authError.message);
      },
      async signUp(email, password) {
        if (!client) throw new Error("Login is not ready");
        const { data, error: authError } = await client.auth.signUp({ email, password });
        if (authError) throw new Error(authError.message);
        return data.session ? "" : "Check your email to confirm the account, then sign in.";
      },
      async signOut() {
        if (client) await client.auth.signOut();
      },
    }),
    [client, error, ready, session],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("AuthProvider is missing");
  return value;
}
