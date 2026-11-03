/**
 * HTTP Client dengan penyisipan otomatis Bearer Token & auto-refresh token Keycloak.
 */

const getApiBaseUrl = (): string => {
  if (typeof window !== "undefined" && window.location && window.location.hostname) {
    const protocol = window.location.protocol;
    const hostname = window.location.hostname;
    if (hostname !== "localhost" && hostname !== "127.0.0.1") {
      return `${protocol}//${hostname}:8000`;
    }
  }
  return import.meta.env.VITE_API_URL || "http://localhost:8000";
};

export const BASE_URL = getApiBaseUrl();

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (err: any) => void;
}> = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token!);
    }
  });
  failedQueue = [];
};

export const getAccessToken = (): string | null => {
  return localStorage.getItem("access_token");
};

export const getRefreshToken = (): string | null => {
  return localStorage.getItem("refresh_token");
};

export const setTokens = (access: string, refresh: string) => {
  localStorage.setItem("access_token", access);
  localStorage.setItem("refresh_token", refresh);
};

export const clearTokens = () => {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  localStorage.removeItem("current_user");
};

export async function apiFetch<T = any>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;
  const token = getAccessToken();

  const headers = new Headers(options.headers || {});
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  // Jika bukan FormData dan belum ada Content-Type, default ke JSON
  if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const config: RequestInit = {
    ...options,
    headers,
  };

  let response = await fetch(url, config);

  // Tangani 401 Unauthorized -> Coba Refresh Token
  if (response.status === 401 && !endpoint.includes("/auth/")) {
    const refreshToken = getRefreshToken();
    if (!refreshToken) {
      clearTokens();
      window.location.href = "/login";
      throw new Error("Sesi berakhir. Silakan login kembali.");
    }

    if (isRefreshing) {
      return new Promise<T>((resolve, reject) => {
        failedQueue.push({
          resolve: async (newToken: string) => {
            headers.set("Authorization", `Bearer ${newToken}`);
            try {
              const res = await fetch(url, { ...options, headers });
              const data = await res.json();
              resolve(data);
            } catch (err) {
              reject(err);
            }
          },
          reject: (err) => reject(err),
        });
      });
    }

    isRefreshing = true;

    try {
      const refreshRes = await fetch(`${BASE_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!refreshRes.ok) {
        throw new Error("Refresh token kadaluarsa.");
      }

      const tokenData = await refreshRes.json();
      setTokens(tokenData.access_token, tokenData.refresh_token);
      processQueue(null, tokenData.access_token);

      // Ulangi request asli dengan token baru
      headers.set("Authorization", `Bearer ${tokenData.access_token}`);
      response = await fetch(url, { ...options, headers });
    } catch (refreshErr) {
      processQueue(refreshErr, null);
      clearTokens();
      window.location.href = "/login";
      throw new Error("Sesi login berakhir. Harap login kembali.");
    } finally {
      isRefreshing = false;
    }
  }

  if (!response.ok) {
    let errorDetail = "Terjadi kesalahan pada server";
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errJson.message || errorDetail;
    } catch {
      errorDetail = await response.text();
    }
    throw new Error(errorDetail);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

/**
 * Ambil respons biner (mis. file PDF) dengan header Authorization.
 * <iframe src> tidak bisa mengirim Bearer token, jadi file diambil sebagai Blob
 * lalu ditampilkan lewat URL.createObjectURL().
 */
export async function apiFetchBlob(endpoint: string): Promise<Blob> {
  const url = `${BASE_URL}${endpoint.startsWith("/") ? endpoint : `/${endpoint}`}`;
  const doFetch = () =>
    fetch(url, { headers: { Authorization: `Bearer ${getAccessToken() ?? ""}` } });

  let response = await doFetch();
  if (response.status === 401) {
    // Picu alur refresh token milik apiFetch, lalu ulangi sekali
    await apiFetch("/me");
    response = await doFetch();
  }
  if (!response.ok) {
    let detail = "Gagal memuat file";
    try {
      detail = (await response.json()).detail || detail;
    } catch {
      /* bukan JSON */
    }
    throw new Error(detail);
  }
  return response.blob();
}

export const api = {
  get: <T = any>(endpoint: string, headers?: HeadersInit) =>
    apiFetch<T>(endpoint, { method: "GET", headers }),
  post: <T = any>(endpoint: string, body?: any, headers?: HeadersInit) =>
    apiFetch<T>(endpoint, {
      method: "POST",
      body: body instanceof FormData ? body : JSON.stringify(body),
      headers,
    }),
  put: <T = any>(endpoint: string, body?: any, headers?: HeadersInit) =>
    apiFetch<T>(endpoint, {
      method: "PUT",
      body: JSON.stringify(body),
      headers,
    }),
  patch: <T = any>(endpoint: string, body?: any, headers?: HeadersInit) =>
    apiFetch<T>(endpoint, {
      method: "PATCH",
      body: JSON.stringify(body),
      headers,
    }),
  delete: <T = any>(endpoint: string, headers?: HeadersInit) =>
    apiFetch<T>(endpoint, { method: "DELETE", headers }),
};
