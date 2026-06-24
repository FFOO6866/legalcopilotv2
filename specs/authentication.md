# Authentication Specification — LegalCoPilot v2

| Field          | Value                                                        |
| -------------- | ------------------------------------------------------------ |
| Status         | Draft                                                        |
| Authors        | LegalCoPilot Engineering                                     |
| Created        | 2026-06-23                                                   |
| Last Updated   | 2026-06-23                                                   |
| Depends On     | Kailash Nexus (NexusAuthPlugin), Kailash DataFlow, bcrypt    |
| Implements For | RevLaw LLC (Singapore) — pilot deployment                    |

## Overview

This specification defines the complete authentication system for LegalCoPilot v2, a legal assistant platform for Singapore law firms. The system provides password-based login with JWT token issuance, multi-tenant isolation via `firm_id`, and role-based access control across six user roles.

The backend is built on Kailash Nexus (API layer) and Kailash DataFlow (database layer). The frontend is React 19 + TypeScript + Vite.

### Current State (What Exists)

- **User model** at `src/legalcopilot/models/core.py:42-79` with `email`, `role`, `firm_id`, `last_login_at` — but NO `password_hash` field.
- **JWT infrastructure** fully wired: `NexusAuthPlugin.enterprise()` with `JWTConfig`, RBAC for 6 roles, tenant isolation via `firm_id` claim (see `src/legalcopilot/api/app.py:51-106`).
- **JWT_SECRET** and **JWT_ALGORITHM** in settings (`src/legalcopilot/config/settings.py:39-50`), sourced from environment variable `JWT_SECRET_KEY`.
- **Frontend scaffolding**: Login page (`src/frontend/src/pages/Login.tsx`), auth store (`src/frontend/src/stores/authStore.ts`), auth service (`src/frontend/src/services/auth.service.ts`), Axios interceptor with 401 redirect (`src/frontend/src/services/api.ts`), auth types (`src/frontend/src/types/auth.ts`).
- **NO login/logout API endpoints** exist on the backend.
- **NO user seed data** exists (no seed script anywhere in the repo).
- **NO `password_hash` field** on the User model.

### What This Spec Delivers

1. `password_hash` field added to the User model.
2. Backend auth endpoints: login, logout, me, refresh.
3. Idempotent seed script for three pre-configured users.
4. Frontend auth flow connected end-to-end.
5. Security constraints: bcrypt, token expiry, rate limiting, error messages.

---

## 1. Data Model Changes

### 1.1 User Model — Add `password_hash`

**File**: `src/legalcopilot/models/core.py`

Add `password_hash` as an optional string field on the `User` model. It is optional because DataFlow models may have users created via SSO or other methods in the future where password auth is not applicable.

```python
@db.model
class User:
    """Lawyer or staff member belonging to a firm."""

    id: str
    firm_id: str
    email: str
    name: str
    role: str = "associate"
    password_hash: Optional[str] = None   # <-- NEW FIELD
    permissions: dict = {}
    active: bool = True
    last_login_at: Optional[datetime] = None
    created_at: datetime = None
    updated_at: datetime = None
```

**Constraints**:
- `password_hash` is `Optional[str]` with a default of `None`.
- The field stores a bcrypt hash string (60 characters, starting with `$2b$`).
- The field MUST NOT appear in any API response body. It is write-only from the API perspective.
- DataFlow's `auto_migrate=True` will add the column on next startup.

### 1.2 Fields Excluded From API Responses

The following User model fields MUST be stripped from every API response that returns user data:

- `password_hash` — credential material, never exposed.

The `/api/auth/me` endpoint and the `user` object in `LoginResponse` MUST omit `password_hash`. The backend handler is responsible for this exclusion before serialization.

---

## 2. Pre-Seeded Users

### 2.1 Seed Data

Three users for RevLaw LLC, pre-configured for the pilot deployment.

| Name       | Email                    | Role    | Password        | Notes                      |
| ---------- | ------------------------ | ------- | --------------- | -------------------------- |
| Sui Tong   | suitong@revlawllc.com    | partner | RevLawST2026!   | Firm steward, full access  |
| Yik Wee    | yikwee@revlawllc.com     | partner | RevLawYW2026!   | Partner, full access       |
| Tech Admin | admin@revlawllc.com      | admin   | DemoAdmin2026!  | Technical administrator    |

**Firm**:

| Field             | Value          |
| ----------------- | -------------- |
| name              | RevLaw LLC     |
| domain            | revlawllc.com  |
| subscription_plan | professional   |
| active            | true           |

### 2.2 Seed Script

**File**: `scripts/seed_users.py`

