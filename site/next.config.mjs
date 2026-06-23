import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
	outputFileTracingRoot: path.join(__dirname, ".."),
	outputFileTracingIncludes: {
		"/docs/\\[\\[\\.\\.\\.slug\\]\\]": ["../docs/**/*"],
	},
};

export default nextConfig;
