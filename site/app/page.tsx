import Link from "next/link";
import {
  ArrowRight,
  BookOpen,
  Code2,
  ExternalLink,
  FileCode2,
  GitBranch,
  Network,
  ShieldCheck,
  TerminalSquare
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Logo, Wordmark } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";

const docsUrl = "/docs";
const githubUrl = "https://github.com/codegen-sh/graph-sitter";

const capabilities = [
  {
    icon: FileCode2,
    tone: "text-aura-purple",
    title: "Parse real codebases",
    text: "Load Python, TypeScript, JavaScript, and React repositories into files, directories, and language-aware symbols."
  },
  {
    icon: GitBranch,
    tone: "text-aura-green",
    title: "Build the graph",
    text: "Index imports, exports, function calls, references, usages, and dependencies before touching any source text."
  },
  {
    icon: ShieldCheck,
    tone: "text-aura-blue",
    title: "Run guarded codemods",
    text: "Write transformations that move, rename, delete, and rewrite code while keeping the related graph edges in sync."
  }
];

const architecture = [
  {
    icon: Code2,
    tone: "text-aura-purple",
    title: "Python stays the shell",
    text: "The authoring experience remains Python: notebooks, scripts, reusable codemods, and the high-level editable API."
  },
  {
    icon: Network,
    tone: "text-aura-green",
    title: "Rust handles scale",
    text: "The rewrite path moves the massive parse and index data structure into a compact Rust backend for large repositories."
  },
  {
    icon: TerminalSquare,
    tone: "text-aura-blue",
    title: "uvx is the entrypoint",
    text: "The target command is uvx graph-sitter for repository parsing, graph inspection, and guarded transformations."
  }
];

const useCases = [
  "Delete dead code with usage checks",
  "Move symbols while repairing imports",
  "Trace API impact across a repo",
  "Inspect import and reference graphs",
  "Build custom codebase analytics",
  "Run checked codemods before writes"
];

