import { ArrowRight } from "lucide-react";
import type { Metadata } from "next";
import { MDXRemote } from "next-mdx-remote/rsc";
import Link from "next/link";
import { notFound } from "next/navigation";
import rehypeAutolinkHeadings from "rehype-autolink-headings";
import rehypePrettyCode from "rehype-pretty-code";
import rehypeSlug from "rehype-slug";
import remarkGfm from "remark-gfm";

import { DocsToc } from "@/components/docs-toc";
import { mdxComponents } from "@/components/mdx-components";
import { auraCodeTheme } from "@/lib/aura-code-theme";
import {
	docsHref,
	getDocsPage,
	getDocsStaticParams,
	getHeadings,
	getPrevNext,
} from "@/lib/docs";
import { cn } from "@/lib/utils";

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
