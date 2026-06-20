import { cp, mkdir, rm } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const siteRoot = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const repoRoot = path.resolve(siteRoot, "..");
const docsRoot = path.join(repoRoot, "docs");
const publicRoot = path.join(siteRoot, "public");

await mkdir(publicRoot, { recursive: true });

await rm(path.join(publicRoot, "images"), { recursive: true, force: true });
await cp(path.join(docsRoot, "images"), path.join(publicRoot, "images"), {
  recursive: true
});

await cp(path.join(docsRoot, "favicon.svg"), path.join(publicRoot, "favicon.svg"));