const graphNodes = [
  { label: "user.py", dot: "bg-aura-purple", x: 17, y: 24 },
  { label: "UserService", dot: "bg-aura-blue", x: 63, y: 17 },
  { label: "create_user()", dot: "bg-aura-orange", x: 72, y: 56 },
  { label: "usages", dot: "bg-aura-green", x: 23, y: 72 }
];

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth={2.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

export default function Home() {
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
              <Link href={docsUrl}>Docs</Link>
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
            <Button asChild size="sm" className="ml-1">
              <Link href={docsUrl}>Get started</Link>
            </Button>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        {/* Hero */}
        <section className="relative overflow-hidden border-b border-border/60">
          <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
            <div className="absolute -top-40 left-1/2 h-[34rem] w-[64rem] -translate-x-1/2 rounded-full bg-primary/10 blur-[130px] dark:bg-primary/20" />
            <div className="absolute right-[-8%] top-1/3 h-72 w-72 rounded-full bg-aura-green/10 blur-[110px]" />
          </div>

          <div className="mx-auto grid w-full max-w-6xl items-center gap-10 px-6 py-16 lg:grid-cols-[1.05fr_1fr] lg:gap-14 lg:px-8 lg:py-24">
            <div>
              <h1 className="text-balance text-4xl font-semibold leading-[1.05] tracking-tight sm:text-5xl lg:text-[3.25rem]">
                A codebase graph and codemod library.
              </h1>
              <p className="mt-5 max-w-xl text-base leading-relaxed text-muted-foreground sm:text-lg">
                Graph-sitter lets Python programs parse whole repositories,
                build reference and import graphs, query code relationships, and
                make targeted source edits — with the largest indexes moving
                into Rust for scale.
              </p>
              <div className="mt-7 flex flex-wrap items-center gap-3">
                <Button asChild size="lg">
                  <Link href={docsUrl}>
                    <BookOpen />
                    Read the docs
                  </Link>
                </Button>
                <Button asChild size="lg" variant="outline">
                  <a href={githubUrl} target="_blank" rel="noreferrer">
                    <ExternalLink />
                    View on GitHub
                  </a>
                </Button>
              </div>
              <div className="mt-8 flex items-center gap-3 text-sm text-muted-foreground">
                <code className="rounded-lg border border-border bg-muted/60 px-3 py-1.5 font-mono text-[0.82rem] text-foreground">
                  <span className="text-muted-foreground">$</span> uvx
                  graph-sitter parse .
                </code>
                <span className="hidden sm:inline">parse any repo</span>
              </div>
            </div>

            <ProductVisual />
          </div>
        </section>

        {/* Capabilities */}
        <section className="mx-auto w-full max-w-6xl px-6 py-16 lg:px-8 lg:py-20">
          <h2 className="max-w-2xl text-balance text-2xl font-semibold tracking-tight sm:text-3xl">
            A graph-shaped API for codebase automation.
          </h2>
          <p className="mt-3 max-w-2xl text-base leading-relaxed text-muted-foreground sm:text-lg">
            Everything resolves through one editable model of your repository —
            so analysis and rewrites stay consistent.
          </p>
          <div className="mt-10 grid gap-px overflow-hidden rounded-xl border border-border bg-border sm:grid-cols-2 lg:grid-cols-3">
            {capabilities.map((item) => (
              <div
                key={item.title}
                className="group flex flex-col gap-2.5 bg-card p-6 transition-colors hover:bg-accent/40"
              >
                <div className="flex items-center gap-2.5">
                  <item.icon className={`size-[1.05rem] ${item.tone}`} />
                  <h3 className="text-[0.95rem] font-semibold tracking-tight">
                    {item.title}
                  </h3>
                </div>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {item.text}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* Use cases */}
        <section className="border-y border-border/60 bg-muted/40">
          <div className="mx-auto grid w-full max-w-6xl gap-8 px-6 py-16 lg:grid-cols-[0.85fr_1.15fr] lg:gap-14 lg:px-8 lg:py-20">
            <div>
              <h2 className="text-balance text-2xl font-semibold tracking-tight sm:text-3xl">
                Programmatic refactors, analysis, and repo maintenance.
              </h2>
              <p className="mt-3 max-w-md text-base leading-relaxed text-muted-foreground sm:text-lg">
                Reach for graph-sitter when a change is too mechanical for hands
                and too structural for find-and-replace.
              </p>
            </div>
            <ul className="grid gap-2.5 sm:grid-cols-2">
              {useCases.map((item) => (
                <li
                  key={item}
                  className="flex items-center gap-2.5 rounded-lg border border-border bg-card px-3.5 py-3 text-sm font-medium"
                >
                  <CheckIcon className="size-4 shrink-0 text-aura-green" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* Architecture */}
        <section className="mx-auto w-full max-w-6xl px-6 py-16 lg:px-8 lg:py-20">
          <h2 className="max-w-2xl text-balance text-2xl font-semibold tracking-tight sm:text-3xl">
            Same Python workflow, smaller graph engine.
          </h2>
          <p className="mt-3 max-w-2xl text-base leading-relaxed text-muted-foreground sm:text-lg">
            The resurrection keeps the Python shell intact while moving the
            heavy lifting into Rust.
          </p>
          <div className="mt-10 grid gap-px overflow-hidden rounded-xl border border-border bg-border sm:grid-cols-2 lg:grid-cols-3">
            {architecture.map((item) => (
              <div
                key={item.title}
                className="flex flex-col gap-2.5 bg-card p-6"
              >
                <div className="flex items-center gap-2.5">
                  <item.icon className={`size-[1.05rem] ${item.tone}`} />
                  <h3 className="text-[0.95rem] font-semibold tracking-tight">
                    {item.title}
                  </h3>
                </div>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {item.text}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* CLI */}
        <section className="border-t border-border/60 bg-muted/40">
          <div className="mx-auto grid w-full max-w-6xl items-center gap-8 px-6 py-16 lg:grid-cols-[0.9fr_1.1fr] lg:gap-14 lg:px-8 lg:py-20">
            <div>
              <h2 className="text-balance text-2xl font-semibold tracking-tight sm:text-3xl">
                One command surface for parse, inspect, and transform.
              </h2>
              <p className="mt-3 max-w-md text-base leading-relaxed text-muted-foreground sm:text-lg">
                The release target is{" "}
                <code className="rounded-md border border-border bg-card px-1.5 py-0.5 font-mono text-[0.85em] text-foreground">
                  uvx graph-sitter
                </code>
                : start with fast parse summaries and graph inspection, then run
                codemods in explicit check and write modes.
              </p>
              <div className="mt-6 flex flex-wrap gap-2">
                <Badge
                  variant="outline"
                  className="border-border text-muted-foreground"
                >
                  Branch wheels: Rust parsing
                </Badge>
                <Badge
                  variant="outline"
                  className="border-border text-muted-foreground"
                >
                  Parity &amp; release: in progress
                </Badge>
              </div>
            </div>

            <Terminal />
          </div>
        </section>
      </main>

      <footer className="border-t border-border/60">
        <div className="mx-auto flex w-full max-w-6xl flex-col items-start justify-between gap-6 px-6 py-10 sm:flex-row sm:items-center lg:px-8">
          <div className="flex items-center gap-3">
            <Logo />
            <div className="text-sm">
              <div className="font-semibold">graph-sitter</div>
              <div className="text-muted-foreground">
                Codebase graphs for codemods.
              </div>
            </div>
          </div>
          <nav className="flex items-center gap-6 text-sm text-muted-foreground">
            <Link href={docsUrl} className="hover:text-foreground">
              Docs
            </Link>
            <a
              href={githubUrl}
              target="_blank"
              rel="noreferrer"
              className="hover:text-foreground"
            >
              GitHub
            </a>
          </nav>
        </div>
      </footer>
    </div>
  );
}

function ProductVisual() {
  return (
    <div className="dark relative">
      <div className="overflow-hidden rounded-xl border border-border bg-background shadow-2xl shadow-black/40">
        <div className="flex items-center gap-2 border-b border-border px-4 py-3">
          <span className="flex gap-1.5">
            <span className="size-2.5 rounded-full bg-aura-red/80" />
            <span className="size-2.5 rounded-full bg-aura-orange/80" />
            <span className="size-2.5 rounded-full bg-aura-green/80" />
          </span>
          <span className="ml-2 font-mono text-xs text-muted-foreground">
            codebase.py
          </span>
          <span className="ml-auto font-mono text-[0.7rem] text-muted-foreground">
            graph indexed
          </span>
        </div>

        <div className="grid sm:grid-cols-[1.08fr_0.92fr]">
          <pre className="overflow-x-auto bg-background px-5 py-5 font-mono text-[0.8rem] leading-[1.85] text-foreground">
            <code>
              <span className="block">
                <span className="text-aura-purple">from</span> graph_sitter{" "}
                <span className="text-aura-purple">import</span>{" "}
                <span className="text-aura-blue">Codebase</span>
              </span>
              <span className="block">
                codebase <span className="text-muted-foreground">=</span>{" "}
                <span className="text-aura-blue">Codebase</span>(
                <span className="text-aura-green">&quot;./&quot;</span>)
              </span>
              <span className="block">{" "}</span>
              <span className="block">
                <span className="text-aura-purple">for</span> fn{" "}
                <span className="text-aura-purple">in</span> codebase.
                <span className="text-aura-orange">functions</span>:
              </span>
              <span className="block pl-[4ch]">
                <span className="text-aura-purple">if</span>{" "}
                <span className="text-aura-purple">not</span> fn.
                <span className="text-aura-orange">usages</span>:
              </span>
              <span className="block pl-[8ch]">
                fn.<span className="text-aura-orange">remove</span>()
              </span>
              <span className="block">{" "}</span>
              <span className="block text-muted-foreground">
                # python stays the control plane
              </span>
              <span className="block">
                codebase.<span className="text-aura-orange">commit</span>()
              </span>
            </code>
          </pre>

          <div
            className="relative hidden min-h-[260px] border-t border-border bg-[#100f15] sm:block sm:border-t-0 sm:border-l"
            style={{
              backgroundImage:
                "radial-gradient(rgba(255,255,255,0.05) 1px, transparent 1px)",
              backgroundSize: "22px 22px"
            }}
          >
            <svg
              className="absolute inset-0 h-full w-full text-aura-purple/40"
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
              aria-hidden="true"
            >
              <g
                stroke="currentColor"
                strokeWidth={1}
                fill="none"
                vectorEffect="non-scaling-stroke"
              >
                <path d="M17 24 L63 17" vectorEffect="non-scaling-stroke" />
                <path d="M63 17 L72 56" vectorEffect="non-scaling-stroke" />
                <path d="M17 24 L23 72" vectorEffect="non-scaling-stroke" />
                <path d="M23 72 L72 56" vectorEffect="non-scaling-stroke" />
              </g>
            </svg>
            {graphNodes.map((node) => (
              <span
                key={node.label}
                className="absolute flex -translate-x-1/2 -translate-y-1/2 items-center gap-1.5 rounded-md border border-border bg-card/90 px-2 py-1 font-mono text-[0.65rem] text-foreground shadow-sm backdrop-blur"
                style={{ left: `${node.x}%`, top: `${node.y}%` }}
              >
                <span className={`size-1.5 rounded-full ${node.dot}`} />
                {node.label}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function Terminal() {
  return (
    <div className="dark">
      <div className="overflow-hidden rounded-xl border border-border bg-background shadow-2xl shadow-black/40">
        <div className="flex items-center gap-2 border-b border-border px-4 py-3">
          <TerminalSquare className="size-4 text-aura-green" />
          <span className="font-mono text-xs text-muted-foreground">
            future command surface
          </span>
        </div>
        <pre className="overflow-x-auto bg-background px-5 py-5 font-mono text-[0.8rem] leading-[1.9] text-foreground">
          <code>
            <span className="block">
              <span className="text-aura-green">uvx</span> graph-sitter parse .{" "}
              <span className="text-muted-foreground">\</span>
            </span>
            <span className="block pl-[2ch] text-muted-foreground">
              --language auto --backend rust --format summary
            </span>
            <span className="block">{" "}</span>
            <span className="block">
              <span className="text-aura-green">uvx</span> graph-sitter
              transform ./codemods/rename.py{" "}
              <span className="text-aura-purple">--check</span>
            </span>
            <span className="block">{" "}</span>
            <span className="block text-muted-foreground">
              # branch wheel proof:
            </span>
            <span className="block text-muted-foreground">
              # uvx --from dist/*.whl graph-sitter parse . --backend rust
            </span>
          </code>
        </pre>
      </div>
    </div>
  );
}
