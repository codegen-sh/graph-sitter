import { cn } from "@/lib/utils";

export function Logo({ className }: { className?: string }) {
	return (
		<svg
			viewBox="0 0 80.87 80.87"
			className={cn("size-5 text-foreground", className)}
			fill="currentColor"
			aria-hidden="true"
		>
			<path d="M57.34,27.51c-.79.79-.79,2.07,0,2.86l8.64,8.64c.79.79.79,2.07,0,2.86l-8.64,8.64c-.79.79-.79,2.07,0,2.86l4.29,4.29c.79.79,2.07.79,2.86,0l15.79-15.79c.79-.79.79-2.07,0-2.86l-15.79-15.79c-.79-.79-2.07-.79-2.86,0,0,0-4.29,4.29-4.29,4.29Z" />
			<path d="M50.19,60.51c-.79-.79-2.07-.79-2.86,0l-5.47,5.47c-.79.79-2.07.79-2.86,0l-24.12-24.12c-.79-.79-.79-2.07,0-2.86l24.12-24.12c.79-.79,2.07-.79,2.86,0l5.47,5.47c.79.79,2.07.79,2.86,0l4.29-4.29c.79-.79.79-2.07,0-2.86L41.86.59c-.79-.79-2.07-.79-2.86,0L.59,39.01c-.79.79-.79,2.07,0,2.86l38.41,38.41c.79.79,2.07.79,2.86,0l12.62-12.62c.79-.79.79-2.07,0-2.86,0,0-4.29-4.29-4.29-4.29Z" />
			<path d="M50.54,40.44c0,5.58-4.53,10.11-10.11,10.11s-10.11-4.53-10.11-10.11,4.53-10.11,10.11-10.11,10.11,4.53,10.11,10.11Z" />
		</svg>
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
			<span>Graph-sitter</span>
		</span>
	);
}
