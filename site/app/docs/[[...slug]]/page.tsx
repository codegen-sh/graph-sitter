import { ArrowRight, ChevronRight } from "lucide-react";
import type { Metadata } from "next";
import { MDXRemote } from "next-mdx-remote/rsc";
import Link from "next/link";
import { notFound } from "next/navigation";
import rehypeAutolinkHeadings from "rehype-autolink-headings";
import rehypePrettyCode from "rehype-pretty-code";
import rehypeSlug from "rehype-slug";
import remarkGfm from "remark-gfm";

import { DocsSearch } from "@/components/docs-search";
import { DocsToc } from "@/components/docs-toc";
import { Wordmark } from "@/components/logo";
import { mdxComponents } from "@/components/mdx-components";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { auraCodeTheme } from "@/lib/aura-code-theme";
import {
	type DocsNavItem,
	docsHref,
	getDocsNav,
	getDocsPage,
	getDocsSearchIndex,
	getDocsStaticParams,
	getHeadings,
	getPrevNext,
} from "@/lib/docs";
import { cn } from "@/lib/utils";

const githubUrl = "https://github.com/codegen-sh/graph-sitter";

type DocsPageProps = {
	params: Promise<{
		slug?: string[];
	}>;
};

const shouldPrerenderDocs = process.env.GRAPH_SITTER_PRERENDER_DOCS !== "0";

export function generateStaticParams() {
	return shouldPrerenderDocs ? getDocsStaticParams() : [];
}

export async function generateMetadata({
	params,
}: DocsPageProps): Promise<Metadata> {
	const { slug } = await params;
	const page = getDocsPage(slug);

	if (!page) {
		return {
			title: "Docs | Graph-sitter",
		};
	}

	return {
		title: `${page.title} | Graph-sitter Docs`,
		description: page.description,
	};
}

export default async function DocsPage({ params }: DocsPageProps) {
	const { slug } = await params;
	const page = getDocsPage(slug);

	if (!page) {
		notFound();
	}

	const { previous, next } = getPrevNext(page.slug);
	const headings = page.kind === "mdx" ? getHeadings(page.source) : [];
	const showToc = headings.length >= 2;

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
						<SidebarInner activeSlug={page.slug} />
					</div>
				</aside>

				<main className="min-w-0 flex-1">
					<details className="group border-b border-border/60 px-6 py-3 lg:hidden">
						<summary className="flex cursor-pointer list-none items-center justify-between text-sm font-medium [&::-webkit-details-marker]:hidden">
							Documentation menu
							<ChevronRight className="size-4 text-muted-foreground transition-transform group-open:rotate-90" />
						</summary>
						<div className="mt-5">
							<SidebarInner activeSlug={page.slug} />
						</div>
					</details>

					<div className="mx-auto flex w-full max-w-[70rem] gap-10 px-6 py-12 lg:px-10">
						<article className="min-w-0 max-w-3xl flex-1">
							<div className="mb-8">
								<h1 className="text-balance text-3xl font-semibold tracking-tight sm:text-[2.5rem] sm:leading-[1.1]">
									{page.title}
								</h1>
								{page.description ? (
									<p className="mt-3 text-lg leading-relaxed text-muted-foreground">
										{page.description}
									</p>
								) : null}
							</div>

							{page.kind === "mdx" ? (
								<div className="docs-prose">
									<MDXRemote
										source={page.source}
										components={mdxComponents}
										options={{
											mdxOptions: {
												remarkPlugins: [remarkGfm],
												rehypePlugins: [
													[
														rehypePrettyCode,
														{
															keepBackground: false,
															theme: auraCodeTheme,
														},
													],
													rehypeSlug,
													[rehypeAutolinkHeadings, { behavior: "wrap" }],
												],
											},
										}}
									/>
								</div>
							) : (
								<div className="grid gap-4 sm:grid-cols-2">
									{page.children.map((child) => (
										<Link
											key={child.slug}
											href={child.href}
											className="group flex flex-col gap-2 rounded-xl border border-border bg-card p-5 transition-colors hover:border-primary/40"
										>
											<strong className="font-semibold text-foreground group-hover:text-primary">
												{child.title}
											</strong>
											{child.description ? (
												<span className="line-clamp-3 text-sm leading-relaxed text-muted-foreground">
													{child.description}
												</span>
											) : null}
										</Link>
									))}
								</div>
							)}

							{previous || next ? (
								<nav
									aria-label="Pagination"
									className="mt-14 grid gap-4 border-t border-border pt-8 sm:grid-cols-2"
								>
									{previous ? (
										<PaginationLink
											href={docsHref(previous.slug)}
											title={previous.title}
											direction="previous"
										/>
									) : (
										<span />
									)}
									{next ? (
										<PaginationLink
											href={docsHref(next.slug)}
											title={next.title}
											direction="next"
										/>
									) : (
										<span />
									)}
								</nav>
							) : null}
						</article>

						{showToc ? (
							<aside className="hidden w-56 shrink-0 xl:block">
								<div className="sticky top-16 max-h-[calc(100vh-4rem)] overflow-y-auto py-12">
									<DocsToc headings={headings} />
								</div>
							</aside>
						) : null}
					</div>
				</main>
			</div>
		</div>
	);
}

