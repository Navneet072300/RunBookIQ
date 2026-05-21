import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_URL ?? "";

export const apiClient = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: {
    "Content-Type": "application/json",
    "X-Tenant-ID": "default",
  },
});

apiClient.interceptors.response.use(
  (res) => res,
  (err) => {
    const msg =
      err.response?.data?.detail ?? err.message ?? "Unknown error";
    console.error("[API Error]", msg);
    return Promise.reject(new Error(msg));
  }
);
