/**
 * The YupReserved mark: a ticket stub (the moment a trip becomes real) with a
 * jaali rosette punched through it. The wordmark pairs a soft, slightly
 * wonky "Yup" with a quieter "reserved" — the confident nod, then the promise.
 */
export function Mark({ size = 28, className = "" }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" className={className} aria-hidden>
      <rect x="4" y="10" width="56" height="44" rx="10" fill="var(--sindoor)" />
      <circle cx="4" cy="32" r="7" fill="var(--paper)" />
      <circle cx="60" cy="32" r="7" fill="var(--paper)" />
      <path d="M32 18l3.6 7.2 7.9-1.4-4.3 6.8 4.3 6.8-7.9-1.4L32 43l-3.6-7.2-7.9 1.4 4.3-6.8-4.3-6.8 7.9 1.4z" fill="var(--paper)" />
      <circle cx="32" cy="30.6" r="3.2" fill="var(--sindoor)" />
    </svg>
  );
}

export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <Mark />
      <span className="leading-none">
        <span className="display text-[1.25rem] font-semibold italic text-ink sm:text-[1.45rem]">Yup</span>
        <span className="display-tight text-[1.25rem] font-light text-ink-2 sm:text-[1.45rem]">reserved</span>
      </span>
    </span>
  );
}

/** Rupee-red divider with the jaali star — used between editorial sections */
export function StarRule({ className = "" }: { className?: string }) {
  return (
    <div className={`flex items-center gap-4 text-sindoor ${className}`} aria-hidden>
      <span className="h-px flex-1 bg-line" />
      <svg width="18" height="18" viewBox="0 0 44 44"><path d="M22 4l4 10 10-4-4 10 10 4-10 4 4 10-10-4-4 10-4-10-10 4 4-10L2 22l10-4-4-10 10 4z" fill="currentColor" /></svg>
      <span className="h-px flex-1 bg-line" />
    </div>
  );
}
