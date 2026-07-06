export default function QuestionCard({ question, options, selectedOption, onSelect, disabled = false }) {
  return (
    <section className="rounded-3xl border border-[#E7EAF2] bg-white p-4 shadow-[0_8px_22px_rgba(15,23,42,0.06)]">
      <h3 className="text-[15px] font-semibold leading-[1.55] text-slate-900">{question}</h3>

      <div className="mt-4 space-y-2.5">
        {options.map((option) => {
          const isSelected = option === selectedOption;

          return (
            <button
              key={option}
              type="button"
              onClick={() => onSelect?.(option)}
              disabled={disabled}
              className={`flex w-full items-center justify-between rounded-2xl border px-3.5 py-2.5 text-left text-[14px] font-medium leading-[1.45] transition ${
                isSelected
                  ? 'border-2 border-[#2F6BFF] bg-blue-50 text-[#2F6BFF]'
                  : 'border-slate-300 bg-white text-slate-600 hover:border-blue-300'
              } disabled:cursor-not-allowed disabled:opacity-70`}
            >
              <span>{option}</span>
              {isSelected && (
                <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-[#2F6BFF] text-xs font-semibold text-white">
                  ✓
                </span>
              )}
            </button>
          );
        })}
      </div>
    </section>
  );
}
