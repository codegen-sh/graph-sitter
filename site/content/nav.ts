import { docsPagesBySlug } from "./docs/pages";

export type DocsNavItem = {
  slug: string;
  title: string;
};

export type DocsNavGroup = {
  title: string;
  items: DocsNavItem[];
};

function navItem(slug: string): DocsNavItem {
  const page = docsPagesBySlug.get(slug);
  if (!page) {
    throw new Error(`Missing docs page for nav slug: ${slug}`);
  }
  return {
    slug,
    title: page.navTitle ?? page.title
  };
}

export const docsNav = [
  {
    title: "Start",
    items: [navItem("overview"), navItem("start/setup")]
  },
  {
    title: "CLI",
    items: [navItem("cli/uvx"), navItem("rust-backend/status")]
  },
  {
    title: "Evidence",
    items: [navItem("correctness/parity"), navItem("benchmarks/large-repos")]
  },
  {
    title: "Languages",
    items: [navItem("typescript/support")]
  }
] satisfies DocsNavGroup[];
