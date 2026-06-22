import { spawnSync } from "node:child_process";

const watchedPaths = [":/site", ":/docs"];
const currentRef = process.env.VERCEL_GIT_COMMIT_SHA || "HEAD";
const previousRef = process.env.VERCEL_GIT_PREVIOUS_SHA;

if (isTruthy(process.env.VERCEL_FORCE_BUILD)) {
	console.log("Vercel build forced by VERCEL_FORCE_BUILD.");
	process.exit(1);
}

const baseRef = pickBaseRef(previousRef);
if (!baseRef) {
	console.log("No previous git ref found; running the Vercel build.");
	process.exit(1);
}

const diff = spawnSync(
	"git",
	["diff", "--quiet", baseRef, currentRef, "--", ...watchedPaths],
	{ stdio: "inherit" },
);

if (diff.status === 0) {
	console.log(`No site/docs changes since ${baseRef}; skipping Vercel build.`);
	process.exit(0);
}

if (diff.status === 1) {
	console.log(
		`Detected site/docs changes since ${baseRef}; running Vercel build.`,
	);
	process.exit(1);
}

console.log("Could not evaluate site/docs diff; running Vercel build.");
process.exit(1);

function pickBaseRef(ref) {
	if (ref && hasCommit(ref)) {
		return ref;
	}

	return hasCommit("HEAD^") ? "HEAD^" : undefined;
}

function hasCommit(ref) {
	const result = spawnSync("git", ["cat-file", "-e", `${ref}^{commit}`], {
		stdio: "ignore",
	});

	return result.status === 0;
}

function isTruthy(value) {
	return /^(1|true|yes)$/iu.test(value ?? "");
}
