export interface NavItem { href: string; label: string; hint: string }
export interface NavGroup { section: string; links: NavItem[] }

export const NAV: NavGroup[] = [
  {
    section: "Desk",
    links: [
      { href: "/applications", label: "Today", hint: "What needs attention" },
      { href: "/tracker", label: "Tracker", hint: "Every application by stage" },
      { href: "/applications/new", label: "Add application", hint: "Paste a JD or job URL" },
    ],
  },
  {
    section: "Find",
    links: [
      { href: "/discovery", label: "Discover jobs", hint: "Scan job boards you configure" },
      { href: "/opportunities", label: "Startups & contacts", hint: "Public contact research" },
      { href: "/compare", label: "Compare jobs", hint: "Fit and ATS side by side" },
    ],
  },
  {
    section: "Resume",
    links: [
      { href: "/resume", label: "My resumes", hint: "Masters and tailored versions" },
      { href: "/resume/tailor", label: "Tailor", hint: "Reorder bullets for a JD" },
      { href: "/resume/ats", label: "ATS check", hint: "Score with methodology" },
      { href: "/resume/optimize", label: "ATS optimize", hint: "Iterate toward a target score" },
    ],
  },
  {
    section: "Prepare",
    links: [
      { href: "/applications/interview", label: "Interview prep", hint: "Questions from the JD" },
      { href: "/applications/company", label: "Company research", hint: "Facts from real pages" },
      { href: "/learn", label: "Learning hub", hint: "Study plans for gaps" },
      { href: "/arena", label: "Interview arena", hint: "Scored mock sessions" },
    ],
  },
  {
    section: "Outreach",
    links: [{ href: "/outreach", label: "Email applications", hint: "Drafts you review before sending" }],
  },
];

export const SETTINGS_NAV: NavItem[] = [
  { href: "/profile", label: "Career profile", hint: "Skills, targets, preferences" },
  { href: "/integrations", label: "Integrations", hint: "AI providers and Gmail" },
];

export const ALL_NAV: NavItem[] = [...NAV.flatMap((g) => g.links), ...SETTINGS_NAV];

/** Longest-prefix match; application detail pages belong to the Tracker. */
export function activeHref(pathname: string): string | null {
  const match = ALL_NAV
    .filter((n) => pathname === n.href || pathname.startsWith(n.href + "/"))
    .sort((a, b) => b.href.length - a.href.length)[0];
  if (match?.href === "/applications" && pathname !== "/applications") return "/tracker";
  return match?.href ?? null;
}
