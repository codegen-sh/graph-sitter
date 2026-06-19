import {
  ArrowRight,
  BookOpen,
  Braces,
  ExternalLink,
  FileCode2,
  GitBranch,
  Network,
  ShieldCheck,
  Sparkles,
  TerminalSquare
} from "lucide-react";

const docsUrl = "https://docs.graph-sitter.com/introduction/getting-started";
const githubUrl = "https://github.com/codegen-sh/graph-sitter";

const graphNodes = [
  { label: "api/user.py", kind: "file", x: 9, y: 18 },
  { label: "UserService", kind: "class", x: 46, y: 13 },
  { label: "create_user()", kind: "function", x: 69, y: 39 },
  { label: "models.ts", kind: "file", x: 15, y: 62 },
  { label: "User", kind: "symbol", x: 45, y: 72 },
  { label: "calls", kind: "usage", x: 77, y: 73 }
];

const capabilities = [
  {
    icon: FileCode2,
    title: "Map the repository",
    text: "Parse Python, TypeScript, JavaScript, and React projects into files, directories, and language-aware symbols."
  },
  {
    icon: GitBranch,
    title: "Follow relationships",
    text: "Connect imports, exports, function calls, usages, and dependencies before touching source text."
  },
  {
    icon: ShieldCheck,
    title: "Edit with context",
    text: "Write codemods and refactors that update related code instead of relying on broad text replacement."
  }
];

const useCases = [
  "delete dead code with usage checks",
  "move symbols while repairing imports",
  "trace API impact across a repo",
  "build custom codebase analytics",
  "prepare targeted transformations"
];

export default function Home() {
  return (
    <main>
      <header className="site-header" aria-label="Primary">
        <a className="brand" href="#top" aria-label="Graph-sitter home">
          <span className="brand-mark" aria-hidden="true">
            <Network size={18} />
          </span>
          <span>Graph-sitter</span>
        </a>
        <nav className="nav-links" aria-label="Site links">
          <a href={docsUrl}>Docs</a>
          <a href={githubUrl}>GitHub</a>
        </nav>
      </header>

      <section className="hero" id="top">
        <div className="hero-copy">
          <p className="eyebrow">Codebase graphs for codemods</p>
          <h1>Write Python programs that understand and edit codebases.</h1>
          <p className="hero-text">
            Graph-sitter parses whole repositories into files, symbols, imports,
            calls, and usages, then gives automation enough structure to query
            relationships and make targeted source edits.
          </p>
          <div className="hero-actions" aria-label="Primary actions">
            <a className="button button-primary" href={docsUrl}>
              <BookOpen size={18} />
              Read the docs
            </a>
            <a className="button button-secondary" href={githubUrl}>
              <ExternalLink size={18} />
              View on GitHub
            </a>
          </div>
        </div>

        <div className="product-visual" aria-label="Codebase graph preview">
          <div className="visual-toolbar">
            <span>repo graph</span>
            <span>relationships indexed</span>
          </div>
          <div className="visual-body">
            <pre aria-label="Graph-sitter Python example">{`from graph_sitter import Codebase

codebase = Codebase("./")

for fn in codebase.functions:
    if not fn.usages:
        fn.remove()

codebase.commit()`}</pre>
            <div className="graph-pane" aria-hidden="true">
              <svg viewBox="0 0 100 90" role="img">
                <path d="M18 26 L48 22 L72 43" />
                <path d="M18 26 L22 66 L49 75 L82 76" />
                <path d="M48 22 L49 75" />
                <path d="M72 43 L82 76" />
              </svg>
              {graphNodes.map((node) => (
                <span
                  className={`graph-node graph-node-${node.kind}`}
                  key={node.label}
                  style={{
                    left: `${node.x}%`,
                    top: `${node.y}%`
                  }}
                >
                  {node.label}
                </span>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="section section-light">
        <div className="section-inner">
          <div className="section-heading">
            <p className="eyebrow">What it gives you</p>
            <h2>A graph-shaped API for codebase automation.</h2>
          </div>
          <div className="capability-grid">
            {capabilities.map((item) => (
              <article className="capability-card" key={item.title}>
                <item.icon size={22} aria-hidden="true" />
                <h3>{item.title}</h3>
                <p>{item.text}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="section section-ink">
        <div className="section-inner split">
          <div>
            <p className="eyebrow">Use it for</p>
            <h2>Programmatic refactors, analysis, and repo maintenance.</h2>
          </div>
          <ul className="use-case-list">
            {useCases.map((item) => (
              <li key={item}>
                <ArrowRight size={17} aria-hidden="true" />
                {item}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="section section-light">
        <div className="section-inner cli-section">
          <div>
            <p className="eyebrow">CLI direction</p>
            <h2>Quick parsing first, guarded transformations next.</h2>
            <p>
              The rewrite branch is shaping a future <code>uvx</code>{" "}
              entrypoint for fast repository summaries and transformation
              workflows. Rust-backed wheels and full parity are still release
              gates, so the stable path remains the documented Python API.
            </p>
          </div>
          <div className="terminal-card" aria-label="Future CLI example">
            <div className="terminal-title">
              <TerminalSquare size={18} />
              Future command surface
            </div>
            <pre>{`uvx graph-sitter parse . \\
  --language auto \\
  --format summary

# next: inspect, check, then write transformations`}</pre>
          </div>
        </div>
      </section>

      <footer className="site-footer">
        <div className="footer-brand">
          <Braces size={18} aria-hidden="true" />
          <span>Graph-sitter</span>
        </div>
        <div className="footer-links">
          <a href={docsUrl}>Docs</a>
          <a href={githubUrl}>GitHub</a>
        </div>
        <Sparkles size={18} aria-hidden="true" />
      </footer>
    </main>
  );
}
