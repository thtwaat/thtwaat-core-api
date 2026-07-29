import type { PageParams, PageResult } from "./types";

/** Normalize various API list shapes into PageResult */
export function normalizePage<T = unknown>(raw: unknown, params: PageParams = {}): PageResult<T> {
  if (Array.isArray(raw)) {
    const limit = params.limit ?? raw.length;
    const offset = params.offset ?? 0;
    return {
      items: raw as T[],
      total: raw.length,
      limit,
      offset,
      hasMore: false,
      raw,
    };
  }

  if (raw && typeof raw === "object") {
    const obj = raw as Record<string, unknown>;
    const items = (obj.items || obj.results || obj.data || obj.companies || obj.users || []) as T[];
    const list = Array.isArray(items) ? items : [];
    const total = typeof obj.total === "number" ? obj.total : undefined;
    const limit = typeof obj.limit === "number" ? obj.limit : params.limit;
    const offset = typeof obj.offset === "number" ? obj.offset : params.offset;
    const cursor = (obj.cursor as string) ?? params.cursor ?? null;
    const nextCursor = (obj.next_cursor as string) || (obj.nextCursor as string) || null;
    const hasMore =
      typeof obj.has_more === "boolean"
        ? obj.has_more
        : nextCursor
          ? true
          : typeof total === "number" && typeof offset === "number" && typeof limit === "number"
            ? offset + list.length < total
            : false;

    return { items: list, total, limit, offset, cursor, nextCursor, hasMore, raw };
  }

  return { items: [], raw };
}

export async function* iteratePages<T>(
  fetchPage: (params: PageParams) => Promise<PageResult<T>>,
  initial: PageParams = {}
): AsyncGenerator<T, void, void> {
  let offset = initial.offset ?? 0;
  let cursor = initial.cursor ?? null;
  const limit = initial.limit ?? 50;

  while (true) {
    const page = await fetchPage({ ...initial, limit, offset, cursor });
    for (const item of page.items) yield item;

    if (page.nextCursor) {
      cursor = page.nextCursor;
      continue;
    }
    if (page.hasMore && typeof page.limit === "number") {
      offset = (page.offset ?? offset) + page.items.length;
      continue;
    }
    break;
  }
}
