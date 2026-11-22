import type { SVGProps } from "react";

const paths = {
  applications: "M4 5h16v15H4z M8 3v4 M16 3v4 M4 10h16 M8 14h3 M8 17h7",
  approvals: "M9 12l2 2 4-4 M12 3l8 4v5c0 5-8 9-8 9s-8-4-8-9V7z",
  evaluations: "M4 20h17 M7 16v-5 M12 16V5 M17 16V8",
  workflow: "M9 3h6v5H9z M3 16h6v5H3z M15 16h6v5h-6z M12 8v4 M6 16v-4h12v4",
  arrow: "M5 12h14 M13 6l6 6-6 6",
  plus: "M12 5v14 M5 12h14",
  search: "M21 21l-5-5 M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0",
  document: "M6 3h8l4 4v14H6z M14 3v5h4 M9 12h6 M9 16h6",
  close: "M6 6l12 12 M6 18L18 6",
  chevron: "M9 5l7 7-7 7",
} as const;
export type IconName = keyof typeof paths;
/** Render the shared icon with accessible native semantics and consistent styling. */
export function Icon({
  name,
  ...props
}: SVGProps<SVGSVGElement> & { name: IconName }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      <path d={paths[name]} />
    </svg>
  );
}
