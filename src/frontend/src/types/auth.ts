export interface User {
  id: string;
  email: string;
  name: string;
  role:
    | "partner"
    | "senior_associate"
    | "associate"
    | "paralegal"
    | "admin"
    | "viewer";
  firm_id: string;
  avatar_url?: string;
  created_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  user: User;
  access_token: string;
  refresh_token: string;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}
