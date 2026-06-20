"use client";

import Link from "next/link";
import { Search } from "lucide-react";
import { useMemo, useState } from "react";
import type { DocsSearchRecord } from "../../content/docs/pages";

type DocsSearchBoxProps = {
  records: DocsSearchRecord[];
};

export function DocsSearchBox({ records }: DocsSearchBoxProps) {
  const [query, setQuery] = useState("");
  const normalizedQuery = query.trim().toLowerCase();

  const results = useMemo(() => {
    if (!normalizedQuery) {
      return [];
    }

    const terms = normalizedQuery.split(/\s+/).filter(Boolean);
    return records
      .map((record) => {
        const haystack = `${record.title} ${record.description} ${record.status} ${record.text}`.toLowerCase();
        const title = record.title.toLowerCase();
        const score = terms.reduce((total, term) => {
          if (title.includes(term)) {
            return total + 4;
          }
          if (haystack.includes(term)) {
            return total + 1;
          }
          return total;
        }, 0);
        return { record, score };
      })
      .filter((result) => result.score > 0)
      .sort((a, b) => b.score - a.score || a.record.title.localeCompare(b.record.title))
      .slice(0, 5)
      .map((result) => result.record);
  }, [normalizedQuery, records]);

  return (
    <section className="docs-search" aria-label="Docs search">
      <label htmlFor="docs-search-input">Search docs</label>
      <div className="docs-search-control">
        <Search size={16} aria-hidden="true" />
        <input
          autoComplete="off"
          id="docs-search-input"
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search setup, uvx, parity..."
          type="search"
          value={query}
        />
      </div>
      {normalizedQuery ? (
        <div className="docs-search-results" role="status">
          {results.length > 0 ? (
            results.map((result) => (
              <Link href={result.href} key={result.slug}>
                <span>{result.title}</span>
                <small>{result.description}</small>
              </Link>
            ))
          ) : (
            <p>No docs matched.</p>
          )}
        </div>
      ) : null}
    </section>
  );
}
