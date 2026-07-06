export default function Header() {
  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-5">
      <div className="flex items-center gap-3">
        <div className="flex size-9 items-center justify-center rounded-lg bg-blue-600 text-lg font-bold text-white">
          S
        </div>
        <h1 className="text-2xl font-bold text-blue-600">SeoulMate</h1>
      </div>

      <button
        type="button"
        className="rounded-full border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700"
      >
        한국어
      </button>
    </header>
  );
}
