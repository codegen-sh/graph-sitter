import fs from "node:fs";
import path from "node:path";
import GithubSlugger from "github-slugger";
import matter from "gray-matter";

export type DocsNavItem = {
	slug: string;
	title: string;
	href: string;
	children?: DocsNavItem[];
};

export type DocsNavGroup = {
	title: string;
	items: DocsNavItem[];
};

export type DocsSearchEntry = {
	title: string;
	href: string;
	section: string;
	description?: string;
};

export type DocsMeta = {
	slug: string;
	title: string;
	navTitle: string;
	href: string;
	section: string;
	description?: string;
};

export type DocsPage =
	| {
			kind: "mdx";
			slug: string;
			title: string;
			description?: string;
			href: string;
			source: string;
	  }
	| {
			kind: "index";
			slug: string;
			title: string;
			description: string;
			href: string;
			children: DocsMeta[];
	  };

type MintPage = string | { group: string; pages?: MintPage[] };

type MintConfig = {
	tabs?: { name: string; url: string }[];
	navigation?: { group: string; pages?: MintPage[] }[];
};

const siteRoot = process.cwd().endsWith("site")
	? process.cwd()
	: path.join(process.cwd(), "site");
const repoRoot = path.resolve(siteRoot, "..");
const docsRoot = path.join(repoRoot, "docs");
const mintPath = path.join(docsRoot, "mint.json");

const linkConstants: Record<string, string> = {
	COMMUNITY_SLACK_URL: "https://community.codegen.com",
	CODEGEN_SDK_GITHUB_URL: "https://github.com/codegen-sh/graph-sitter",
	CODEGEN_SDK_EXAMPLES_GITHUB_URL:
		"https://github.com/codegen-sh/graph-sitter-examples",
	CODEGEN_SYSTEM_PROMPT:
		"https://raw.githubusercontent.com/codegen-sh/graph-sitter/refs/heads/develop/src/codegen/sdk/system-prompt.txt",
};

let mintConfigCache: MintConfig | undefined;
let fileSlugCache: string[] | undefined;
let routeSlugCache: string[] | undefined;
let navCache: DocsNavGroup[] | undefined;
let orderedNavCache: DocsNavItem[] | undefined;
let searchCache: DocsSearchEntry[] | undefined;

export function docsHref(slug: string) {
	const normalized = normalizeSlug(slug);
	return normalized ? `/docs/${normalized}` : "/docs";
}

export function rewriteDocsHref(href?: string) {
	if (!href) {
		return href;
	}

	if (
		href.startsWith("#") ||
		href.startsWith("http://") ||
		href.startsWith("https://") ||
		href.startsWith("mailto:") ||
		href.startsWith("/images/")
	) {
		return href;
	}

	if (href === "/docs" || href.startsWith("/docs/")) {
		return href;
	}

	if (href.startsWith("/")) {
		return `/docs${href}`;
	}

	return href;
}

export function getDocsNav() {
	if (navCache) {
		return navCache;
	}

	navCache = (getMintConfig().navigation ?? [])
		.map((group) => ({
			title: group.group,
			items: (group.pages ?? [])
				.map((page) => toNavItem(page, group.group))
				.filter((item): item is DocsNavItem => Boolean(item)),
		}))
		.filter((group) => group.items.length > 0);

	return navCache;
}

export function getOrderedDocsNavItems() {
	if (orderedNavCache) {
		return orderedNavCache;
	}

	orderedNavCache = getDocsNav().flatMap((group) => flattenNav(group.items));
	return orderedNavCache;
}

export function getDocsSearchIndex() {
	if (searchCache) {
		return searchCache;
	}

	const sectionBySlug = new Map<string, string>();
	for (const group of getDocsNav()) {
		for (const item of flattenNav(group.items)) {
			sectionBySlug.set(item.slug, group.title);
		}
	}

	searchCache = getFileSlugs()
		.map((slug) => getDocsMeta(slug, sectionBySlug.get(slug)))
		.sort((a, b) => a.title.localeCompare(b.title))
		.map((page) => ({
			title: page.title,
			href: page.href,
			section: page.section,
			description: page.description,
		}));

	return searchCache;
}

export function getDocsStaticParams() {
	return getRouteSlugs().map((slug) => ({
		slug: slug ? slug.split("/") : undefined,
	}));
}

