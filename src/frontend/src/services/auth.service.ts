import { nexusCall } from "./api";
import { ROUTES } from "@/utils/constants";
import type { LoginResponse, User } from "@/types/auth";

export async function login(
  email: string,
  password: string,
): Promise<LoginResponse> {
  return nexusCall<LoginResponse>("login", { email, password });
}

export function logout(): void {
  sessionStorage.removeItem("access_token");
  sessionStorage.removeItem("refresh_token");
  sessionStorage.removeItem("user");
  window.location.href = ROUTES.LOGIN;
}

export function getStoredToken(): string | null {
  return sessionStorage.getItem("access_token");
}

export function getStoredUser(): User | null {
  const raw = sessionStorage.getItem("user");
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

export function storeAuth(token: string, user: User): void {
  sessionStorage.setItem("access_token", token);
  sessionStorage.setItem("user", JSON.stringify(user));
}

export async function refreshToken(): Promise<string> {
  const storedRefresh = sessionStorage.getItem("refresh_token");
  const result = await nexusCall<{ access_token: string }>("refresh_token", {
    refresh_token: storedRefresh,
  });
  const newToken = result.access_token;
  sessionStorage.setItem("access_token", newToken);
  return newToken;
}