The script MUST be:

- **Idempotent**: Running it multiple times produces the same result. If the firm already exists (matched by `domain`), skip creation. If a user already exists (matched by `firm_id` + `email`), update the `password_hash` (in case the password changed) but do not duplicate.
- **Standalone**: Executable via `python scripts/seed_users.py` from the project root.
- **Environment-aware**: Uses the same `DATABASE_URL` from `.env` via the existing settings module.

**Algorithm**:

```
1. Load settings (DATABASE_URL from .env).
2. Initialize DataFlow with the same DATABASE_URL.
3. Upsert Firm:
   a. Search for firm with domain = "revlawllc.com".
   b. If not found, create it. Record the firm_id.
   c. If found, use the existing firm_id.
4. For each seed user (Sui Tong, Yik Wee, Tech Admin):
   a. Hash the password with bcrypt (cost factor 12).
   b. Search for user with firm_id + email.
   c. If not found, create the user with all fields.
   d. If found, update password_hash only.
5. Print summary of actions taken.
```

**Password hashing**:

```python
import bcrypt

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
```

The `bcrypt` library MUST be added to `pyproject.toml` dependencies.

### 2.3 Seed Script Output

The script MUST print human-readable output indicating what it did:

```
LegalCoPilot v2 — User Seed Script
====================================
Firm: RevLaw LLC (domain: revlawllc.com) — created / already exists
User: suitong@revlawllc.com (partner) — created / updated
User: yikwee@revlawllc.com (partner) — created / updated
User: admin@revlawllc.com (admin) — created / updated
====================================
Seed complete. 3 users ready.
```

---

## 3. Backend Auth Endpoints

All auth endpoints live under the `/api/auth` prefix. The Nexus handler registration pattern is used (direct `@app.handler` decorators or explicit route registration).

### 3.1 Endpoint Summary

| Method | Path               | Auth Required | Description                        |
| ------ | ------------------ | ------------- | ---------------------------------- |
| POST   | /api/auth/login    | No            | Authenticate with email + password |
| POST   | /api/auth/logout   | Yes           | Invalidate session (client-side)   |
| GET    | /api/auth/me       | Yes           | Return current user profile        |
| POST   | /api/auth/refresh  | No            | Exchange refresh token for new access token |

### 3.2 JWT Exempt Paths

The following paths MUST be added to the `JWTConfig.exempt_paths` list in `src/legalcopilot/api/app.py`:

```python
exempt_paths=[
    "/health",
    "/health/detailed",
    "/docs",
    "/openapi.json",
    "/api/auth/login",      # <-- NEW
    "/api/auth/refresh",    # <-- NEW
]
```

These paths bypass JWT verification. All other `/api/*` paths require a valid Bearer token.

### 3.3 POST /api/auth/login

**Purpose**: Authenticate a user with email and password. Return JWT tokens and user profile on success.

**Request**:

```
POST /api/auth/login
Content-Type: application/json

{
  "email": "suitong@revlawllc.com",
  "password": "RevLawST2026!"
}
```

**Request validation**:
- `email`: required, non-empty string, valid email format.
- `password`: required, non-empty string, minimum 8 characters.
- If either field is missing or empty, return 422 with `{"error": "Email and password are required"}`.

**Handler algorithm**:

```
1. Validate request body (email, password present and non-empty).
2. Look up user by email (case-insensitive) using DataFlow.
   - If not found → 401 {"error": "Invalid email or password"}
3. Check user.active == True.
   - If inactive → 403 {"error": "Account is inactive. Contact your firm administrator."}
4. Check user.password_hash is not None.
   - If None → 401 {"error": "Invalid email or password"}
   (This covers users who exist but have no password set.)
5. Verify password against password_hash using bcrypt.checkpw().
   - If mismatch → 401 {"error": "Invalid email or password"}
6. Update user.last_login_at to current UTC timestamp via DataFlow.
7. Generate access token (JWT) with claims:
   {
     "user_id": user.id,
     "firm_id": user.firm_id,
     "role": user.role,
     "email": user.email,
     "type": "access",
     "exp": now + 1 hour,
     "iat": now
   }
8. Generate refresh token (JWT) with claims:
   {
     "user_id": user.id,
     "firm_id": user.firm_id,
     "type": "refresh",
     "exp": now + 7 days,
     "iat": now
   }
9. Return 200 with response body.
```

**Success response** (200):