function SidebarInner({ activeSlug }: { activeSlug: string }) {
	return (
		<>
			<DocsSearch entries={getDocsSearchIndex()} />
			<nav className="mt-6 space-y-7">
				{getDocsNav().map((group) => (
					<div key={group.title}>
						<p className="mb-1.5 px-2.5 text-xs font-semibold text-muted-foreground">
							{group.title}
						</p>
						<ul className="space-y-0.5">
							{group.items.map((item) => (
								<DocsNavListItem
									activeSlug={activeSlug}
									item={item}
									key={item.slug}
								/>
							))}
						</ul>
					</div>
				))}
			</nav>
		</>
	);
}

function isActiveTree(item: DocsNavItem, slug: string): boolean {
	if (item.slug === slug) {
		return true;
	}
	return Boolean(item.children?.some((child) => isActiveTree(child, slug)));
}

function DocsNavListItem({
	activeSlug,
	item,
}: {
	activeSlug: string;
	item: DocsNavItem;
}) {
	const isActive = item.slug === activeSlug;
	const isOpen = isActiveTree(item, activeSlug);

	return (
		<li>
			<Link
				href={item.href}
				className={cn(
					"block rounded-md px-2.5 py-1.5 text-sm transition-colors",
					isActive
						? "bg-primary/10 font-medium text-primary"
						: "text-muted-foreground hover:bg-accent hover:text-foreground",
				)}
			>
				{item.title}
			</Link>
			{item.children && isOpen ? (
				<ul className="mt-0.5 ml-3 space-y-0.5 border-l border-border pl-2">
					{item.children.map((child) => (
						<DocsNavListItem
							activeSlug={activeSlug}
							item={child}
							key={child.slug}
						/>
					))}
				</ul>
			) : null}
		</li>
	);
}

function PaginationLink({
	href,
	title,
	direction,
}: {
	href: string;
	title: string;
	direction: "previous" | "next";
}) {
	const isNext = direction === "next";

	return (
		<Link
			href={href}
			className={cn(
				"group flex flex-col gap-1 rounded-xl border border-border bg-card p-4 transition-colors hover:border-primary/40",
				isNext && "sm:items-end sm:text-right",
			)}
		>
			<span className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
				{!isNext ? <ArrowRight className="size-3.5 rotate-180" /> : null}
				{isNext ? "Next" : "Previous"}
				{isNext ? <ArrowRight className="size-3.5" /> : null}
			</span>
			<span className="font-medium text-foreground group-hover:text-primary">
				{title}
			</span>
		</Link>
	);
}
