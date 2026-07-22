export function LogoMark({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
      <defs>
        <linearGradient id="logoBg" x1="0" y1="0" x2="48" y2="48" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#6D5BD0" />
          <stop offset="1" stopColor="#E8BD5C" />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="46" height="46" rx="11" fill="url(#logoBg)" />
      <g fill="none" stroke="#ffffff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="24" cy="9" r="1.6" fill="#ffffff" stroke="none" />
        <line x1="24" y1="11" x2="24" y2="30" />
        <line x1="12" y1="15" x2="36" y2="15" />
        <line x1="12" y1="15" x2="8" y2="24" />
        <line x1="36" y1="15" x2="40" y2="24" />
        <path d="M4,24 Q8,31 12,24" />
        <path d="M32,24 Q36,31 40,24" />
        <line x1="24" y1="30" x2="15" y2="36" />
        <line x1="24" y1="30" x2="33" y2="36" />
        <line x1="14" y1="36" x2="34" y2="36" />
      </g>
    </svg>
  );
}
