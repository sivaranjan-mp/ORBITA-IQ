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
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: any) => void;
}> = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token as string);
    }
  });
  failedQueue = [];
};

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;

    if (error.response?.status === 401 && originalRequest) {
      // Axios may strip custom config properties, so we use a header to track retries.
      if (originalRequest.headers['X-Retried']) {
        await supabase.auth.signOut();
        alert("Session validation failed on the server. Please log in again.");
        window.location.assign("/login");
        return Promise.reject(error);
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            originalRequest.headers['X-Retried'] = 'true';
            return apiClient.request(originalRequest);
          })
          .catch((err) => {
            return Promise.reject(err);
          });
      }

      originalRequest.headers['X-Retried'] = 'true';
      isRefreshing = true;
      try {
        const { data, error: refreshError } = await supabase.auth.refreshSession();
        if (!refreshError && data.session) {
          const newToken = data.session.access_token;
          processQueue(null, newToken);
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
          return await apiClient.request(originalRequest);
        }

        // If we reach here, refresh failed. We distinguish between a genuine
        // auth failure (4xx) which warrants a logout, vs a network error.
        const isAuthError = refreshError?.status === 400 || refreshError?.status === 401 || refreshError?.status === 403;
        
        processQueue(refreshError || new Error("Refresh failed"), null);

        if (isAuthError) {
          await supabase.auth.signOut();
          window.location.assign("/login");
        }
      } catch (err) {
        processQueue(err, null);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);
