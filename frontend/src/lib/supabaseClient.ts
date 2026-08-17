import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error(
    "Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY. Check your .env file."
  );
}

/**
 * A single, shared Supabase client.
 *
 * - persistSession: writes the session to localStorage so it survives
 *   page reloads and browser restarts (session persistence).
 * - autoRefreshToken: silently rotates the access token before it
 *   expires, as long as the tab stays open.
 * - detectSessionInUrl: required for the password-reset flow — when the
 *   user lands on /reset-password from the emailed link, supabase-js
 *   parses the recovery token out of the URL and establishes a
 *   short-lived recovery session automatically.
 */
export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
    storage: window.localStorage,
    storageKey: "satops-auth-session",
  },
});