```json
{
  "user": {
    "id": "uuid-string",
    "email": "suitong@revlawllc.com",
    "name": "Sui Tong",
    "role": "partner",
    "firm_id": "uuid-string",
    "created_at": "2026-06-23T00:00:00Z"
  },
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**The `user` object MUST NOT include `password_hash`, `permissions`, `updated_at`, or `active`.**

**Error responses**:

| Status | Condition                        | Body                                                              |
| ------ | -------------------------------- | ----------------------------------------------------------------- |
| 401    | User not found                   | `{"error": "Invalid email or password"}`                          |
| 401    | Wrong password                   | `{"error": "Invalid email or password"}`                          |
| 401    | No password_hash set             | `{"error": "Invalid email or password"}`                          |
| 403    | User is inactive                 | `{"error": "Account is inactive. Contact your firm administrator."}` |
| 422    | Missing/empty email or password  | `{"error": "Email and password are required"}`                    |
| 429    | Rate limit exceeded              | Handled by existing `RateLimitConfig`                             |

**Security notes**:
- The 401 responses for "not found", "wrong password", and "no password_hash" MUST use the identical error message `"Invalid email or password"` to prevent user enumeration.
- Email lookup MUST be case-insensitive (lowercase comparison).
- The existing rate limiter in `app.py` applies to this endpoint. An additional per-route rate limit SHOULD be configured (see section 6.3).

### 3.4 POST /api/auth/logout

**Purpose**: Client-side logout. With stateless JWT, this endpoint is a no-op on the server but exists for API completeness and to support future token blacklisting.

**Request**:

```
POST /api/auth/logout
Authorization: Bearer <access_token>
```

No request body required.

**Handler algorithm**:

```
1. Verify JWT from Authorization header (handled by NexusAuthPlugin).
2. Return 200 with success message.
```

Future enhancement: If token blacklisting is added (e.g., via Redis), this endpoint would add the token's `jti` to the blacklist with a TTL matching the token's remaining lifetime.

**Success response** (200):

```json
{
  "message": "Logged out successfully"
}
```

**Error responses**:

| Status | Condition        | Body                                       |
| ------ | ---------------- | ------------------------------------------ |
| 401    | Missing token    | `{"error": "Authentication required"}`     |
| 401    | Invalid token    | `{"error": "Invalid or expired token"}`    |

### 3.5 GET /api/auth/me

**Purpose**: Return the currently authenticated user's profile, derived from JWT claims and enriched with database data.

**Request**:

```
GET /api/auth/me
Authorization: Bearer <access_token>
```

**Handler algorithm**:

```
1. Extract user_id from JWT claims (injected by NexusAuthPlugin).
2. Look up user by id using DataFlow.
   - If not found → 404 {"error": "User not found"}
   - If inactive → 403 {"error": "Account is inactive. Contact your firm administrator."}
3. Return user profile (excluding password_hash).
```

**Success response** (200):

```json
{
  "id": "uuid-string",
  "email": "suitong@revlawllc.com",
  "name": "Sui Tong",
  "role": "partner",
  "firm_id": "uuid-string",
  "last_login_at": "2026-06-23T10:30:00Z",
  "created_at": "2026-06-23T00:00:00Z"
}
```

**Error responses**:

| Status | Condition        | Body                                                              |
| ------ | ---------------- | ----------------------------------------------------------------- |
| 401    | Missing token    | `{"error": "Authentication required"}`                            |
| 401    | Expired token    | `{"error": "Token expired"}`                                     |
| 403    | Inactive user    | `{"error": "Account is inactive. Contact your firm administrator."}` |
| 404    | User deleted     | `{"error": "User not found"}`                                    |

### 3.6 POST /api/auth/refresh

**Purpose**: Exchange a valid refresh token for a new access token. The refresh token itself is NOT rotated (single-use refresh rotation is a future enhancement).

**Request**:

```
POST /api/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Handler algorithm**:

```
1. Validate refresh_token is present and non-empty.
   - If missing → 422 {"error": "Refresh token is required"}
2. Decode and verify the refresh token JWT.
   - If invalid signature → 401 {"error": "Invalid refresh token"}
   - If expired → 401 {"error": "Refresh token expired. Please log in again."}
3. Verify the token's "type" claim == "refresh".
   - If not a refresh token → 401 {"error": "Invalid refresh token"}
4. Look up user by user_id from token claims.
   - If not found → 401 {"error": "Invalid refresh token"}
   - If inactive → 403 {"error": "Account is inactive. Contact your firm administrator."}
5. Generate a new access token with fresh claims from the database
   (role may have changed since the original login):
   {
     "user_id": user.id,
     "firm_id": user.firm_id,
     "role": user.role,
     "email": user.email,
     "type": "access",
     "exp": now + 1 hour,
     "iat": now
   }
6. Return the new access token.
```

