export type DocsBlock =
  | {
      type: "paragraph";
      text: string;
    }
  | {
      type: "list";
      items: string[];
    }
  | {
      type: "code";
      language: "bash" | "python" | "text";
      code: string;
    };

export type DocsSection = {
  title: string;
  blocks: DocsBlock[];
};

export type DocsPage = {
  slug: string;
  title: string;
  navTitle?: string;
  description: string;
  status: string;
  sections: DocsSection[];
};

export type DocsSearchRecord = {
  slug: string;
  href: string;
  title: string;
  description: string;
  status: string;
  text: string;
};

export const docsPages = [
  {
    slug: "overview",
    title: "Graph-sitter Docs",
    navTitle: "Overview",
    description:
      "Graph-sitter is a Python library and CLI for building codebase graphs and running guarded codemods.",
    status: "Vercel docs preview",
    sections: [
      {
        title: "What This Is",
        blocks: [
          {
            type: "paragraph",
            text: "Graph-sitter parses repositories into files, symbols, imports, exports, references, dependencies, and editable code objects. The current resurrection keeps Python as the authoring shell and moves large parse/index data structures into a compact Rust backend for scale."
          },
          {
            type: "list",
            items: [
              "Use Python when you need the full mature API surface.",
              "Use strict Rust mode when you are validating the supported compact backend.",
              "Use check mode before write mode for every codemod workflow."
            ]
          }
        ]
      },
      {
        title: "Current Release Posture",
        blocks: [
          {
            type: "paragraph",
            text: "Rust is still opt-in. Branch-built wheels prove the package shape, CLI entry points, Rust extension, parse summaries, selected TypeScript support, and selected codemod flows. Published-package claims stay gated until uploaded artifacts pass the same clean-environment checks."
          }
        ]
      }
    ]
  },
  {
    slug: "start/setup",
    title: "Setup",
    navTitle: "Setup",
    description:
      "Choose the local checkout, published package, or branch-built wheel workflow.",
    status: "Release-gated guidance",
    sections: [
      {
        title: "Local Source Checkout",
        blocks: [
          {
            type: "code",
            language: "bash",
            code: "uv sync --frozen\nuv run graph-sitter doctor --json\nuv run graph-sitter parse . --language python --backend python --format summary"
          },
          {
            type: "paragraph",
            text: "Use this path while developing Graph-sitter itself or debugging the Python backend."
          }
        ]
      },
      {
        title: "Published Package",
        blocks: [
          {
            type: "code",
            language: "bash",
            code: "uvx --python 3.13 graph-sitter doctor --json\nuvx --python 3.13 graph-sitter parse . --language auto --backend auto --fallback python --format json"
          },
          {
            type: "paragraph",
            text: "This is the target public setup path after release validation. Until then, avoid presenting PyPI-backed Rust commands as proven."
          }
        ]
      },
      {
        title: "Branch-Built Wheel Proof",
        blocks: [
          {
            type: "code",
            language: "bash",
            code: "uv build --wheel\nuvx --python 3.13 --from dist/<wheel>.whl graph-sitter doctor --backend rust --language python --json\nuvx --python 3.13 --from dist/<wheel>.whl graph-sitter parse . --backend rust --fallback error --format json"
          }
        ]
      }
    ]
  },
  {
    slug: "cli/uvx",
    title: "uvx Command Surface",
    navTitle: "uvx",
    description:
      "Run Graph-sitter from a package or wheel in a clean temporary environment.",
    status: "Branch wheel validated",
    sections: [
      {
        title: "Parse",
        blocks: [
          {
            type: "code",
            language: "bash",
            code: "uvx --python 3.13 graph-sitter parse . --language python --format json\nuvx --python 3.13 graph-sitter parse ./repo --language typescript --subdir packages/app --format json"
          },
          {
            type: "paragraph",
            text: "The JSON output includes a schema version, requested backend, actual backend, language, elapsed time, selected subdirectories, graph counts, and fallback disclosure."
          }
        ]
      },
      {
        title: "Transform",
        blocks: [
          {
            type: "code",
            language: "bash",
            code: "uvx --python 3.13 graph-sitter transform ./codemods/rename.py:rename . --check\nuvx --python 3.13 graph-sitter transform ./codemods/rename.py:rename . --write"
          },
          {
            type: "paragraph",
            text: "Run check mode first. Check mode executes in a temporary copy and leaves the target repository untouched; write mode mutates the target."
          }
        ]
      },
      {
        title: "Registered Codemods",
        blocks: [
          {
            type: "code",
            language: "bash",
            code: "uvx --python 3.13 graph-sitter run rename-function ./repo --check\nuvx --python 3.13 graph-sitter run rename-function ./repo --subdir src --check"
          }
        ]
      }
    ]
  },
  {
    slug: "rust-backend/status",
    title: "Rust Backend Status",
    navTitle: "Rust status",
    description:
      "What the compact Rust backend proves today and what remains gated.",
    status: "Opt-in backend",
    sections: [
      {
        title: "How To Read Results",
        blocks: [
          {
            type: "paragraph",
            text: "Strict Rust mode is the proof mode: use --backend rust --fallback error. Compatibility mode can fall back to Python and must not be counted as Rust-backed evidence unless the output says the actual backend was Rust."
          },
          {
            type: "code",
            language: "bash",
            code: "graph-sitter parse . --backend rust --fallback error --format json\ngraph-sitter parse . --backend auto --fallback python --format json"
          }
        ]
      },
      {
        title: "Current Evidence",
        blocks: [
          {
            type: "list",
            items: [
              "Fast parity fixtures cover selected Python and TypeScript file, symbol, import, export, usage, dependency, and mutation behavior.",
              "Pinned Airflow and Next.js checks prove selected large-repo semantic behavior.",
              "Installed-wheel smokes prove CLI entry points, doctor, parse output, transforms, and registered codemods from a clean uvx environment."
            ]
          }
        ]
      }
    ]
  },
  {
    slug: "correctness/parity",
    title: "Correctness And Parity",
    navTitle: "Parity",
    description:
      "Parity with the old backend is evidence, not a universal correctness claim.",
    status: "Conservative release language",
    sections: [
      {
        title: "Current Position",
        blocks: [
          {
            type: "paragraph",
            text: "The Rust backend is tested against the existing Python backend for supported surfaces. That proves compatibility for those workflows, but the old backend itself is not treated as absolutely correct in every case."
          },
          {
            type: "list",
            items: [
              "Use strict Rust mode for benchmarks and release gates.",
              "Use Python fallback when compatibility is more important than proving Rust.",
              "Keep public language scoped to tested surfaces, selected pinned repos, and known gates."
            ]
          }
        ]
      },
      {
        title: "Known Boundary",
        blocks: [
          {
            type: "paragraph",
            text: "The current open gaps are broader TypeScript expression/type coverage and full graph-wide large-repo semantic equality. Those remain pre-default gates."
          }
        ]
      }
    ]
  },
  {
    slug: "benchmarks/large-repos",
    title: "Large-Repo Benchmarks",
    navTitle: "Benchmarks",
    description:
      "Pinned Airflow and Next.js evidence for latency and memory improvements.",
    status: "Pinned branch evidence",
    sections: [
      {
        title: "Pinned Repositories",
        blocks: [
          {
            type: "list",
            items: [
              "Apache Airflow 2.10.5 at b93c3db6b1641b0840bd15ac7d05bc58ff2cccbf.",
              "Next.js v15.0.0 at 51bfe3c1863b191f4b039bc230e8ed5c57b0baf3."
            ]
          }
        ]
      },
      {
        title: "Observed Improvements",
        blocks: [
          {
            type: "paragraph",
            text: "Codebase construction measurements show Airflow at 4.637x faster and 13.031x lower RSS in strict Rust mode, and Next.js at 2.385x faster and 7.112x lower RSS. Installed-wheel uvx parse proofs show larger parse-path wins because they compare strict Rust parse summaries against the Python backend parse path."
          },
          {
            type: "code",
            language: "bash",
            code: "rust-rewrite/tools/check_fast.sh\nrust-rewrite/tools/check_pinned_large_repos.sh\nuv run python rust-rewrite/tools/check_wheel_pinned_typescript_repo.py --compare-python-backend --run-transform-proof"
          }
        ]
      }
    ]
  },
  {
    slug: "typescript/support",
    title: "TypeScript Support",
    navTitle: "TypeScript",
    description:
      "Current TypeScript and JavaScript proof boundaries for the Rust backend.",
    status: "Supported subset",
    sections: [
      {
        title: "Language Mode",
        blocks: [
          {
            type: "paragraph",
            text: "Use --language typescript for current TypeScript, JavaScript, and React/JSX repository proofs. A separate JavaScript selector can be added later if the CLI needs one."
          },
          {
            type: "code",
            language: "bash",
            code: "graph-sitter parse ./next --language typescript --backend rust --fallback error --format json"
          }
        ]
      },
      {
        title: "Current Proofs",
        blocks: [
          {
            type: "list",
            items: [
              "Files, symbols, imports, exports, references, dependencies, subclass edges, function-call records, and Promise-chain records are covered in pinned Next.js checks.",
              "Installed-wheel transform proof renames AppRouterAnnouncer and updates its importing usage while asserting only the expected files changed.",
              "Broader TypeScript expression and type-system parity remains open before default-backend promotion."
            ]
          }
        ]
      }
    ]
  }
] satisfies DocsPage[];

export const docsPagesBySlug = new Map(docsPages.map((page) => [page.slug, page]));

export function docsHref(slug: string) {
  return slug === "overview" ? "/docs" : `/docs/${slug}`;
}

export function normalizeDocsSlug(slug?: string[]) {
  if (!slug || slug.length === 0) {
    return "overview";
  }
  return slug.join("/");
}

export function getDocsPage(slug?: string[]) {
  return docsPagesBySlug.get(normalizeDocsSlug(slug));
}

export function docsStaticParams() {
  return docsPages.map((page) => ({
    slug: page.slug === "overview" ? [] : page.slug.split("/")
  }));
}

export function docsSearchRecords(): DocsSearchRecord[] {
  return docsPages.map((page) => {
    const sectionText = page.sections.flatMap((section) => [
      section.title,
      ...section.blocks.flatMap((block) => {
        if (block.type === "list") {
          return block.items;
        }
        return block.text ?? block.code;
      })
    ]);

    return {
      slug: page.slug,
      href: docsHref(page.slug),
      title: page.title,
      description: page.description,
      status: page.status,
      text: [page.title, page.description, page.status, ...sectionText].join(" ")
    };
  });
}
