"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Search } from "lucide-react";

import { cn } from "@/lib/utils";
import type { DocsSearchEntry } from "@/lib/docs";

export function DocsSearch({ entries }: { entries: DocsSearchEntry[] }) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const normalizedQuery = query.trim().toLowerCase();

  const results = useMemo(() => {
    if (!normalizedQuery) {
      return [];
    }

    return entries
      .filter((entry) => {
        const haystack =
          `${entry.title} ${entry.section} ${entry.description ?? ""}`.toLowerCase();
        return haystack.includes(normalizedQuery);
      })
      .slice(0, 8);
  }, [entries, normalizedQuery]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        inputRef.current?.focus();
      }
      if (event.key === "Escape") {
        setQuery("");
        setOpen(false);
        inputRef.current?.blur();
      }
    };

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="relative">
      <div className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 transition-colors focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/30">
        <Search className="size-4 shrink-0 text-muted-foreground" />
        <input
          ref={inputRef}
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => window.setTimeout(() => setOpen(false), 120)}
          placeholder="Search docs"
          type="search"
          className="h-9 w-full min-w-0 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground [&::-webkit-search-cancel-button]:appearance-none"
        />
        <kbd className="pointer-events-none hidden h-5 select-none items-center gap-0.5 rounded border border-border bg-muted px-1.5 font-mono text-[0.65rem] font-medium text-muted-foreground sm:inline-flex">
          ⌘K
        </kbd>
      </div>

      {open && normalizedQuery ? (
        <div className="absolute left-0 right-0 top-[calc(100%+0.5rem)] z-40 overflow-hidden rounded-lg border border-border bg-popover p-1.5 shadow-xl shadow-black/20">
          {results.length > 0 ? (
            results.map((entry) => (
              <a
                key={entry.href}
                href={entry.href}
                className={cn(
                  "block rounded-md px-2.5 py-2 transition-colors",
                  "hover:bg-accent"
                )}
              >
                <span className="block text-sm font-medium text-foreground">
                  {entry.title}
                </span>
                <span className="block text-xs text-muted-foreground">
                  {entry.section}
                </span>
              </a>
            ))
          ) : (
            <p className="px-2.5 py-2 text-sm text-muted-foreground">
              No matching docs.
            </p>
          )}
        </div>
      ) : null}
    </div>
  );
}