**Success response** (200):

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Error responses**:

| Status | Condition                    | Body                                                              |
| ------ | ---------------------------- | ----------------------------------------------------------------- |
| 401    | Invalid signature            | `{"error": "Invalid refresh token"}`                              |
| 401    | Expired refresh token        | `{"error": "Refresh token expired. Please log in again."}`        |
| 401    | Token type is not "refresh"  | `{"error": "Invalid refresh token"}`                              |
| 401    | User not found               | `{"error": "Invalid refresh token"}`                              |
| 403    | User is inactive             | `{"error": "Account is inactive. Contact your firm administrator."}` |
| 422    | Missing refresh_token field  | `{"error": "Refresh token is required"}`                          |

---

## 4. JWT Token Design

### 4.1 Access Token

| Field     | Value                                                    |
| --------- | -------------------------------------------------------- |
| Algorithm | HS256 (from `settings.JWT_ALGORITHM`)                    |
| Secret    | From `settings.JWT_SECRET` (env var `JWT_SECRET_KEY`)    |
| Expiry    | 1 hour from issuance                                     |
| Claims    | `user_id`, `firm_id`, `role`, `email`, `type: "access"` |

### 4.2 Refresh Token

| Field     | Value                                                    |
| --------- | -------------------------------------------------------- |
| Algorithm | HS256 (same as access)                                   |
| Secret    | From `settings.JWT_SECRET` (same key; see note below)    |
| Expiry    | 7 days from issuance                                     |
| Claims    | `user_id`, `firm_id`, `type: "refresh"`                  |

**Note on shared secret**: For the pilot deployment, both access and refresh tokens use the same signing secret. A future enhancement should use separate secrets or asymmetric keys for refresh tokens to limit blast radius if the access token secret is compromised.

### 4.3 Token Claims Schema

**Access token payload**:

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "firm_id": "660e8400-e29b-41d4-a716-446655440001",
  "role": "partner",
  "email": "suitong@revlawllc.com",
  "type": "access",
  "iat": 1750694400,
  "exp": 1750698000
}
```

**Refresh token payload**:

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "firm_id": "660e8400-e29b-41d4-a716-446655440001",
  "type": "refresh",
  "iat": 1750694400,
  "exp": 1751299200
}
```

### 4.4 Tenant Isolation

The existing `TenantConfig` in `app.py` enforces tenant isolation:

```python
tenant_isolation=TenantConfig(
    jwt_claim="firm_id",
    admin_role="partner",
)
```

This means:
- Every authenticated request carries `firm_id` in the JWT.
- DataFlow queries are automatically scoped to the user's `firm_id`.
- Users with role `partner` can access cross-tenant data (admin override).
- The `firm_id` claim in the JWT MUST match the firm_id on resources being accessed.

---

## 5. Frontend Auth Flow

### 5.1 Existing Frontend Infrastructure

The following files already exist and implement the frontend auth scaffolding:

| File                                        | What It Does                                           |
| ------------------------------------------- | ------------------------------------------------------ |
| `src/frontend/src/types/auth.ts`            | `User`, `LoginRequest`, `LoginResponse`, `AuthState` types |
| `src/frontend/src/stores/authStore.ts`      | Zustand store with `login`, `logout`, `initializeAuth` |
| `src/frontend/src/services/auth.service.ts` | `login()`, `logout()`, `refreshToken()`, storage helpers |
| `src/frontend/src/services/api.ts`          | Axios client with Bearer header interceptor and 401 redirect |
| `src/frontend/src/pages/Login.tsx`          | Login page with email/password form                    |
| `src/frontend/src/utils/constants.ts`       | `ROUTES.LOGIN`, `ROUTES.DASHBOARD`, `API_BASE_URL`    |

### 5.2 Auth Flow — Login

1. User navigates to `/login`.
2. `Login.tsx` renders the email/password form.
3. On form submit, `handleSubmit()` calls `useAuthStore.login(email, password)`.
4. The store calls `authService.login(email, password)`, which POSTs to `/api/auth/login`.
5. On success:
   a. `authService.storeAuth(access_token, user)` saves the access token and user to `sessionStorage`.
   b. The refresh token is saved to `sessionStorage` separately.
   c. The Zustand store is updated with `user` and `token`.
   d. Zustand's `persist` middleware also saves `user` and `token` to `sessionStorage` under the key `"auth-storage"`.
   e. `navigate(ROUTES.DASHBOARD, { replace: true })` redirects to the dashboard.
6. On failure:
   a. The error message from the API (or a fallback) is set in the store.
   b. The error is displayed in the red alert banner on the login page.

