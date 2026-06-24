import {
	ArrowRight,
	BookOpen,
	Bot,
	Database,
	ExternalLink,
	FolderTree,
	Share2,
	TerminalSquare,
	Trash2,
	TreePine,
} from "lucide-react";
import Link from "next/link";

import { Logo, Wordmark } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";

const docsUrl = "/docs";
const githubUrl = "https://github.com/codegen-sh/graph-sitter";

const pillars = [
	{
		icon: Database,
		tone: "text-aura-purple",
		title: "Fast, in-memory index",
		text: "Parse a whole repository into an in-memory index that captures more than the AST — imports, exports, usages, references, and call relationships.",
	},
	{
		icon: TreePine,
		tone: "text-aura-green",
		title: "Backed by tree-sitter",
		text: "Built on tree-sitter parsing for Python, TypeScript, JavaScript, and React, with the heaviest indexes moving into Rust for scale.",
	},
	{
		icon: Bot,
		tone: "text-aura-blue",
		title: "Optimized for coding agents",
		text: "A clean, scriptable API designed for AI coding agents to explore code and make safe, graph-aware edits without breaking imports.",
	},
];

const useCases = [
	{
		icon: FolderTree,
		tone: "text-aura-purple",
		title: "Large-scale reorganization",
		text: "Restructure directories and move symbols across a codebase while every import and reference is repaired automatically.",
		href: `${docsUrl}/tutorials/organize-your-codebase`,
		cta: "Reorganize a codebase",
	},
	{
		icon: Trash2,
		tone: "text-aura-red",
		title: "Dead code monitoring & deletion",
		text: "Find functions, classes, and imports with no usages across the index, then remove them with confidence in a single pass.",
		href: `${docsUrl}/tutorials/deleting-dead-code`,
		cta: "Delete dead code",
	},
	{
		icon: Share2,
		tone: "text-aura-green",
		title: "Codebase visualization",
		text: "Turn the dependency and call graph into interactive visualizations to understand structure and blast radius before you change it.",
		href: `${docsUrl}/tutorials/codebase-visualization`,
		cta: "Visualize a codebase",
	},
];

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
							<Link href="/cli">CLI</Link>
						</Button>
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
							className="text-muted-foreground hover:text-foreground"
						>
							<Link href="/explore">Explore</Link>
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
					<div
						aria-hidden
						className="pointer-events-none absolute inset-0 -z-10"
					>
						<div className="absolute -top-40 left-1/2 h-[34rem] w-[64rem] -translate-x-1/2 rounded-full bg-primary/10 blur-[130px] dark:bg-primary/20" />
						<div className="absolute right-[-8%] top-1/3 h-72 w-72 rounded-full bg-aura-green/10 blur-[110px]" />
					</div>

					<div className="mx-auto grid w-full max-w-6xl items-center gap-10 px-6 py-16 lg:grid-cols-[1.05fr_1fr] lg:gap-14 lg:px-8 lg:py-24">
						<div>
							<div className="inline-flex items-center gap-2 rounded-full border border-border bg-muted/60 px-3 py-1 text-xs font-medium text-muted-foreground">
								<TreePine className="size-3.5 text-aura-green" />
								Backed by tree-sitter · built for coding agents
							</div>
							<h1 className="mt-5 text-balance text-4xl font-semibold leading-[1.05] tracking-tight sm:text-5xl lg:text-[3.25rem]">
								A fast, in-memory codebase index — beyond the AST.
							</h1>
							<p className="mt-5 max-w-xl text-base leading-relaxed text-muted-foreground sm:text-lg">
								Graph-sitter parses whole repositories into an in-memory index
								of imports, usages, and references — backed by tree-sitter and
								optimized for coding agents that need to analyze and safely
								rewrite code.
							</p>

							<HeroTerminal />

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
						</div>

						<DeadCodeExample />
					</div>
				</section>

				{/* Pillars */}
				<section className="mx-auto w-full max-w-6xl px-6 py-14 lg:px-8 lg:py-16">
					<div className="grid gap-px overflow-hidden rounded-xl border border-border bg-border sm:grid-cols-2 lg:grid-cols-3">
						{pillars.map((item) => (
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

				{/* Use cases */}
				<section className="border-y border-border/60 bg-muted/40">
					<div className="mx-auto w-full max-w-6xl px-6 py-16 lg:px-8 lg:py-20">
						<h2 className="max-w-2xl text-balance text-2xl font-semibold tracking-tight sm:text-3xl">
							What people build with graph-sitter.
						</h2>
						<p className="mt-3 max-w-2xl text-base leading-relaxed text-muted-foreground sm:text-lg">
							Reach for graph-sitter when a change is too mechanical for hands
							and too structural for find-and-replace.
						</p>
						<div className="mt-10 grid gap-5 lg:grid-cols-3">
							{useCases.map((item) => (
								<Link
									key={item.title}
									href={item.href}
									className="group flex flex-col rounded-xl border border-border bg-card p-6 transition-colors hover:border-foreground/20 hover:bg-accent/40"
								>
									<item.icon className={`size-5 ${item.tone}`} />
									<h3 className="mt-4 text-lg font-semibold tracking-tight">
										{item.title}
									</h3>
									<p className="mt-2 flex-1 text-sm leading-relaxed text-muted-foreground">
										{item.text}
									</p>
									<span className="mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-foreground">
										{item.cta}
										<ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
									</span>
								</Link>
							))}
						</div>
					</div>
				</section>

				{/* CLI */}
				<section className="mx-auto w-full max-w-6xl px-6 py-16 lg:px-8 lg:py-20">
					<div className="grid items-center gap-8 lg:grid-cols-[0.9fr_1.1fr] lg:gap-14">
						<div>
							<h2 className="text-balance text-2xl font-semibold tracking-tight sm:text-3xl">
								One command surface:{" "}
								<span className="font-mono">uvx graph-sitter</span>.
							</h2>
							<p className="mt-3 max-w-md text-base leading-relaxed text-muted-foreground sm:text-lg">
								Run it with no install. Start with fast parse summaries, then
								run codemods in explicit check and write modes — with the
								heaviest indexes moving into Rust for scale.
							</p>
							<Button asChild size="lg" variant="outline" className="mt-6">
								<Link href="/cli">
									<TerminalSquare />
									Open CLI reference
								</Link>
							</Button>
						</div>

						<CommandSurface />
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
						<Link href="/cli" className="hover:text-foreground">
							CLI
						</Link>
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

function HeroTerminal() {
	return (
		<div className="dark mt-7">
			<div className="overflow-hidden rounded-xl border border-border bg-background shadow-xl shadow-black/30">
				<div className="flex items-center gap-2 border-b border-border px-4 py-2.5">
					<TerminalSquare className="size-4 text-aura-green" />
					<span className="font-mono text-xs text-muted-foreground">
						uvx graph-sitter
					</span>
				</div>
				<pre className="overflow-x-auto bg-background px-5 py-4 font-mono text-[0.8rem] leading-[1.95] text-foreground">
					<code>
						<span className="block">
							<span className="text-muted-foreground">$</span>{" "}
							<span className="text-aura-green">uvx</span> graph-sitter parse .
						</span>
						<span className="block">
							<span className="text-muted-foreground">$</span>{" "}
							<span className="text-aura-green">uvx</span> graph-sitter
							transform delete_dead_code.py:run .{" "}
							<span className="text-aura-purple">--check</span>
						</span>
						<span className="block">
							<span className="text-muted-foreground">$</span>{" "}
							<span className="text-aura-green">uvx</span> graph-sitter
							transform delete_dead_code.py:run .{" "}
							<span className="text-aura-purple">--write</span>
						</span>
					</code>
				</pre>
			</div>
		</div>
	);
}

function DeadCodeExample() {
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
						delete_dead_code.py
					</span>
					<span className="ml-auto font-mono text-[0.7rem] text-muted-foreground">
						index ready
					</span>
				</div>
				<pre className="overflow-x-auto bg-background px-5 py-5 font-mono text-[0.82rem] leading-[1.9] text-foreground">
					<code>
						<span className="block">
							<span className="text-aura-purple">from</span> graph_sitter{" "}
							<span className="text-aura-purple">import</span>{" "}
							<span className="text-aura-blue">Codebase</span>
						</span>
						<span className="block"> </span>
						<span className="block text-muted-foreground">
							# Parse the repo into a fast, in-memory index
						</span>
						<span className="block">
							codebase <span className="text-muted-foreground">=</span>{" "}
							<span className="text-aura-blue">Codebase</span>(
							<span className="text-aura-green">&quot;./&quot;</span>)
						</span>
						<span className="block"> </span>
						<span className="block text-muted-foreground">
							# Delete functions with no usages anywhere
						</span>
						<span className="block">
							<span className="text-aura-purple">for</span> function{" "}
							<span className="text-aura-purple">in</span> codebase.
							<span className="text-aura-orange">functions</span>:
						</span>
						<span className="block pl-[4ch]">
							<span className="text-aura-purple">if</span>{" "}
							<span className="text-aura-purple">not</span> function.
							<span className="text-aura-orange">usages</span>:
						</span>
						<span className="block pl-[8ch]">
							function.<span className="text-aura-orange">remove</span>()
						</span>
						<span className="block"> </span>
						<span className="block">
							codebase.<span className="text-aura-orange">commit</span>()
						</span>
					</code>
				</pre>
			</div>
		</div>
	);
}

function CommandSurface() {
	return (
		<div className="dark">
			<div className="overflow-hidden rounded-xl border border-border bg-background shadow-2xl shadow-black/40">
				<div className="flex items-center gap-2 border-b border-border px-4 py-3">
					<TerminalSquare className="size-4 text-aura-green" />
					<span className="font-mono text-xs text-muted-foreground">
						parse · transform
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
						<span className="block"> </span>
						<span className="block text-muted-foreground">
							# run a codemod in check mode, then write
						</span>
						<span className="block">
							<span className="text-aura-green">uvx</span> graph-sitter
							transform delete_dead_code.py:run .{" "}
							<span className="text-aura-purple">--check</span>
						</span>
						<span className="block">
							<span className="text-aura-green">uvx</span> graph-sitter
							transform delete_dead_code.py:run .{" "}
							<span className="text-aura-purple">--write</span>
						</span>
					</code>
				</pre>
			</div>
		</div>
	);
}
