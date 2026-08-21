import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";

import { supabase } from "@/lib/supabaseClient";

const baseURL = (import.meta.env.VITE_API_BASE_URL as string);

if (!baseURL) {
  throw new Error("Missing VITE_API_BASE_URL. Check your .env file.");
}

export const apiClient = axios.create({ baseURL });

// Attach the current Supabase access token to every outgoing request.
apiClient.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// If a request comes back 401, try one silent refresh + retry before
// giving up and forcing the user back to /login.
let isRefreshing = false;

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;

    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retried &&
      !isRefreshing &&
      !originalRequest.url?.includes("/auth/")
    ) {
      originalRequest._retried = true;
      isRefreshing = true;
      try {
        const { data, error: refreshError } = await supabase.auth.refreshSession();
        if (!refreshError && data.session) {
          originalRequest.headers = originalRequest.headers ?? {};
          originalRequest.headers.Authorization = `Bearer ${data.session.access_token}`;
          return apiClient.request(originalRequest);
        }
      } finally {
        isRefreshing = false;
      }

      await supabase.auth.signOut();
      window.location.assign("/login");
    }

    return Promise.reject(error);
  }
);