export function getDocsPage(parts?: string[]): DocsPage | null {
	const requestedSlug = normalizeSlug((parts ?? []).join("/"));
	const slug = requestedSlug || "introduction/overview";
	const filePath = findDocFile(slug);

	if (filePath) {
		const raw = fs.readFileSync(filePath, "utf8");
		const parsed = matter(raw);
		const title =
			readString(parsed.data.title) ?? titleize(slug.split("/").at(-1) ?? slug);

		return {
			kind: "mdx",
			slug,
			title,
			description: readString(parsed.data.description),
			href: docsHref(requestedSlug),
			source: preprocessMdx(parsed.content),
		};
	}

	if (slug && isDocsDirectory(slug)) {
		const children = getDirectoryChildren(slug);
		if (children.length > 0) {
			return {
				kind: "index",
				slug,
				title: titleize(slug.split("/").at(-1) ?? slug),
				description: `Browse ${titleize(slug.split("/").at(-1) ?? slug)} documentation.`,
				href: docsHref(slug),
				children,
			};
		}
	}

	return null;
}

export function getPrevNext(slug: string) {
	const ordered = getOrderedDocsNavItems().filter((item) => !item.children);
	const index = ordered.findIndex((item) => item.slug === slug);

	return {
		previous: index > 0 ? ordered[index - 1] : undefined,
		next:
			index >= 0 && index < ordered.length - 1 ? ordered[index + 1] : undefined,
	};
}

export type DocsHeading = {
	depth: number;
	text: string;
	id: string;
};

