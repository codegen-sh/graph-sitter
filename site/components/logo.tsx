import { cn } from "@/lib/utils";

export function Logo({ className }: { className?: string }) {
	return (
		<span
			className={cn(
				"inline-flex size-8 items-center justify-center rounded-lg bg-primary/12 text-primary ring-1 ring-inset ring-primary/25",
				className,
			)}
			aria-hidden="true"
		>
			<svg
				aria-hidden="true"
				viewBox="0 0 24 24"
				className="size-[1.05rem]"
				fill="none"
				stroke="currentColor"
				strokeWidth={1.6}
			>
				<path
					d="M7.4 8.4 16 6.2 M7.7 9.9 11.3 15.2 M12.7 15.4 16.6 7.6"
					strokeLinecap="round"
				/>
				<circle cx="6" cy="8" r="2.5" fill="currentColor" stroke="none" />
				<circle cx="17.6" cy="6" r="2" fill="currentColor" stroke="none" />
				<circle cx="12" cy="16.4" r="2.3" fill="currentColor" stroke="none" />
			</svg>
		</span>
	);
}

export function Wordmark({ className }: { className?: string }) {
	return (
		<span
			className={cn(
				"flex items-center gap-2.5 text-[0.98rem] font-semibold tracking-tight",
				className,
			)}
		>
			<Logo />
			<span>graph-sitter</span>
		</span>
	);
}
