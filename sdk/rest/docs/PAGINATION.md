# Pagination Guide

```ts
const page = await api.companies.list({ limit: 20, offset: 0 });
console.log(page.items, page.total, page.hasMore);

// Auto iterator
for await (const company of api.companies.iterate({ limit: 50 })) {
  console.log(company);
}
```

Helpers:

- `normalizePage(raw, params)`
- `iteratePages(fetchPage, initialParams)`

Supports `limit` / `offset` / `cursor` / `next_cursor` shapes.
