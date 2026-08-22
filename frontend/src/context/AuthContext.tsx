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

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchProfile = useCallback(async () => {
    try {
      setIsLoading(true);
      const { data } = await apiClient.get<UserProfile>("/auth/me");
      setProfile(data);
    } catch (error) {
      console.error("Failed to fetch profile", error);
      setProfile(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    // Initial session check
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      if (session) {
        fetchProfile();
      } else {
        setIsLoading(false);
      }
    });

    // Listen for auth state changes (e.g. login, logout, token refresh)
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
      if (session) {
        fetchProfile();
      } else {
        setProfile(null);
        setIsLoading(false);
      }
    });

    return () => {
      subscription.unsubscribe();
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
      await fetchProfile();
    }
  }, [session, fetchProfile]);

  const isBypass = import.meta.env.DEV && import.meta.env.VITE_DISABLE_LOGIN === 'true';

  const value = useMemo<AuthContextValue>(
    () => {
      if (isBypass) {
        return {
          session: null,
          profile: {
            id: "dev-bypass",
            employee_id: "dev-bypass",
            full_name: "DEV BYPASS - NOT REAL",
            role: "admin",
            department: "DEV",
            is_active: true,
            last_login_at: new Date().toISOString(),
          },
          role: "admin",
          isLoading: false,
          isAuthenticated: true,
          login: async () => {},
          logout: async () => {},
          refreshProfile: async () => {},
        };
      }

      return {
        session,
        profile,
        role: profile?.role ?? null,
        isLoading,
        isAuthenticated: Boolean(session),
        login,
        logout,
        refreshProfile,
      };
    },
    [session, profile, isLoading, login, logout, refreshProfile, isBypass]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