### 5.3 Auth Flow — Authenticated Requests

1. The Axios request interceptor (`src/frontend/src/services/api.ts:12-23`) reads the access token from `sessionStorage.getItem("access_token")`.
2. If a token exists, it attaches `Authorization: Bearer <token>` to every outgoing request.
3. This is transparent to all service calls (`chat.service.ts`, `case.service.ts`, etc.).

### 5.4 Auth Flow — 401 Handling

1. The Axios response interceptor (`src/frontend/src/services/api.ts:25-58`) catches 401 responses.
2. On 401:
   a. Clears `access_token` and `user` from `sessionStorage`.
   b. Redirects to `ROUTES.LOGIN` via `window.location.href`.
   c. Rejects the promise with `"Session expired. Please log in again."`.

**Enhancement needed**: Before redirecting on 401, the interceptor SHOULD attempt a token refresh using the stored refresh token. If the refresh succeeds, retry the original request. If the refresh also fails (401 or network error), then clear storage and redirect to login.

### 5.5 Auth Flow — Token Refresh

The `refreshToken()` function already exists in `src/frontend/src/services/auth.service.ts:44-53`:

1. Reads the refresh token from `sessionStorage.getItem("refresh_token")`.
2. POSTs to `/api/auth/refresh` with `{ refresh_token }`.
3. On success, stores the new access token in `sessionStorage`.
4. Returns the new token string.

**Integration with 401 interceptor**: The Axios response interceptor MUST be enhanced to:

```
On 401 response:
  1. Check if a refresh token exists in sessionStorage.
  2. If yes AND this is not already a refresh attempt:
     a. Call refreshToken().
     b. On success: update sessionStorage, retry original request with new token.
     c. On failure: clear storage, redirect to /login.
  3. If no refresh token: clear storage, redirect to /login.
```

A flag or queue mechanism MUST prevent concurrent refresh attempts (e.g., if multiple requests fail with 401 simultaneously, only one refresh call should be made).

### 5.6 Auth Flow — Logout

1. User clicks logout (button in the header/sidebar).
2. `useAuthStore.logout()` is called.
3. The store clears `user` and `token` to `null`.
4. `authService.logout()` clears `access_token`, `refresh_token`, and `user` from `sessionStorage`.
5. `window.location.href = ROUTES.LOGIN` redirects to the login page.

### 5.7 Auth Flow — Page Refresh / Session Persistence

1. On app mount, `useAuthStore.initializeAuth()` reads `access_token` and `user` from `sessionStorage`.
2. If both exist, the Zustand store is populated (the user remains logged in).
3. If either is missing, the store is cleared (the user must log in again).
4. The Zustand `persist` middleware with `sessionStorage` also restores state via its own hydration mechanism.

**Session lifetime**: Because `sessionStorage` is scoped to the browser tab, closing the tab clears the session. This is appropriate for a legal application handling sensitive data. Users who want cross-tab persistence should be informed that each tab requires separate login.

### 5.8 Route Protection

A route guard component MUST wrap all authenticated routes.

**Component**: `src/frontend/src/components/auth/ProtectedRoute.tsx`

```typescript
// Conceptual contract — not literal implementation
interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: string[];  // Optional: restrict to specific roles
}
```

**Behavior**:

1. Check `useIsAuthenticated()` from the auth store.
2. If not authenticated: redirect to `/login` with the current path as a `returnTo` query param.
3. If authenticated but role not in `requiredRole` (when specified): render a 403 "Access Denied" page.
4. If authenticated and authorized: render `children`.

**Route structure** (in the app router):

```
/login              → Login (public, redirects to /dashboard if already authenticated)
/dashboard          → ProtectedRoute > Dashboard
/cases              → ProtectedRoute > Cases
/cases/:id          → ProtectedRoute > CaseDetail
/documents          → ProtectedRoute > Documents
/research           → ProtectedRoute > Research (future)
/firm-knowledge     → ProtectedRoute > FirmKnowledge
/profile            → ProtectedRoute > Profile (future)
*                   → NotFound
```

### 5.9 Post-Login Redirect

When an unauthenticated user tries to access a protected route (e.g., `/cases/abc123`):

1. `ProtectedRoute` redirects to `/login?returnTo=/cases/abc123`.
2. After successful login, `handleSubmit()` checks for a `returnTo` query parameter.
3. If present, navigates to `returnTo` instead of the default `/dashboard`.
4. The `returnTo` value MUST be validated to prevent open redirect attacks: it MUST start with `/` and MUST NOT start with `//` or contain a protocol prefix.

---

## 6. Security

### 6.1 Password Hashing

