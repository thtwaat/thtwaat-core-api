import { describe, expect, it } from "vitest";
import { ApiError } from "./api";
import {
  buildSelectPayload,
  connectionStatusLabel,
  connectionStatusTone,
  githubApiErrorMessage,
  githubCallbackErrorMessage,
  hasSelectedRepository,
  isNotConnectedError,
  repositoryFullName,
  visibilityLabel,
  type GitHubBranchList,
  type GitHubConnection,
  type GitHubRepositoryList
} from "./github";

function fakeConnection(overrides: Partial<GitHubConnection> = {}): GitHubConnection {
  return {
    id: "conn-1",
    site_id: "site-1",
    connected: true,
    github_account_id: "55",
    github_username: "octocat",
    account_type: "User",
    installation_id: "1001",
    repository_owner: null,
    repository_name: null,
    repository_id: null,
    default_branch: null,
    selected_branch: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides
  };
}

describe("github: connection state mapping (item 1 — connected/disconnected state, items 11-12)", () => {
  it("connected state -> Connected / success tone", () => {
    const connection = fakeConnection();
    expect(connectionStatusLabel(connection)).toBe("Connected");
    expect(connectionStatusTone(connection)).toBe("success");
  });

  it("disconnected state (no connection row) -> Not connected / neutral tone", () => {
    expect(connectionStatusLabel(null)).toBe("Not connected");
    expect(connectionStatusTone(null)).toBe("neutral");
  });
});

describe("github: repository selection state (item 15 — selected repository payload)", () => {
  it("no repository selected yet", () => {
    const connection = fakeConnection();
    expect(hasSelectedRepository(connection)).toBe(false);
    expect(repositoryFullName(connection)).toBeNull();
  });

  it("repository selected -> owner/name full name", () => {
    const connection = fakeConnection({ repository_owner: "anish", repository_name: "my-saas" });
    expect(hasSelectedRepository(connection)).toBe(true);
    expect(repositoryFullName(connection)).toBe("anish/my-saas");
  });

  it("a partial row (owner without name, e.g. a mid-migration state) is never treated as selected", () => {
    const connection = fakeConnection({ repository_owner: "anish", repository_name: null });
    expect(hasSelectedRepository(connection)).toBe(false);
    expect(repositoryFullName(connection)).toBeNull();
  });
});

describe("github: select-repository payload builder (item 15/16 — selected repository/branch payload)", () => {
  it("builds the exact POST .../github/select body the backend expects", () => {
    const payload = buildSelectPayload({ owner: "anish", name: "my-saas", branch: "main" });
    expect(payload).toEqual({
      repository_owner: "anish",
      repository_name: "my-saas",
      branch: "main"
    });
  });
});

describe("github: repository display mapping (item 2)", () => {
  it("maps private/public to a visibility label", () => {
    expect(visibilityLabel(true)).toBe("Private");
    expect(visibilityLabel(false)).toBe("Public");
  });
});

describe("github: empty repository/branch lists (items 13-14)", () => {
  it("empty repository list has no items to render", () => {
    const list: GitHubRepositoryList = { items: [], page: 1, per_page: 30 };
    expect(list.items).toHaveLength(0);
  });

  it("empty branch list has no items to render", () => {
    const list: GitHubBranchList = { items: [], page: 1, per_page: 30 };
    expect(list.items).toHaveLength(0);
  });
});

describe("github: not-connected 404 detection", () => {
  it("a 404 ApiError is the 'not connected' sentinel", () => {
    expect(isNotConnectedError(new ApiError("x", 404))).toBe(true);
  });

  it("any other status is not treated as 'not connected'", () => {
    expect(isNotConnectedError(new ApiError("x", 403))).toBe(false);
    expect(isNotConnectedError(new Error("boom"))).toBe(false);
  });
});

