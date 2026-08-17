import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { Session } from "@supabase/supabase-js";

import { apiClient } from "@/lib/apiClient";
import { supabase } from "@/lib/supabaseClient";
import type { LoginPayload, TokenResponse, UserProfile, UserRole } from "@/types/auth";

interface AuthContextValue {
  session: Session | null;
  profile: UserProfile | null;
  role: UserRole | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (payload: LoginPayload) => Promise<void>;
  logout: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const PROFILE_COLUMNS =
  "id, employee_id, full_name, role, department, is_active, last_login_at";

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchProfile = useCallback(async (userId: string) => {
    const { data, error } = await supabase
      .from("profiles")
      .select(PROFILE_COLUMNS)
      .eq("id", userId)
      .single();

    if (error) {
      console.error("Failed to load profile:", error.message);
      setProfile(null);
      return;
    }
    setProfile(data as UserProfile);
  }, []);

  // On mount: restore any persisted session (session persistence), then
  // keep listening for auth state changes (login, logout, token refresh,
  // password recovery) for the lifetime of the app.
  useEffect(() => {
    let isMounted = true;

    (async () => {
      const { data } = await supabase.auth.getSession();
      if (!isMounted) return;
      setSession(data.session);
      if (data.session?.user) {
        await fetchProfile(data.session.user.id);
      }
      setIsLoading(false);
    })();

    const { data: listener } = supabase.auth.onAuthStateChange(async (_event, nextSession) => {
      setSession(nextSession);
      if (nextSession?.user) {
        await fetchProfile(nextSession.user.id);
      } else {
        setProfile(null);
      }
    });

    return () => {
      isMounted = false;
      listener.subscription.unsubscribe();
    };
  }, [fetchProfile]);

  // Login goes through our backend (which resolves Employee ID -> email and
  // validates the password via Supabase GoTrue), then hands the resulting
  // tokens to supabase-js so it takes over persistence + auto-refresh.
  const login = useCallback(async (payload: LoginPayload) => {
    const { data } = await apiClient.post<TokenResponse>("/auth/login", payload);

    const { error } = await supabase.auth.setSession({
      access_token: data.access_token,
      refresh_token: data.refresh_token,
    });
    if (error) throw error;

    setProfile(data.user);
  }, []);

  const logout = useCallback(async () => {
    const { data } = await supabase.auth.getSession();
    const refreshToken = data.session?.refresh_token;
    try {
      if (refreshToken) {
        await apiClient.post("/auth/logout", { refresh_token: refreshToken });
      }
    } finally {
      await supabase.auth.signOut();
      setProfile(null);
      setSession(null);
    }
  }, []);

  const refreshProfile = useCallback(async () => {
    if (session?.user) {
      await fetchProfile(session.user.id);
    }
  }, [session, fetchProfile]);

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      profile,
      role: profile?.role ?? null,
      isLoading,
      isAuthenticated: Boolean(session),
      login,
      logout,
      refreshProfile,
    }),
    [session, profile, isLoading, login, logout, refreshProfile]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
