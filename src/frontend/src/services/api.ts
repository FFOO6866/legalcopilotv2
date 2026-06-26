import axios from "axios";
import { API_BASE_URL, ROUTES } from "@/utils/constants";

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use(
  (config) => {
    const token = sessionStorage.getItem("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error: unknown) => {
    return Promise.reject(error);
  },
);

apiClient.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (axios.isAxiosError(error)) {
      if (error.response?.status === 401) {
        sessionStorage.removeItem("access_token");
        sessionStorage.removeItem("user");
        window.location.href = ROUTES.LOGIN;
        return Promise.reject(new Error("Session expired. Please log in again."));
      }

      if (error.response?.status === 429) {
        return Promise.reject(
          new Error("Too many requests. Please wait a moment and try again."),
        );
      }

      const serverMessage =
        (error.response?.data as Record<string, unknown>)?.error;
      if (typeof serverMessage === "string") {
        return Promise.reject(new Error(serverMessage));
      }
    }

    if (axios.isAxiosError(error) && !error.response) {
      return Promise.reject(
        new Error(
          "Unable to connect to the server. Please check your connection.",
        ),
      );
    }

    return Promise.reject(error);
  },
);

export async function nexusCall<T>(
  handler: string,
  params: Record<string, unknown>,
): Promise<T> {
  const response = await apiClient.post<T>("/nexus", {
    handler,
    params,
  });
  const data = response.data;
  // Backend returns 200 with {error: "..."} for business-logic errors
  if (
    data &&
    typeof data === "object" &&
    "error" in data &&
    typeof (data as Record<string, unknown>).error === "string"
  ) {
    throw new Error((data as Record<string, unknown>).error as string);
  }
  return data;
}

export { apiClient };