export function getHeadings(source: string): DocsHeading[] {
	const slugger = new GithubSlugger();
	const headings: DocsHeading[] = [];
	let inFence = false;

	for (const raw of source.split("\n")) {
		if (/^\s*(```|~~~)/u.test(raw)) {
			inFence = !inFence;
			continue;
		}
		if (inFence) {
			continue;
		}

		const match = /^(#{1,6})\s+(.+?)\s*#*\s*$/u.exec(raw);
		if (!match) {
			continue;
		}

		const depth = match[1].length;
		const text = cleanHeadingText(match[2]);
		if (!text) {
			continue;
		}

		// Advance the slugger for every heading so duplicate-suffix numbering
		// stays aligned with rehype-slug, but only surface h2/h3 in the TOC.
		const id = slugger.slug(text);
		if (depth >= 2 && depth <= 3) {
			headings.push({ depth, text, id });
		}
	}

	return headings;
}

function cleanHeadingText(value: string) {
	return value
		.replace(/`([^`]+)`/gu, "$1")
		.replace(/\*\*([^*]+)\*\*/gu, "$1")
		.replace(/\*([^*]+)\*/gu, "$1")
		.replace(/\[([^\]]+)\]\([^)]*\)/gu, "$1")
		.replace(/<[^>]+>/gu, "")
		.trim();
}

function getMintConfig() {
	if (!mintConfigCache) {
		mintConfigCache = JSON.parse(
			fs.readFileSync(mintPath, "utf8"),
		) as MintConfig;
	}

	return mintConfigCache;
}

function toNavItem(page: MintPage, section: string): DocsNavItem | null {
	if (typeof page === "string") {
		const slug = normalizeDocSlug(page);
		if (!hasDocsRoute(slug)) {
			return null;
		}

		const meta = getDocsMeta(slug, section);
		return {
			slug,
			title: meta.navTitle,
			href: meta.href,
		};
	}

	const children = (page.pages ?? [])
		.map((child) => toNavItem(child, section))
		.filter((item): item is DocsNavItem => Boolean(item));

	if (children.length === 0) {
		return null;
	}

	const slug = commonSlugPrefix(children.map((child) => child.slug));
	return {
		slug: slug || children[0].slug,
		title: page.group,
		href: slug && hasDocsRoute(slug) ? docsHref(slug) : children[0].href,
		children,
	};
}

function getDocsMeta(slug: string, section?: string): DocsMeta {
	const normalized = normalizeDocSlug(slug);
	const filePath = findDocFile(normalized);
	if (!filePath) {
		const title = titleize(normalized.split("/").at(-1) ?? normalized);
		return {
			slug: normalized,
			title,
			navTitle: title,
			href: docsHref(normalized),
			section: section ?? titleize(normalized.split("/")[0] ?? "Docs"),
		};
	}

	const raw = fs.readFileSync(filePath, "utf8");
	const parsed = matter(raw);
	const title =
		readString(parsed.data.title) ??
		titleize(normalized.split("/").at(-1) ?? normalized);

	return {
		slug: normalized,
		title,
		navTitle: readString(parsed.data.sidebarTitle) ?? title,
		href: docsHref(normalized),
		section: section ?? titleize(normalized.split("/")[0] ?? "Docs"),
		description: readString(parsed.data.description) ?? excerpt(parsed.content),
	};
}

function getFileSlugs() {
	if (fileSlugCache) {
		return fileSlugCache;
	}

	fileSlugCache = walk(docsRoot)
		.filter((file) => /\.(md|mdx)$/u.test(file))
		.map((file) =>
			normalizeDocSlug(
				path.relative(docsRoot, file).replace(/\.(md|mdx)$/u, ""),
			),
		)
		.filter((slug) => !slug.startsWith("snippets/"))
		.sort((a, b) => a.localeCompare(b));

	return fileSlugCache;
}

function getRouteSlugs() {
	if (routeSlugCache) {
		return routeSlugCache;
	}

	const slugs = new Set<string>(["", ...getFileSlugs()]);
	for (const slug of getFileSlugs()) {
		const parts = slug.split("/");
		for (let index = 1; index < parts.length; index += 1) {
			slugs.add(parts.slice(0, index).join("/"));
		}
	}

	routeSlugCache = [...slugs].sort((a, b) => a.localeCompare(b));
	return routeSlugCache;
}

function findDocFile(slug: string) {
	const normalized = normalizeDocSlug(slug);
	const candidates = [
		`${normalized}.mdx`,
		`${normalized}.md`,
		`${normalized}/index.mdx`,
		`${normalized}/index.md`,
	].map((candidate) => path.join(docsRoot, candidate));

	return candidates.find((candidate) => fs.existsSync(candidate)) ?? null;
}

function isDocsDirectory(slug: string) {
	const directory = path.join(docsRoot, slug);
	return fs.existsSync(directory) && fs.statSync(directory).isDirectory();
}

function hasDocsRoute(slug: string) {
	return Boolean(findDocFile(slug)) || isDocsDirectory(slug);
}

function getDirectoryChildren(slug: string): DocsMeta[] {
	const prefix = `${normalizeDocSlug(slug)}/`;
	return getFileSlugs()
		.filter((childSlug) => childSlug.startsWith(prefix))
		.filter((childSlug) => !childSlug.slice(prefix.length).includes("/"))
		.map((childSlug) => getDocsMeta(childSlug))
		.sort((a, b) => a.navTitle.localeCompare(b.navTitle));
}

function preprocessMdx(source: string) {
	let inFence = false;
	let skippingImport = false;
	const lines: string[] = [];

	for (const line of source.split("\n")) {
		if (/^\s*(```|~~~)/u.test(line)) {
			inFence = !inFence;
			lines.push(line);
			continue;
		}

		if (!inFence) {
			if (skippingImport) {
				if (/from\s+["']\/snippets\//u.test(line) || /;\s*$/u.test(line)) {
					skippingImport = false;
				}
				continue;
			}

			const trimmed = line.trim();
			if (
				/^import\s+\{/u.test(trimmed) &&
				(trimmed.includes("/snippets/") || !trimmed.includes(" from "))
			) {
				skippingImport = !/;\s*$/u.test(trimmed);
				continue;
			}
		}

		lines.push(line);
	}

	let transformed = lines.join("\n");
	for (const [name, value] of Object.entries(linkConstants)) {
		transformed = transformed.replace(
			new RegExp(`\\b${name}\\b`, "gu"),
			JSON.stringify(value),
		);
	}

	return transformed;
}

function flattenNav(items: DocsNavItem[]): DocsNavItem[] {
	return items.flatMap((item) => [
		item,
		...(item.children ? flattenNav(item.children) : []),
	]);
}

function walk(directory: string): string[] {
	return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
		const fullPath = path.join(directory, entry.name);
		if (entry.isDirectory()) {
			if (["images", "logo"].includes(entry.name)) {
				return [];
			}
			return walk(fullPath);
		}

		return [fullPath];
	});
}

function normalizeDocSlug(slug: string) {
	return normalizeSlug(slug).replace(/\/index$/u, "");
}

function normalizeSlug(slug: string) {
	return slug.replace(/^\/+|\/+$/gu, "").replace(/\\/gu, "/");
}

function readString(value: unknown) {
	return typeof value === "string" && value.trim() ? value : undefined;
}

function excerpt(content: string) {
	const plain = content
		.replace(/```[\s\S]*?```/gu, " ")
		.replace(/<[^>]+>/gu, " ")
		.replace(/[#*_`[\](){}>-]/gu, " ")
		.replace(/\s+/gu, " ")
		.trim();

	return plain
		? `${plain.slice(0, 180)}${plain.length > 180 ? "..." : ""}`
		: undefined;
}

function titleize(value: string) {
	return value
		.replace(/[-_]/gu, " ")
		.replace(/\b\w/gu, (match) => match.toUpperCase());
}

function commonSlugPrefix(slugs: string[]) {
	if (slugs.length === 0) {
		return "";
	}

	const splitSlugs = slugs.map((slug) => slug.split("/"));
	const prefix: string[] = [];
	for (let index = 0; index < splitSlugs[0].length; index += 1) {
		const part = splitSlugs[0][index];
		if (splitSlugs.every((slug) => slug[index] === part)) {
			prefix.push(part);
		} else {
			break;
		}
	}

	return prefix.join("/");
}
