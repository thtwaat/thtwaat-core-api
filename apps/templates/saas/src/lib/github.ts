// THTWAAT Deploy Phase 5B — GitHub Connect (UI over the Phase 5 backend).
// Sibling to lib/env-vars.ts / lib/static-sites.ts — types and pure helpers
// only; the API surface lives in lib/services.ts (githubApi).
//
// Mirrors the backend contract exactly (app/static_sites/schemas.py):
// GitHubConnection never carries an access/refresh token, installation
// token, or private key field — this is a GitHub App installation, not an
// OAuth App, so the backend never has one to return in the first place (see
// app/static_sites/models.py::GitHubConnection). Every type below is a 1:1
// mirror of the backend response shape; do not add a field here for
// anything the backend intentionally omits.

import { ApiError } from "@/lib/api";

export type GitHubConnection = {
  id: string;
  site_id: string;
  connected: boolean;
  github_account_id: string;
  github_username: string;
  account_type?: string | null;
  installation_id: string;
  repository_owner?: string | null;
  repository_name?: string | null;
  repository_id?: string | null;
  default_branch?: string | null;
  selected_branch?: string | null;
  created_at: string;
  updated_at: string;
};

export type GitHubConnectStartResponse = {
  authorize_url: string;
};

export type GitHubRepository = {
  repository_id: string;
  owner: string;
  name: string;
  full_name: string;
  private: boolean;
  default_branch?: string | null;
};

export type GitHubRepositoryList = {
  items: GitHubRepository[];
  page: number;
  per_page: number;
};

export type GitHubBranch = {
  name: string;
  protected: boolean;
};

export type GitHubBranchList = {
  items: GitHubBranch[];
  page: number;
  per_page: number;
};

export type GitHubSelectRepositoryRequest = {
  repository_owner: string;
  repository_name: string;
  branch: string;
};

export const GITHUB_REPOSITORIES_PER_PAGE = 30;
export const GITHUB_BRANCHES_PER_PAGE = 30;

/** "owner/name", or null when no repository has been selected yet. */
export function repositoryFullName(
  connection: Pick<GitHubConnection, "repository_owner" | "repository_name">
): string | null {
  if (!connection.repository_owner || !connection.repository_name) return null;
  return `${connection.repository_owner}/${connection.repository_name}`;
}

export function hasSelectedRepository(
  connection: Pick<GitHubConnection, "repository_owner" | "repository_name">
): boolean {
  return Boolean(connection.repository_owner && connection.repository_name);
}

export function visibilityLabel(isPrivate: boolean): "Private" | "Public" {
  return isPrivate ? "Private" : "Public";
}

export function connectionStatusLabel(connection: GitHubConnection | null): "Connected" | "Not connected" {
  return connection ? "Connected" : "Not connected";
}

export function connectionStatusTone(connection: GitHubConnection | null): "success" | "neutral" {
  return connection ? "success" : "neutral";
}

/** Payload builder for POST .../github/select — keeps the request shape in
 * one place rather than assembled inline at each call site. */
export function buildSelectPayload(input: {
  owner: string;
  name: string;
  branch: string;
}): GitHubSelectRepositoryRequest {
  return {
    repository_owner: input.owner,
    repository_name: input.name,
    branch: input.branch
  };
}

const FRIENDLY_STATUS_MESSAGE: Record<number, string> = {
  401: "Your session has expired. Please sign in again.",
  403: "You don't have permission to manage GitHub connections.",
  404: "That GitHub connection, repository, or site could not be found.",
  409: "This site is already connected to a GitHub repository.",
  422: "Please check the repository and branch you selected.",
  429: "GitHub API rate limit exceeded. Please try again in a few minutes.",
  500: "Something went wrong on our end. Please try again.",
  503: "GitHub integration is temporarily unavailable. Please try again later."
};

/**
 * Safe, user-facing message for any GitHub Connect API failure. Only
 * ApiError's `.message` is trusted (see lib/api.ts's formatApiErrorMessage,
 * which already strips a raw backend payload down to a short, safe string)
 * — `error.detail` (which could carry an arbitrary object) is never
 * surfaced, so nothing sensitive the backend might echo back can leak into
 * a toast or log line through this function.
 */
export function githubApiErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return "Something went wrong. Please try again.";
  }
  const status = error.status;
  if (FRIENDLY_STATUS_MESSAGE[status]) {
    if (status === 422 && error.message.trim()) {
      return error.message;
    }
    return FRIENDLY_STATUS_MESSAGE[status];
  }
  if (error.message.trim()) {
    return error.message;
  }
  return "Something went wrong. Please try again.";
}

/** True only for the "GitHub is not connected for this site" 404 that
 * githubApi.getConnection() maps to `null` — see lib/services.ts. */
export function isNotConnectedError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}

// Error codes the backend callback redirect can carry as `?github_error=`
// (see app/static_sites/github_service.py::handle_callback) — never an HTTP
// status code, so these are mapped separately from githubApiErrorMessage.
const CALLBACK_ERROR_MESSAGE: Record<string, string> = {
  invalid_state: "That GitHub authorization link was invalid or had expired. Please try connecting again.",
  pending_approval: "GitHub authorization is pending approval from your GitHub organization owner.",
  missing_installation: "GitHub authorization did not complete. Please try again.",
  installation_suspended:
    "This GitHub App installation has been suspended. Please contact your GitHub organization admin.",
  github_unavailable: "GitHub is temporarily unavailable. Please try again later.",
  internal_error: "Something went wrong while connecting GitHub. Please try again."
};

export function githubCallbackErrorMessage(code?: string | null): string {
  if (!code) return "Something went wrong while connecting GitHub. Please try again.";
  return CALLBACK_ERROR_MESSAGE[code] || "Something went wrong while connecting GitHub. Please try again.";
}