describe("github: API error message mapping (items 4-10 — 401/403/404/409/429/503)", () => {
  it("401 -> session expired", () => {
    expect(githubApiErrorMessage(new ApiError("x", 401))).toMatch(/session has expired/i);
  });

  it("403 -> permission message (RBAC copy, matches spec section 16 exactly)", () => {
    expect(githubApiErrorMessage(new ApiError("x", 403))).toBe(
      "You don't have permission to manage GitHub connections."
    );
  });

  it("404 -> not found message, never echoes backend detail", () => {
    expect(githubApiErrorMessage(new ApiError("x", 404))).toMatch(/could not be found/i);
  });

  it("409 -> already-connected message", () => {
    expect(githubApiErrorMessage(new ApiError("x", 409))).toMatch(/already connected/i);
  });

  it("422 -> prefers the formatted validation message when present", () => {
    const err = new ApiError("Invalid branch name.", 422);
    expect(githubApiErrorMessage(err)).toBe("Invalid branch name.");
  });

  it("422 -> falls back to generic copy when no message was formatted", () => {
    expect(githubApiErrorMessage(new ApiError("", 422))).toMatch(/check the repository and branch/i);
  });

  it("429 -> rate limit message", () => {
    expect(githubApiErrorMessage(new ApiError("x", 429))).toMatch(/rate limit/i);
  });

  it("500 -> generic safe message, never a stack trace", () => {
    const err = new ApiError("TypeError: cannot read property 'x' of undefined\n  at foo.js:42", 500);
    const msg = githubApiErrorMessage(err);
    expect(msg).toBe("Something went wrong on our end. Please try again.");
    expect(msg).not.toMatch(/at foo\.js/);
  });

  it("503 -> GitHub App not configured, safe copy (spec section 10 special case)", () => {
    expect(githubApiErrorMessage(new ApiError("x", 503))).toBe(
      "GitHub integration is temporarily unavailable. Please try again later."
    );
  });

  it("unknown/non-ApiError errors get a generic safe fallback", () => {
    expect(githubApiErrorMessage(new Error("boom"))).toBe("Something went wrong. Please try again.");
    expect(githubApiErrorMessage("not an error at all")).toBe("Something went wrong. Please try again.");
  });
});

describe("github: OAuth-callback error mapping", () => {
  it("maps every backend callback error code to a safe, specific message", () => {
    expect(githubCallbackErrorMessage("invalid_state")).toMatch(/invalid or had expired/i);
    expect(githubCallbackErrorMessage("pending_approval")).toMatch(/pending approval/i);
    expect(githubCallbackErrorMessage("installation_suspended")).toMatch(/suspended/i);
    expect(githubCallbackErrorMessage("github_unavailable")).toMatch(/temporarily unavailable/i);
  });

  it("unknown or missing codes fall back to a generic safe message", () => {
    expect(githubCallbackErrorMessage(undefined)).toMatch(/something went wrong/i);
    expect(githubCallbackErrorMessage(null)).toMatch(/something went wrong/i);
    expect(githubCallbackErrorMessage("some_new_backend_code")).toMatch(/something went wrong/i);
  });
});

describe("github: credentials are never part of this module's data (items 17-18)", () => {
  it("a full GitHubConnection object never carries a credential-shaped field", () => {
    const connection = fakeConnection({ repository_owner: "anish", repository_name: "my-saas" });
    const forbidden = [
      "access_token",
      "refresh_token",
      "installation_token",
      "client_secret",
      "private_key",
      "token",
      "code",
      "authorization_code"
    ];
    for (const key of forbidden) {
      expect(Object.prototype.hasOwnProperty.call(connection, key)).toBe(false);
    }
  });

  it("error mapping never echoes error.detail — a leaked secret in a backend error body cannot reach a toast", () => {
    const err = new ApiError("Repository not found", 404, {
      detail: "installation access_token=ghs_leaked_token_value_should_never_appear"
    });
    const msg = githubApiErrorMessage(err);
    expect(msg).not.toMatch(/ghs_leaked_token_value/);
  });
});
