import type { Metadata } from "next";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Wordmark } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import {
  DependencyGraph,
  type DepGraphData
} from "@/components/visualizations/dependency-graph";
import depGraph from "@/lib/data/nextjs-depgraph.json";

const data = depGraph as DepGraphData;
const githubUrl = "https://github.com/codegen-sh/graph-sitter";

export const metadata: Metadata = {
  title: "The shape of Next.js | Graph-sitter",
  description:
    "An interactive dependency graph of the Next.js framework core, parsed with graph-sitter."
};

const hubs = [...data.nodes].sort((a, b) => b.inbound - a.inbound).slice(0, 6);

export default function ExplorePage() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-6 lg:px-8">
          <Link href="/" aria-label="Graph-sitter home">
            <Wordmark />
          </Link>
          <nav className="flex items-center gap-1">
            <Button
              asChild
              variant="ghost"
              size="sm"
              className="text-muted-foreground hover:text-foreground"
            >
              <Link href="/docs">Docs</Link>
            </Button>
            <Button
              asChild
              variant="ghost"
              size="sm"
              className="hidden text-muted-foreground hover:text-foreground sm:inline-flex"
            >
              <a href={githubUrl} target="_blank" rel="noreferrer">
                GitHub
              </a>
            </Button>
            <ThemeToggle />
          </nav>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-12 lg:px-8 lg:py-16">
        <div className="max-w-2xl">
          <h1 className="text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
            The shape of Next.js
          </h1>
          <p className="mt-3 text-base leading-relaxed text-muted-foreground sm:text-lg">
            Every module in the Next.js framework core, wired by its real import
            graph. Graph-sitter parsed{" "}
            <code className="rounded-md border border-border bg-muted/60 px-1.5 py-0.5 font-mono text-[0.85em] text-foreground">
              packages/next/src
            </code>{" "}
            — {data.meta.files.toLocaleString()} files,{" "}
            {data.meta.symbols.toLocaleString()} symbols — in{" "}
            {data.meta.parse_seconds}s.
          </p>
        </div>

        <div className="mt-8">
          <DependencyGraph data={data} />
        </div>

        <section className="mt-10 grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
          <div>
            <h2 className="text-lg font-semibold tracking-tight">
              Most-depended-on modules
            </h2>
            <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
              Ranked by inbound imports — the modules that the rest of the
              framework leans on hardest.
            </p>
            <ul className="mt-4 overflow-hidden rounded-xl border border-border">
              {hubs.map((n, i) => (
                <li
                  key={n.id}
                  className="flex items-center gap-3 border-b border-border bg-card px-4 py-2.5 text-sm last:border-b-0"
                >
                  <span className="w-4 text-right font-mono text-xs text-muted-foreground">
                    {i + 1}
                  </span>
                  <span className="font-mono text-foreground">{n.id}</span>
                  <span className="ml-auto font-medium text-foreground">
                    {n.inbound}
                  </span>
                  <span className="text-xs text-muted-foreground">imports</span>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h2 className="text-lg font-semibold tracking-tight">
              How this was built
            </h2>
            <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
              No language server, no IDE — just the graph-sitter Rust backend
              resolving imports across the whole tree.
            </p>
            <pre className="code-surface mt-4 overflow-x-auto px-4 py-3.5 font-mono text-[0.8rem] leading-relaxed">
              <code>
                <span className="block">
                  <span className="text-aura-green">uvx</span> graph-sitter parse
                  packages/next/src \
                </span>
                <span className="block pl-[2ch] text-muted-foreground">
                  --backend rust --format json
                </span>
              </code>
            </pre>
            <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
              The resulting graph — {data.meta.modules} modules and{" "}
              {data.meta.edges} aggregated import edges — is laid out live in
              your browser with a force simulation.
            </p>
          </div>
        </section>
      </main>

      <footer className="border-t border-border/60">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-8 text-sm text-muted-foreground lg:px-8">
          <span>Codebase graphs for codemods.</span>
          <Link href="/docs" className="hover:text-foreground">
            Read the docs
          </Link>
        </div>
      </footer>
    </div>
  );
}
