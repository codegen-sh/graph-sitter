"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { DocsSearch } from "@/components/docs-search";
import type { DocsNavGroup, DocsNavItem, DocsSearchEntry } from "@/lib/docs";
import { cn } from "@/lib/utils";

const DEFAULT_SLUG = "introduction/overview";

function pathnameToSlug(pathname: string | null) {
	if (!pathname || pathname === "/docs" || pathname === "/docs/") {
		return DEFAULT_SLUG;
	}

	return decodeURIComponent(pathname)
		.replace(/^\/docs\//u, "")
		.replace(/\/+$/u, "");
}

export function DocsSidebar({
	groups,
	searchEntries,
}: {
	groups: DocsNavGroup[];
	searchEntries: DocsSearchEntry[];
}) {
	const activeSlug = pathnameToSlug(usePathname());

	return (
		<>
			<DocsSearch entries={searchEntries} />
			<nav className="mt-6 space-y-7">
				{groups.map((group) => (
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