- **Algorithm**: bcrypt.
- **Cost factor**: 12 (approximately 250ms per hash on modern hardware; balances security against login latency).
- **Library**: `bcrypt` (Python package).
- **Encoding**: Passwords are encoded to UTF-8 before hashing. The stored hash is a 60-character ASCII string.

**Verification**:

```python
import bcrypt

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
```

### 6.2 JWT Expiry

| Token Type    | Lifetime | Rationale                                                  |
| ------------- | -------- | ---------------------------------------------------------- |
| Access token  | 1 hour   | Short-lived to limit damage if intercepted                 |
| Refresh token | 7 days   | Allows users to stay logged in across a work week          |

**Clock skew**: The JWT library's default leeway (typically 0-30 seconds) is acceptable. No custom leeway is needed.

### 6.3 Rate Limiting on Login

The existing `RateLimitConfig` in `app.py` applies globally at `settings.RATE_LIMIT_RPM` (default: 100 RPM). The login endpoint SHOULD have a stricter per-route limit to prevent brute-force attacks.

**Recommended configuration**:

```python
route_limits={
    "/health": None,
    "/health/detailed": None,
    "/api/auth/login": 10,     # 10 requests per minute per IP
    "/api/auth/refresh": 20,   # 20 requests per minute per IP
}
```

This limits login attempts to 10 per minute per client, which is sufficient for legitimate use and blocks automated brute-force attempts.

### 6.4 No Secrets in Frontend Code

- The JWT secret MUST NOT appear in any frontend file, environment variable, or build artifact.
- The frontend accesses `VITE_API_BASE_URL` only (see `src/frontend/src/utils/constants.ts:3`).
- All token operations (signing, verification) happen exclusively on the backend.
- The frontend treats tokens as opaque strings.

### 6.5 CORS

The existing CORS configuration in `app.py` uses `settings.CORS_ORIGINS` (default: `http://localhost:3000`). In production, this MUST be set to the actual frontend origin.

`cors_allow_credentials` is currently `False` in `app.py:31`. Since tokens are passed via the `Authorization` header (not cookies), this is correct. If cookie-based auth is added in the future, this MUST be set to `True`.

### 6.6 Password Policy (Validation at Seed Time)

For the pilot deployment, passwords are set via the seed script only (no self-service password change). The seed passwords already meet these minimum requirements:

- Minimum 8 characters.
- At least one uppercase letter.
- At least one lowercase letter.
- At least one digit.
- At least one special character.

When a password change endpoint is added in the future, these constraints MUST be enforced server-side.

---

## 7. Error Responses — Complete Catalog

All error responses follow the same shape:

```json
{
  "error": "Human-readable error message"
}
```

### 7.1 Authentication Errors (401)

| Trigger                            | Response Body                                           |
| ---------------------------------- | ------------------------------------------------------- |
| No Authorization header            | `{"error": "Authentication required"}`                  |
| Malformed Authorization header     | `{"error": "Authentication required"}`                  |
| Invalid JWT signature              | `{"error": "Invalid or expired token"}`                 |
| Expired access token               | `{"error": "Token expired"}`                            |
| Login: user not found              | `{"error": "Invalid email or password"}`                |
| Login: wrong password              | `{"error": "Invalid email or password"}`                |
| Login: no password_hash set        | `{"error": "Invalid email or password"}`                |
| Refresh: invalid signature         | `{"error": "Invalid refresh token"}`                    |
| Refresh: expired token             | `{"error": "Refresh token expired. Please log in again."}` |
| Refresh: wrong token type          | `{"error": "Invalid refresh token"}`                    |
| Refresh: user not found            | `{"error": "Invalid refresh token"}`                    |

**User enumeration prevention**: The login endpoint uses the same error message for "user not found", "wrong password", and "no password set". An attacker cannot distinguish between these cases.

### 7.2 Authorization Errors (403)

| Trigger                          | Response Body                                                              |
| -------------------------------- | -------------------------------------------------------------------------- |
| User account is inactive         | `{"error": "Account is inactive. Contact your firm administrator."}`       |
| Insufficient role for operation  | `{"error": "Insufficient permissions"}`  (handled by existing RBAC)        |
| Tenant isolation violation       | `{"error": "Access denied"}`  (handled by existing TenantConfig)           |

### 7.3 Validation Errors (422)

| Trigger                              | Response Body                                    |
| ------------------------------------ | ------------------------------------------------ |
| Login: missing email or password     | `{"error": "Email and password are required"}`   |
| Refresh: missing refresh_token       | `{"error": "Refresh token is required"}`         |

### 7.4 Rate Limit Errors (429)

