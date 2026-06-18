use graph_sitter_engine::index_python_path;
use std::env;
use std::error::Error;
use std::time::Instant;

fn main() -> Result<(), Box<dyn Error>> {
    let mut args = env::args().skip(1);
    let Some(repo_path) = args.next() else {
        eprintln!("usage: cargo run -p graph-sitter-engine --example index_python -- <repo-path> [--json]");
        std::process::exit(2);
    };
    let json = args.any(|arg| arg == "--json");

    let started = Instant::now();
    let index = index_python_path(&repo_path)?;
    let elapsed = started.elapsed();
    let summary = index.summary();

    if json {
        println!(
            "{}",
            serde_json::json!({
                "repo_path": repo_path,
                "wall_seconds": elapsed.as_secs_f64(),
                "summary": summary,
            })
        );
    } else {
        println!("repo: {repo_path}");
        println!("wall: {:.6}s", elapsed.as_secs_f64());
        println!(
            "index: files={} symbols={} classes={} functions={} imports={} bytes={} lines={} files_with_errors={}",
            summary.files,
            summary.symbols,
            summary.classes,
            summary.functions,
            summary.imports,
            summary.bytes,
            summary.lines,
            summary.files_with_errors
        );
    }

    Ok(())
}
