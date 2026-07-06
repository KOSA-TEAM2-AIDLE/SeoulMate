export default function QuestionCard({ question, options, selectedOption, onSelect, disabled = false }) {
  return (
    <section className="rounded-[18px] border border-slate-200 bg-white p-5 shadow-sm">
      <h3 className="text-base font-bold leading-relaxed text-slate-900">{question}</h3>

      <div className="mt-5 space-y-3">
        {options.map((option) => {
          const isSelected = option === selectedOption;

          return (
            <button
              key={option}
              type="button"
              onClick={() => onSelect?.(option)}
              disabled={disabled}
              className={`flex w-full items-center justify-between rounded-xl border px-4 py-3 text-left text-base font-semibold transition ${
                isSelected
                  ? 'border-2 border-blue-600 bg-blue-50 text-blue-600'
                  : 'border-slate-300 bg-white text-slate-600 hover:border-blue-300'
              } disabled:cursor-not-allowed disabled:opacity-70`}
            >
              <span>{option}</span>
              {isSelected && (
                <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm text-white">
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