Handled by the existing `RateLimitConfig`. The response format is determined by NexusAuthPlugin's rate limiter.

---

## 8. File Layout

### 8.1 New Files

| File                                                    | Purpose                                        |
| ------------------------------------------------------- | ---------------------------------------------- |
| `src/legalcopilot/api/auth.py`                          | Auth endpoint handlers (login, logout, me, refresh) |
| `src/legalcopilot/services/auth_service.py`             | Password hashing/verification, JWT creation    |
| `scripts/seed_users.py`                                 | Idempotent user seed script                    |
| `src/frontend/src/components/auth/ProtectedRoute.tsx`   | Route guard component                          |

### 8.2 Modified Files

| File                                                    | Change                                         |
| ------------------------------------------------------- | ---------------------------------------------- |
| `src/legalcopilot/models/core.py`                       | Add `password_hash` field to User model        |
| `src/legalcopilot/api/app.py`                           | Add auth exempt paths, register auth routes    |
| `src/frontend/src/services/api.ts`                      | Enhance 401 interceptor with refresh logic     |
| `src/frontend/src/App.tsx`                              | Wire React Router with ProtectedRoute          |
| `pyproject.toml`                                        | Add `bcrypt` dependency                        |

### 8.3 Backend Module Structure

```
src/legalcopilot/
  api/
    app.py              # Nexus app factory (modified)
    auth.py             # NEW — auth endpoint registration
    cases.py            # Existing
    chat.py             # Existing
    ...
  services/
    auth_service.py     # NEW — password + JWT helpers
  models/
    core.py             # Modified — password_hash on User
    database.py         # Unchanged
  config/
    settings.py         # Unchanged (JWT_SECRET already here)
```

---

## 9. Integration Points

### 9.1 Auth Endpoints Registered in App Factory

In `src/legalcopilot/api/app.py`, the auth route registration MUST be called in `create_app()`:

```python
from legalcopilot.api.auth import register_auth_routes

def create_app() -> Nexus:
    app = Nexus(...)
    _configure_auth(app)
    _register_health_checks(app)
    _register_dataflow_workflows(app)

    # Register domain API routes
    register_auth_routes(app)        # <-- NEW, before other routes
    register_chat_routes(app)
    register_case_routes(app)
    register_document_routes(app)
    register_knowledge_routes(app)
    register_firm_knowledge_routes(app)

    return app
```

### 9.2 Auth Service — No PEP 563

Per the Nexus critical rule: **Never use `from __future__ import annotations`** in any file that defines Nexus handler functions. This breaks runtime type resolution for handler dependency injection.

### 9.3 DataFlow Integration

The auth endpoints interact with DataFlow for user lookup and update. Since `auto_discovery=False` is already set in `app.py:29`, there is no startup blocking risk. The auth handler will use DataFlow's auto-generated workflows:

- `user_read` — look up user by ID.
- `user_search` — search user by email + firm_id.
- `user_update` — update `last_login_at` after login.

### 9.4 Frontend API Base URL

The frontend's `API_BASE_URL` defaults to `/api` (see `src/frontend/src/utils/constants.ts:3`). The auth service calls go to `/auth/login`, which resolves to `/api/auth/login` via the Axios `baseURL`.

This means the backend auth endpoints MUST be mounted at `/api/auth/*` from the Nexus app's perspective, OR the Nexus app MUST be mounted behind a reverse proxy that strips the `/api` prefix.

---

## 10. Environment Variables

### 10.1 Required for Auth

| Variable        | Required | Default                                      | Description                      |
| --------------- | -------- | -------------------------------------------- | -------------------------------- |
| `JWT_SECRET_KEY`| Yes*     | `change-this-to-a-random-string-at-least-32-chars` | JWT signing secret        |
| `JWT_ALGORITHM` | No       | `HS256`                                      | JWT signing algorithm            |
| `DATABASE_URL`  | No       | `sqlite:///legalcopilot_dev.db`              | Database connection string       |

*In production (`APP_ENV != "development"`), `JWT_SECRET_KEY` MUST be set to a secure random value of at least 32 characters. The app raises `RuntimeError` on startup if the default is used in non-development mode (see `settings.py:44-49`).

### 10.2 Recommended .env for Development

