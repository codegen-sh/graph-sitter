import {
	ArrowLeft,
	Binary,
	Edit3,
	FileCode2,
	Network,
	Search,
	TerminalSquare,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { Wordmark } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
	title: "CLI reference | Graph-sitter",
	description:
		"High-level graph and codemod commands for inspecting and editing repositories with graph-sitter.",
};

const graphCommands = [
	{
		icon: FileCode2,
		name: "inspect",
		signature: "graph-sitter inspect FILE [PATH]",
		text: "Shows line counts, imports, classes, functions, and per-function call summaries for a file.",
		example:
			"uvx graph-sitter inspect packages/app/src/index.ts ./repo --level calls",
	},
	{
		icon: Search,
		name: "symbols",
		signature: "graph-sitter symbols [QUERY] [PATH]",
		text: "Finds functions, classes, and symbols and prints copyable target strings for later commands.",
		example:
			"uvx graph-sitter symbols runInference ./repo --kind function --backend rust",
	},
	{
		icon: TerminalSquare,
		name: "query",
		signature: "graph-sitter query [PATH]",
		text: "Parses once, keeps the graph in memory, and answers JSONL graph queries over stdin/stdout.",
		example:
			'printf \'{"id":"1","op":"symbols","query":"runInference"}\\n\' | uvx graph-sitter query ./repo',
	},
	{
		icon: TerminalSquare,
		name: "query-server",
		signature: "graph-sitter query-server start [PATH]",
		text: "Starts a local background graph server so agents can query the same in-memory graph across shell commands.",
		example:
			'uvx graph-sitter query-server run ./repo --request \'{"op":"symbols","query":"runInference"}\'',
	},
	{
		icon: Network,
		name: "callgraph",
		signature: "graph-sitter callgraph TARGET [PATH]",
		text: "Traces outbound callees or inbound callers with clean local, resolved, deduped edges by default.",
		example:
			"uvx graph-sitter callgraph packages/app/src/index.ts.main ./repo --depth 2",
	},
	{
		icon: Binary,
		name: "using",
		signature: "graph-sitter using TARGET [PATH]",
		text: "Traces the functions and methods a target calls, recursively up to the requested depth.",
		example:
			"uvx graph-sitter using src/app.py:handler ./repo --depth 3 --resolved-only",
	},
	{
		icon: Network,
		name: "usages",
		signature: "graph-sitter usages TARGET [PATH]",
		text: "Finds callers and usage sites for a target, with optional recursive inbound traversal.",
		example:
			"uvx graph-sitter usages src/app.py:helper ./repo --depth 2 --dedupe",
	},
	{
		icon: Edit3,
		name: "rename",
		signature: "graph-sitter rename TARGET --to NAME [PATH]",
		text: "Applies a graph-aware rename and reports affected files in check mode before writing.",
		example:
			"uvx graph-sitter rename src/app.py:helper ./repo --to execute_helper --check",
	},
];

const parseOptions = [
	["--backend python|rust|auto", "Select the graph backend."],
	["--fallback python|error", "Control behavior when Rust is unavailable."],
	["--language auto|python|typescript", "Set language detection explicitly."],
	["--subdir PATH", "Limit parsing to one or more repo-relative paths."],
	[
		"--format summary|json",
		"Choose human-readable or machine-readable output.",
	],
];

