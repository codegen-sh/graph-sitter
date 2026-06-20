import {
	AlertTriangle,
	ChevronRight,
	Code2,
	FileText,
	Info,
	Lightbulb,
	Link2,
} from "lucide-react";
import Link from "next/link";
import type { CSSProperties, ComponentProps, ReactNode } from "react";

import { rewriteDocsHref } from "@/lib/docs";
import { cn } from "@/lib/utils";

type ChildrenProps = {
	children?: ReactNode;
};

type AdmonitionKind = "note" | "tip" | "warning" | "info";

const calloutConfig: Record<
	AdmonitionKind,
	{ Icon: typeof Info; accent: string; icon: string; tint: string }
> = {
	note: {
		Icon: Info,
		accent: "border-l-aura-purple",
		icon: "text-aura-purple",
		tint: "bg-aura-purple/5",
	},
	info: {
		Icon: Info,
		accent: "border-l-aura-blue",
		icon: "text-aura-blue",
		tint: "bg-aura-blue/5",
	},
	tip: {
		Icon: Lightbulb,
		accent: "border-l-aura-green",
		icon: "text-aura-green",
		tint: "bg-aura-green/5",
	},
	warning: {
		Icon: AlertTriangle,
		accent: "border-l-aura-orange",
		icon: "text-aura-orange",
		tint: "bg-aura-orange/5",
	},
};

function InternalLink({ href, children, ...props }: ComponentProps<"a">) {
	const rewritten = rewriteDocsHref(href);
	const isExternal = Boolean(rewritten?.startsWith("http"));

	if (!rewritten) {
		return <a {...props}>{children}</a>;
	}

	if (isExternal) {
		return (
			<a href={rewritten} rel="noreferrer" target="_blank" {...props}>
				{children}
			</a>
		);
	}

	return (
		<Link href={rewritten} {...props}>
			{children}
		</Link>
	);
}

function Admonition({
	children,
	kind,
}: ChildrenProps & { kind: AdmonitionKind }) {
	const config = calloutConfig[kind];
	const Icon = config.Icon;

	return (
		<div
			className={cn(
				"my-5 flex gap-3 rounded-lg border border-l-[3px] border-border p-4 text-[0.95rem] leading-relaxed",
				config.accent,
				config.tint,
			)}
		>
			<Icon className={cn("mt-0.5 size-[1.05rem] shrink-0", config.icon)} />
			<div className="min-w-0 [&>:first-child]:mt-0 [&>:last-child]:mb-0">
				{children}
			</div>
		</div>
	);
}

function CardGroup({ children, cols }: ChildrenProps & { cols?: number }) {
	const columns = cols ?? 2;
	return (
		<div
			className={cn(
				"my-6 grid gap-4",
				columns >= 4
					? "sm:grid-cols-2 lg:grid-cols-4"
					: columns === 3
						? "sm:grid-cols-2 lg:grid-cols-3"
						: columns === 1
							? "grid-cols-1"
							: "sm:grid-cols-2",
			)}
		>
			{children}
		</div>
	);
}

function Card({
	children,
	href,
	title,
	img,
}: ChildrenProps & {
	href?: string;
	icon?: string;
	img?: string;
	title?: string;
}) {
	const content = (
		<>
			{img ? (
				<img
					alt=""
					src={img}
					className="aspect-video w-full rounded-lg object-cover"
				/>
			) : null}
			{title ? (
				<span className="flex items-center gap-2 text-[0.95rem] font-semibold text-foreground">
					{href ? <FileText className="size-4 shrink-0 text-primary" /> : null}
					{title}
				</span>
			) : null}
			{children ? (
				<span className="text-sm leading-relaxed text-muted-foreground">
					{children}
				</span>
			) : null}
		</>
	);

	const className =
		"group flex flex-col items-start gap-2 rounded-xl border border-border bg-card p-5 text-foreground no-underline transition-colors hover:border-primary/40";

	if (!href) {
		return <div className={className}>{content}</div>;
	}

	return (
		<InternalLink className={className} href={href}>
			{content}
		</InternalLink>
	);
}

function Frame({ children, caption }: ChildrenProps & { caption?: string }) {
	return (
		<figure className="my-6">
			<div className="overflow-hidden rounded-xl border border-border bg-card">
				{children}
			</div>
			{caption ? (
				<figcaption className="mt-2 text-sm text-muted-foreground">
					{caption}
				</figcaption>
			) : null}
		</figure>
	);
}

function AccordionGroup({ children }: ChildrenProps) {
	return <div className="my-5 space-y-2.5">{children}</div>;
}

function Accordion({ children, title }: ChildrenProps & { title?: string }) {
	return (
		<details className="group rounded-lg border border-border bg-card px-4 py-3 [&[open]]:pb-4">
			<summary className="flex cursor-pointer list-none items-center justify-between gap-3 font-medium text-foreground [&::-webkit-details-marker]:hidden">
				{title}
				<ChevronRight className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-90" />
			</summary>
			<div className="mt-2.5 text-[0.95rem] text-muted-foreground [&>:first-child]:mt-0 [&>:last-child]:mb-0">
				{children}
			</div>
		</details>
	);
}

function CodeGroup({ children }: ChildrenProps) {
	return <div className="my-6 space-y-2">{children}</div>;
}

function Tabs({ children }: ChildrenProps) {
	return <div className="my-6 space-y-5">{children}</div>;
}

function Tab({ children, title }: ChildrenProps & { title?: string }) {
	return (
		<section>
			{title ? (
				<h4 className="mb-2 text-sm font-semibold text-foreground">{title}</h4>
			) : null}
			<div className="[&>:first-child]:mt-0 [&>:last-child]:mb-0">
				{children}
			</div>
		</section>
	);
}

