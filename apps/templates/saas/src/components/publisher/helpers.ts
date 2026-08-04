export function statusBadgeClass(status: string): string {
  switch (status) {
    case "published":
      return "bg-emerald-50 text-emerald-800";
    case "pending_review":
      return "bg-amber-50 text-amber-800";
    case "draft":
      return "bg-slate-100 text-slate-700";
    case "private":
      return "bg-indigo-50 text-indigo-800";
    case "rejected":
      return "bg-rose-50 text-rose-800";
    case "archived":
    case "suspended":
      return "bg-zinc-100 text-zinc-600";
    default:
      return "bg-slate-100 text-slate-700";
  }
}

export function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 120);
}