```env
APP_ENV=development
JWT_SECRET_KEY=dev-secret-key-at-least-32-chars-long!!
DATABASE_URL=sqlite:///legalcopilot_dev.db
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

---

## 11. Testing Strategy

### 11.1 Backend Tests

| Test                                | Tier   | What It Verifies                                |
| ----------------------------------- | ------ | ----------------------------------------------- |
| `test_login_success`                | Tier-1 | Valid credentials return 200 + tokens + user    |
| `test_login_invalid_password`       | Tier-1 | Wrong password returns 401                      |
| `test_login_unknown_email`          | Tier-1 | Non-existent email returns 401                  |
| `test_login_inactive_user`          | Tier-1 | Inactive user returns 403                       |
| `test_login_no_password_hash`       | Tier-1 | User without password_hash returns 401          |
| `test_login_missing_fields`         | Tier-1 | Missing email/password returns 422              |
| `test_login_case_insensitive_email` | Tier-1 | Email lookup is case-insensitive                |
| `test_me_returns_profile`           | Tier-1 | Valid token returns user profile                |
| `test_me_excludes_password_hash`    | Tier-1 | Response does not contain password_hash         |
| `test_me_expired_token`             | Tier-1 | Expired token returns 401                       |
| `test_me_no_token`                  | Tier-1 | Missing token returns 401                       |
| `test_refresh_success`              | Tier-1 | Valid refresh token returns new access token    |
| `test_refresh_expired`              | Tier-1 | Expired refresh token returns 401               |
| `test_refresh_wrong_type`           | Tier-1 | Access token used as refresh returns 401        |
| `test_refresh_inactive_user`        | Tier-1 | Refresh for inactive user returns 403           |
| `test_logout_success`               | Tier-1 | Authenticated logout returns 200                |
| `test_password_hash_bcrypt`         | Tier-1 | hash_password produces valid bcrypt output      |
| `test_verify_password_correct`      | Tier-1 | verify_password returns True for matching pair  |
| `test_verify_password_incorrect`    | Tier-1 | verify_password returns False for wrong input   |
| `test_seed_script_idempotent`       | Tier-2 | Running seed twice does not duplicate records   |
| `test_login_updates_last_login_at`  | Tier-2 | Successful login writes last_login_at to DB     |
| `test_jwt_claims_correct`           | Tier-2 | Access token contains expected claims           |
| `test_tenant_isolation`             | Tier-2 | User from firm A cannot access firm B data      |

### 11.2 Frontend Tests

| Test                                     | What It Verifies                                     |
| ---------------------------------------- | ---------------------------------------------------- |
| `test_login_form_renders`                | Login page renders email, password fields, button    |
| `test_login_success_redirects`           | Successful login navigates to /dashboard             |
| `test_login_error_displays`              | Failed login shows error message                     |
| `test_401_redirects_to_login`            | 401 response triggers redirect to /login             |
| `test_protected_route_redirects`         | Unauthenticated access redirects to /login           |
| `test_authenticated_redirect_from_login` | Authenticated user on /login redirects to /dashboard |
| `test_logout_clears_state`              | Logout clears store and sessionStorage               |

---

## 12. Future Enhancements (Out of Scope for This Spec)

These are explicitly NOT part of the current implementation but are anticipated:

1. **Password change endpoint** (`POST /api/auth/password`) — with current password verification.
2. **Token blacklisting** — Redis-backed invalidation for logout and password change.
3. **Refresh token rotation** — issue a new refresh token on each refresh, invalidating the old one.
4. **Account lockout** — lock account after N failed login attempts (e.g., 5 failures in 15 minutes).
5. **SSO / OAuth2** — integration with firm identity providers (Azure AD, Google Workspace).
6. **Multi-factor authentication** — TOTP or SMS-based second factor.
7. **Separate refresh token secret** — asymmetric keys or a distinct HMAC secret for refresh tokens.
8. **Audit logging for auth events** — login success/failure, logout, token refresh logged to the audit system.
9. **Password reset via email** — for self-service password recovery.

---

## 13. Implementation Checklist

Ordered sequence for implementation:

1. Add `bcrypt` to `pyproject.toml` dependencies.
2. Add `password_hash: Optional[str] = None` to the User model in `core.py`.
3. Create `src/legalcopilot/services/auth_service.py` with `hash_password()`, `verify_password()`, `create_access_token()`, `create_refresh_token()`, `decode_token()`.
4. Create `src/legalcopilot/api/auth.py` with the four endpoint handlers.
5. Update `src/legalcopilot/api/app.py`: add auth exempt paths, register auth routes.
6. Create `scripts/seed_users.py` and run it.
7. Test all four endpoints manually (login, me, refresh, logout).
8. Enhance the frontend 401 interceptor with refresh token retry logic.
9. Create `ProtectedRoute.tsx` and wire it into `App.tsx` with React Router.
10. Test the full login-to-dashboard flow in the browser.
11. Write backend unit tests (Tier-1).
12. Write backend integration tests (Tier-2).
