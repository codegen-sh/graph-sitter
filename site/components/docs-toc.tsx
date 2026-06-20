"use client";

import { useEffect, useState } from "react";

import type { DocsHeading } from "@/lib/docs";
import { cn } from "@/lib/utils";

export function DocsToc({ headings }: { headings: DocsHeading[] }) {
	const [active, setActive] = useState<string>(headings[0]?.id ?? "");

	useEffect(() => {
		const elements = headings
			.map((heading) => document.getElementById(heading.id))
			.filter((el): el is HTMLElement => Boolean(el));

		if (elements.length === 0) {
			return;
		}

		const observer = new IntersectionObserver(
			(entries) => {
				const visible = entries
					.filter((entry) => entry.isIntersecting)
					.sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);

				if (visible[0]) {
					setActive(visible[0].target.id);
				}
			},
			{ rootMargin: "-88px 0px -68% 0px", threshold: [0, 1] },
		);

		elements.forEach((el) => observer.observe(el));
		return () => observer.disconnect();
	}, [headings]);

	if (headings.length < 2) {
		return null;
	}

	return (
		<nav aria-label="On this page" className="text-sm">
			<p className="mb-3 font-semibold text-foreground/90">On this page</p>
			<ul className="border-l border-border">
				{headings.map((heading) => (
					<li key={heading.id}>
						<a
							href={`#${heading.id}`}
							className={cn(
								"-ml-px block border-l border-transparent py-1 pl-4 leading-snug text-muted-foreground transition-colors hover:text-foreground",
								heading.depth === 3 && "pl-7",
								active === heading.id &&
									"border-primary font-medium text-primary",
							)}
						>
							{heading.text}
						</a>
					</li>
				))}
			</ul>
		</nav>
	);
}
