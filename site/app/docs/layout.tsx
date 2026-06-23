import { ChevronRight } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { DocsSidebar } from "@/components/docs-sidebar";
import { Wordmark } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { getDocsNav, getDocsSearchIndex } from "@/lib/docs";

const githubUrl = "https://github.com/codegen-sh/graph-sitter";

export default function DocsLayout({ children }: { children: ReactNode }) {
	const groups = getDocsNav();
	const searchEntries = getDocsSearchIndex();

	return (
		<div className="flex min-h-screen flex-col">
			<header className="sticky top-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur-xl">
				<div className="mx-auto flex h-16 w-full max-w-[90rem] items-center justify-between px-6 lg:px-8">
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
							<Link href="/">Home</Link>
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

			<div className="mx-auto flex w-full max-w-[90rem] flex-1">
				<aside className="hidden w-[17rem] shrink-0 border-r border-border/60 lg:block">
					<div className="sticky top-16 h-[calc(100vh-4rem)] overflow-y-auto px-5 py-7">
						<DocsSidebar groups={groups} searchEntries={searchEntries} />
					</div>
				</aside>

				<main className="min-w-0 flex-1">
					<details className="group border-b border-border/60 px-6 py-3 lg:hidden">
						<summary className="flex cursor-pointer list-none items-center justify-between text-sm font-medium [&::-webkit-details-marker]:hidden">
							Documentation menu
							<ChevronRight className="size-4 text-muted-foreground transition-transform group-open:rotate-90" />
						</summary>
						<div className="mt-5">
							<DocsSidebar groups={groups} searchEntries={searchEntries} />
						</div>
					</details>

					{children}
				</main>
			</div>
		</div>
	);
}
