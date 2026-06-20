import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { docsNav } from "../../../content/nav";
import {
  docsHref,
  docsPages,
  docsStaticParams,
  getDocsPage,
  type DocsBlock
} from "../../../content/docs/pages";

type DocsPageProps = {
  params: Promise<{
    slug?: string[];
  }>;
};

export const dynamicParams = false;

export function generateStaticParams() {
  return docsStaticParams();
}

export async function generateMetadata({
  params
}: DocsPageProps): Promise<Metadata> {
  const { slug } = await params;
  const page = getDocsPage(slug);
  if (!page) {
    return {
      title: "Docs | Graph-sitter"
    };
  }
  return {
    title: `${page.title} | Graph-sitter Docs`,
    description: page.description
  };
}

export default async function DocsPage({ params }: DocsPageProps) {
  const { slug } = await params;
  const page = getDocsPage(slug);
  if (!page) {
    notFound();
  }

  const pageIndex = docsPages.findIndex((candidate) => candidate.slug === page.slug);
  const previous = pageIndex > 0 ? docsPages[pageIndex - 1] : undefined;
  const next = pageIndex < docsPages.length - 1 ? docsPages[pageIndex + 1] : undefined;

  return (
    <main className="docs-shell">
      <header className="docs-topbar">
        <Link className="brand" href="/">
          <span className="brand-mark" aria-hidden="true">
            GS
          </span>
          <span>Graph-sitter</span>
        </Link>
        <nav className="nav-links" aria-label="Docs links">
          <Link href="/">Landing</Link>
          <Link href="https://github.com/codegen-sh/graph-sitter">GitHub</Link>
        </nav>
      </header>

      <div className="docs-layout">
        <aside className="docs-sidebar" aria-label="Docs navigation">
          {docsNav.map((group) => (
            <section className="docs-nav-group" key={group.title}>
              <h2>{group.title}</h2>
              <ul>
                {group.items.map((item) => (
                  <li key={item.slug}>
                    <Link
                      className={item.slug === page.slug ? "is-active" : undefined}
                      href={docsHref(item.slug)}
                    >
                      {item.title}
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </aside>

        <article className="docs-article">
          <div className="docs-status">{page.status}</div>
          <h1>{page.title}</h1>
          <p className="docs-description">{page.description}</p>

          {page.sections.map((section) => (
            <section className="docs-section" key={section.title}>
              <h2>{section.title}</h2>
              {section.blocks.map((block, index) => (
                <DocsBlockView block={block} key={`${section.title}-${index}`} />
              ))}
            </section>
          ))}

          <nav className="docs-pagination" aria-label="Docs pagination">
            {previous ? (
              <Link href={docsHref(previous.slug)}>
                <span>Previous</span>
                {previous.navTitle ?? previous.title}
              </Link>
            ) : (
              <span />
            )}
            {next ? (
              <Link href={docsHref(next.slug)}>
                <span>Next</span>
                {next.navTitle ?? next.title}
              </Link>
            ) : (
              <span />
            )}
          </nav>
        </article>
      </div>
    </main>
  );
}

function DocsBlockView({ block }: { block: DocsBlock }) {
  if (block.type === "paragraph") {
    return <p>{block.text}</p>;
  }

  if (block.type === "list") {
    return (
      <ul className="docs-list">
        {block.items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    );
  }

  return (
    <pre className="docs-code">
      <code>{block.code}</code>
    </pre>
  );
}
