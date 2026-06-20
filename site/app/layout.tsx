import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";

export const metadata: Metadata = {
	title: "Graph-sitter",
	description:
		"Write Python programs that understand and safely edit whole codebases.",
	metadataBase: new URL("https://graph-sitter.com"),
	openGraph: {
		title: "Graph-sitter",
		description:
			"Graph files, symbols, imports, calls, and usages so codebase automation can make targeted edits.",
		url: "https://graph-sitter.com",
		siteName: "Graph-sitter",
		type: "website",
	},
	twitter: {
		card: "summary_large_image",
		title: "Graph-sitter",
		description:
			"Write Python programs that understand and safely edit whole codebases.",
	},
};

export default function RootLayout({
	children,
}: Readonly<{
	children: React.ReactNode;
}>) {
	return (
		<html lang="en" suppressHydrationWarning>
			<body>
				<ThemeProvider
					attribute="class"
					defaultTheme="dark"
					enableSystem={false}
					disableTransitionOnChange
				>
					{children}
				</ThemeProvider>
			</body>
		</html>
	);
}