export default function CliReferencePage() {
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
							className="text-muted-foreground hover:text-foreground"
						>
							<Link href="/explore">Explore</Link>
						</Button>
						<ThemeToggle />
					</nav>
				</div>
			</header>

			<main className="flex-1">
				<section className="border-b border-border/60">
					<div className="mx-auto grid w-full max-w-6xl gap-10 px-6 py-12 lg:grid-cols-[0.95fr_1.05fr] lg:px-8 lg:py-16">
						<div>
							<Button asChild variant="ghost" size="sm" className="-ml-3 mb-5">
								<Link href="/">
									<ArrowLeft />
									Home
								</Link>
							</Button>
							<Badge variant="outline" className="gap-1.5">
								<TerminalSquare />
								uvx graph-sitter
							</Badge>
							<h1 className="mt-4 max-w-xl text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
								CLI reference for graph-aware agents.
							</h1>
							<p className="mt-4 max-w-2xl text-base leading-relaxed text-muted-foreground sm:text-lg">
								Use the command line to parse repositories, inspect symbols,
								trace call relationships, and run focused codemods without
								writing a one-off script first.
							</p>
						</div>
						<CodeBlock
							lines={[
								"uvx graph-sitter parse ./repo --format json",
								"uvx graph-sitter query-server start ./repo --backend rust --fallback error",
								'uvx graph-sitter query-server run ./repo --request \'{"op":"symbols","query":"runInference"}\'',
								'printf \'{"id":"1","op":"symbols","query":"runInference"}\\n{"id":"2","op":"exit"}\\n\' | uvx graph-sitter query ./repo',
								"uvx graph-sitter symbols runInference ./repo --backend rust",
								"uvx graph-sitter callgraph src/app.ts.main ./repo --depth 2",
								"uvx graph-sitter rename src/app.py:helper ./repo --to execute_helper --check",
							]}
						/>
					</div>
				</section>

				<section className="mx-auto w-full max-w-6xl px-6 py-12 lg:px-8 lg:py-16">
					<div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
						{graphCommands.map((command) => (
							<article
								key={command.name}
								className="flex min-h-[17rem] flex-col rounded-lg border border-border bg-card p-5"
							>
								<div className="flex items-center gap-2">
									<command.icon className="size-4 text-aura-green" />
									<h2 className="font-mono text-sm font-semibold">
										{command.name}
									</h2>
								</div>
								<code className="mt-4 block text-wrap rounded-md border border-border bg-muted/50 px-3 py-2 font-mono text-xs leading-relaxed text-foreground">
									{command.signature}
								</code>
								<p className="mt-3 flex-1 text-sm leading-relaxed text-muted-foreground">
									{command.text}
								</p>
								<pre className="code-surface mt-4 overflow-x-auto px-3 py-2.5 font-mono text-xs leading-relaxed">
									<code>{command.example}</code>
								</pre>
							</article>
						))}
					</div>
				</section>

				<section className="border-y border-border/60 bg-muted/35">
					<div className="mx-auto grid w-full max-w-6xl gap-10 px-6 py-12 lg:grid-cols-[0.85fr_1.15fr] lg:px-8 lg:py-16">
						<div>
							<h2 className="text-2xl font-semibold tracking-tight">
								Common parse controls
							</h2>
							<p className="mt-3 text-sm leading-relaxed text-muted-foreground">
								These options are shared by the graph commands and make the CLI
								useful on large monorepos.
							</p>
						</div>
						<div className="grid gap-px overflow-hidden rounded-lg border border-border bg-border">
							{parseOptions.map(([option, text]) => (
								<div
									key={option}
									className="grid gap-2 bg-card px-4 py-3 text-sm sm:grid-cols-[17rem_1fr]"
								>
									<code className="font-mono text-aura-purple">{option}</code>
									<span className="text-muted-foreground">{text}</span>
								</div>
							))}
						</div>
					</div>
				</section>

				<section className="mx-auto w-full max-w-6xl px-6 py-12 lg:px-8 lg:py-16">
					<div className="grid gap-8 lg:grid-cols-2">
						<div>
							<h2 className="text-2xl font-semibold tracking-tight">
								Persistent query sessions
							</h2>
							<p className="mt-3 text-sm leading-relaxed text-muted-foreground">
								Use query mode when an agent needs several graph lookups from
								the same repository. The command emits a ready event after the
								initial parse, then returns one JSON response per JSON request.
							</p>
						</div>
						<CodeBlock
							lines={[
								'{"id":"symbols","op":"symbols","query":"runInference","kind":"function"}',
								'{"id":"trace","op":"callgraph","target":"packages/app/src/index.ts.runInference","depth":2}',
								'{"id":"done","op":"exit"}',
							]}
						/>
					</div>
				</section>

				<section className="border-y border-border/60 bg-muted/35">
					<div className="mx-auto grid w-full max-w-6xl gap-10 px-6 py-12 lg:grid-cols-[0.85fr_1.15fr] lg:px-8 lg:py-16">
						<div>
							<h2 className="text-2xl font-semibold tracking-tight">
								Background query server
							</h2>
							<p className="mt-3 text-sm leading-relaxed text-muted-foreground">
								Use server mode when a coding agent needs to query, edit files,
								then query again from separate shell commands. Client requests
								reload automatically when the repository has changed since the
								server parsed it.
							</p>
						</div>
						<CodeBlock
							lines={[
								"uvx graph-sitter query-server start ./repo --language typescript --backend rust --fallback error",
								'uvx graph-sitter query-server run ./repo --request \'{"op":"symbols","query":"runInference","kind":"function"}\'',
								'uvx graph-sitter query-server run ./repo --request \'{"op":"callgraph","target":"packages/app/src/index.ts.runInference","depth":2}\'',
								"uvx graph-sitter query-server status ./repo",
								"uvx graph-sitter query-server stop ./repo",
							]}
						/>
					</div>
				</section>

				<section className="mx-auto w-full max-w-6xl px-6 py-12 lg:px-8 lg:py-16">
					<div className="grid gap-8 lg:grid-cols-2">
						<div>
							<h2 className="text-2xl font-semibold tracking-tight">
								Full-repo TypeScript
							</h2>
							<p className="mt-3 text-sm leading-relaxed text-muted-foreground">
								Use the Rust backend for broad discovery and outbound call graph
								traversal. Scope to a package with the Python backend when you
								need function-level inbound caller recursion.
							</p>
						</div>
						<CodeBlock
							lines={[
								"uvx graph-sitter parse ./monorepo --language typescript --backend rust --fallback error --format json",
								"uvx graph-sitter callgraph packages/app/src/index.ts.main ./monorepo --language typescript --backend rust --depth 2",
								"uvx graph-sitter usages packages/app/src/index.ts.main ./monorepo --language typescript --backend python --subdir packages/app",
							]}
						/>
					</div>
				</section>
			</main>
		</div>
	);
}

function CodeBlock({ lines }: { lines: string[] }) {
	return (
		<div className="dark">
			<div className="overflow-hidden rounded-lg border border-border bg-background shadow-2xl shadow-black/35">
				<div className="flex items-center gap-2 border-b border-border px-4 py-3">
					<TerminalSquare className="size-4 text-aura-green" />
					<span className="font-mono text-xs text-muted-foreground">
						terminal
					</span>
				</div>
				<pre className="overflow-x-auto bg-background px-5 py-4 font-mono text-[0.78rem] leading-[1.9] text-foreground">
					<code>
						{lines.map((line) => (
							<span key={line} className="block">
								<span className="text-muted-foreground">$</span>{" "}
								<span className="text-aura-green">{line.split(" ")[0]}</span>
								{line.slice(line.indexOf(" "))}
							</span>
						))}
					</code>
				</pre>
			</div>
		</div>
	);
}
