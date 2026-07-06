export default function AssistantMessage({ children }) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[92%] rounded-[22px] border border-slate-200 bg-slate-50 px-5 py-4 text-base font-semibold leading-relaxed text-slate-900 shadow-sm">
        {children}
      </div>
    </div>
  );
}