function Steps({ children }: ChildrenProps) {
	return <ol className="docs-steps">{children}</ol>;
}

function Step({ children, title }: ChildrenProps & { title?: string }) {
	return (
		<li>
			{title ? <span className="docs-step-title">{title}</span> : null}
			<div className="text-[0.95rem] [&>:first-child]:mt-0 [&>:last-child]:mb-0">
				{children}
			</div>
		</li>
	);
}

function Update({
	children,
	description,
	label,
}: ChildrenProps & {
	description?: string;
	label?: string;
}) {
	return (
		<article className="my-6 rounded-xl border border-border bg-card p-5">
			<div className="mb-2.5 flex flex-wrap items-baseline gap-2">
				<strong className="font-semibold text-foreground">{label}</strong>
				{description ? (
					<span className="text-sm text-muted-foreground">{description}</span>
				) : null}
			</div>
			<div className="text-[0.95rem] [&>:first-child]:mt-0 [&>:last-child]:mb-0">
				{children}
			</div>
		</article>
	);
}

function ParameterWrapper({ children }: ChildrenProps) {
	return (
		<section className="my-6 rounded-xl border border-border bg-card p-5">
			<h4 className="mt-0 mb-4 text-sm font-semibold text-foreground">
				Parameters
			</h4>
			<div className="space-y-4">{children}</div>
		</section>
	);
}

function Parameter({
	defaultValue,
	description,
	name,
	type,
}: {
	defaultValue?: string;
	description?: string;
	name?: string;
	type?: ReactNode;
}) {
	return (
		<div className="border-t border-border pt-4 first:border-0 first:pt-0">
			<div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
				<code>{name}</code>
				{type ? (
					<span className="text-xs text-muted-foreground">{type}</span>
				) : null}
				<span className="ml-auto text-xs text-muted-foreground">
					{defaultValue ? `default: ${defaultValue}` : "required"}
				</span>
			</div>
			{description ? (
				<p className="mt-1.5 text-sm text-muted-foreground">{description}</p>
			) : null}
		</div>
	);
}

function Return({
	description,
	return_type,
}: {
	description?: string;
	return_type?: ReactNode;
}) {
	return (
		<section className="my-6 rounded-xl border border-border bg-card p-5">
			<h4 className="mt-0 mb-3 text-sm font-semibold text-foreground">
				Returns
			</h4>
			<div className="flex flex-wrap items-baseline gap-2">
				{return_type ? <code>{return_type}</code> : null}
			</div>
			{description ? (
				<p className="mt-1.5 text-sm text-muted-foreground">{description}</p>
			) : null}
		</section>
	);
}

function Attribute({
	description,
	type,
}: {
	description?: string;
	type?: ReactNode;
}) {
	return (
		<div className="my-4 rounded-lg border border-border bg-card p-4">
			<div className="text-sm text-foreground">{type}</div>
			{description ? (
				<p className="mt-1.5 text-sm text-muted-foreground">{description}</p>
			) : null}
		</div>
	);
}

function GithubLinkNote({ link }: { link?: string }) {
	return (
		<Admonition kind="info">
			<p>
				View source on{" "}
				<a href={link} rel="noreferrer" target="_blank">
					GitHub
				</a>
			</p>
		</Admonition>
	);
}

function HorizontalDivider({ light = false }: { light?: boolean }) {
	return <hr className={cn("my-6 border-border", light && "opacity-50")} />;
}

export const mdxComponents = {
	a: InternalLink,
	Accordion,
	AccordionGroup,
	Attribute,
	Card,
	CardGroup,
	Check: (props: ChildrenProps) => <Admonition kind="info" {...props} />,
	CodeGroup,
	Frame,
	GithubLinkNote,
	HorizontalDivider,
	Info: (props: ChildrenProps) => <Admonition kind="info" {...props} />,
	Link: Link2,
	Note: (props: ChildrenProps) => <Admonition kind="note" {...props} />,
	Parameter,
	ParameterWrapper,
	Return,
	Step,
	Steps,
	Tab,
	Tabs,
	Tip: (props: ChildrenProps) => <Admonition kind="tip" {...props} />,
	Update,
	Warning: (props: ChildrenProps) => <Admonition kind="warning" {...props} />,
	img: ({ alt = "", ...props }: ComponentProps<"img">) => (
		// eslint-disable-next-line @next/next/no-img-element
		<img alt={alt} loading="lazy" {...props} />
	),
	ChevronRight,
	Code2,
	Component: ({ children }: ChildrenProps) => (
		<code>{children ?? "Component"}</code>
	),
	Github: ({ children }: ChildrenProps) => <code>{children ?? "GitHub"}</code>,
	Instance: ({ children }: ChildrenProps) => (
		<code>{children ?? "Instance"}</code>
	),
	MyComponent: ({ children }: ChildrenProps) => (
		<code>{children ?? "MyComponent"}</code>
	),
	New: ({ children }: ChildrenProps) => <code>{children ?? "New"}</code>,
	NewFeature: ({ children }: ChildrenProps) => (
		<code>{children ?? "NewFeature"}</code>
	),
	NewUI: ({ children }: ChildrenProps) => <code>{children ?? "NewUI"}</code>,
	Old: ({ children }: ChildrenProps) => <code>{children ?? "Old"}</code>,
	OldFeature: ({ children }: ChildrenProps) => (
		<code>{children ?? "OldFeature"}</code>
	),
	OldUI: ({ children }: ChildrenProps) => <code>{children ?? "OldUI"}</code>,
	T: ({ children }: ChildrenProps) => <code>{children ?? "T"}</code>,
	Type: ({ children }: ChildrenProps) => <code>{children ?? "Type"}</code>,
};
