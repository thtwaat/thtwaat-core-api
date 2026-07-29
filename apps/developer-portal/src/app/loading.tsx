export default function Loading() {
  return (
    <div className="animate-pulse space-y-4 py-8">
      <div className="h-8 w-48 rounded-lg bg-line" />
      <div className="h-4 w-full max-w-xl rounded bg-line" />
      <div className="h-4 w-2/3 rounded bg-line" />
      <div className="mt-8 h-64 rounded-2xl border border-dashed border-line bg-canvas" />
    </div>
  );
}
