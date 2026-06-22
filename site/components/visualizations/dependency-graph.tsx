"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type Simulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum
} from "d3-force";
import { useTheme } from "next-themes";

import { cn } from "@/lib/utils";

export type DepGraphData = {
  meta: {
    source: string;
    parser: string;
    parse_seconds: number;
    files: number;
    modules: number;
    edges: number;
    symbols: number;
  };
  groups: string[];
  nodes: {
    id: string;
    group: string;
    files: number;
    loc: number;
    symbols: number;
    inbound: number;
    outbound: number;
  }[];
  edges: { source: string; target: string; weight: number }[];
};

type GNode = SimulationNodeDatum & DepGraphData["nodes"][number] & { r: number };
type GLink = SimulationLinkDatum<GNode> & { weight: number };

// Aura-derived palette. Core subsystems get semantic Aura colors; the rest
// pull from an extended palette so every group stays distinct.
const GROUP_COLORS: Record<string, string> = {
  server: "#a277ff",
  client: "#82e2ff",
  shared: "#61ffca",
  build: "#ffca85",
  lib: "#f694ff",
  "next-devtools": "#ff6767",
  export: "#b9a3ff",
  pages: "#7ee0ff",
  experimental: "#ffd9a8",
  telemetry: "#c792ea",
  trace: "#89ddff",
  api: "#f78c6c",
  cli: "#addb67",
  diagnostics: "#ff9cac",
  bundles: "#d6bcff",
  bin: "#9aa5ce",
  "(root)": "#7c7a89"
};

const FALLBACK = "#a277ff";

function colorFor(group: string) {
  return GROUP_COLORS[group] ?? FALLBACK;
}

export function DependencyGraph({
  data,
  className
}: {
  data: DepGraphData;
  className?: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme !== "light";

  const [hovered, setHovered] = useState<string | null>(null);
  const [activeGroups, setActiveGroups] = useState<Set<string>>(new Set());

  // Mutable view state lives in refs so the rAF loop never goes stale.
  const view = useRef({ x: 0, y: 0, k: 1 });
  const hoveredRef = useRef<string | null>(null);
  const activeGroupsRef = useRef<Set<string>>(new Set());
  const themeRef = useRef(isDark);
  const tooltip = useRef<{ x: number; y: number } | null>(null);
  const [, force] = useState(0);

  useEffect(() => {
    hoveredRef.current = hovered;
  }, [hovered]);
  useEffect(() => {
    activeGroupsRef.current = activeGroups;
  }, [activeGroups]);
  useEffect(() => {
    themeRef.current = isDark;
  }, [isDark]);

  const { nodes, links, neighbors } = useMemo(() => {
    const maxIn = Math.max(1, ...data.nodes.map((n) => n.inbound));
    const nodes: GNode[] = data.nodes.map((n) => ({
      ...n,
      r: 5 + (24 * Math.sqrt(n.inbound)) / Math.sqrt(maxIn)
    }));
    const links: GLink[] = data.edges.map((e) => ({
      source: e.source,
      target: e.target,
      weight: e.weight
    }));
    const neighbors = new Map<string, Set<string>>();
    for (const n of data.nodes) neighbors.set(n.id, new Set());
    for (const e of data.edges) {
      neighbors.get(e.source)?.add(e.target);
      neighbors.get(e.target)?.add(e.source);
    }
    return { nodes, links, neighbors };
  }, [data]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let width = wrap.clientWidth;
    let height = wrap.clientHeight;
    let dpr = Math.min(window.devicePixelRatio || 1, 2);

    const resize = () => {
      width = wrap.clientWidth;
      height = wrap.clientHeight;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
    };
    resize();

    const sim: Simulation<GNode, GLink> = forceSimulation(nodes)
      .force(
        "link",
        forceLink<GNode, GLink>(links)
          .id((d) => d.id)
          .distance((l) => 70 + 90 / Math.sqrt(l.weight))
          .strength((l) => Math.min(0.7, l.weight / 40))
      )
      .force(
        "charge",
        forceManyBody<GNode>().strength(-420).distanceMax(900)
      )
      .force("collide", forceCollide<GNode>((d) => d.r + 8).iterations(2))
      .force("center", forceCenter(0, 0))
      .force("x", forceX(0).strength(0.03))
      .force("y", forceY(0).strength(0.03))
      .alpha(1)
      .alphaDecay(0.02);

    sim.stop();

    const toWorld = (sx: number, sy: number) => {
      const v = view.current;
      return {
        x: (sx - width / 2 - v.x) / v.k,
        y: (sy - height / 2 - v.y) / v.k
      };
    };

    const nodeAt = (sx: number, sy: number): GNode | null => {
      const w = toWorld(sx, sy);
      let best: GNode | null = null;
      let bestD = Infinity;
      for (const n of nodes) {
        const dx = (n.x ?? 0) - w.x;
        const dy = (n.y ?? 0) - w.y;
        const d = dx * dx + dy * dy;
        const rr = (n.r + 4) * (n.r + 4);
        if (d < rr && d < bestD) {
          bestD = d;
          best = n;
        }
      }
      return best;
    };

    let raf = 0;
    const draw = () => {
      const dark = themeRef.current;
      const v = view.current;
      const hov = hoveredRef.current;
      const groups = activeGroupsRef.current;
      const hl = neighbors.get(hov ?? "");

      ctx.save();
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.scale(dpr, dpr);
      ctx.translate(width / 2 + v.x, height / 2 + v.y);
      ctx.scale(v.k, v.k);

      const dimmed = (id: string, group: string) => {
        if (groups.size > 0 && !groups.has(group)) return true;
        if (hov && id !== hov && !(hl && hl.has(id))) return true;
        return false;
      };

      // Edges
      ctx.lineWidth = 0.6 / v.k;
      for (const l of links) {
        const s = l.source as GNode;
        const t = l.target as GNode;
        if (!s.x || !t.x) continue;
        const sDim = dimmed(s.id, s.group);
        const tDim = dimmed(t.id, t.group);
        const touchesHover = hov && (s.id === hov || t.id === hov);
        if (touchesHover) {
          ctx.strokeStyle = colorFor((s.id === hov ? t : s).group);
          ctx.globalAlpha = 0.55;
          ctx.lineWidth = Math.max(0.8, Math.min(3, l.weight / 18)) / v.k;
        } else if (sDim || tDim) {
          ctx.strokeStyle = dark ? "#edecee" : "#1b1a23";
          ctx.globalAlpha = 0.03;
          ctx.lineWidth = 0.6 / v.k;
        } else {
          ctx.strokeStyle = dark ? "#edecee" : "#1b1a23";
          ctx.globalAlpha = 0.09;
          ctx.lineWidth = 0.6 / v.k;
        }
        ctx.beginPath();
        ctx.moveTo(s.x, s.y!);
        ctx.lineTo(t.x, t.y!);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;

      // Nodes
      for (const n of nodes) {
        if (n.x == null || n.y == null) continue;
        const dim = dimmed(n.id, n.group);
        const c = colorFor(n.group);
        ctx.globalAlpha = dim ? 0.18 : 1;
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        ctx.fillStyle = c;
        ctx.fill();
        ctx.lineWidth = 1.5 / v.k;
        ctx.strokeStyle = dark ? "#15141b" : "#ffffff";
        ctx.stroke();
        if (n.id === hov) {
          ctx.globalAlpha = 1;
          ctx.lineWidth = 2 / v.k;
          ctx.strokeStyle = c;
          ctx.beginPath();
          ctx.arc(n.x, n.y, n.r + 3 / v.k, 0, Math.PI * 2);
          ctx.stroke();
        }
      }

      // Labels — only for prominent or hovered/neighbor nodes
      ctx.globalAlpha = 1;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      const fontPx = Math.max(9, 11 / v.k);
      ctx.font = `${fontPx}px ui-sans-serif, system-ui, sans-serif`;
      for (const n of nodes) {
        if (n.x == null || n.y == null) continue;
        const isHi = n.id === hov || (hl && hl.has(n.id));
        const big = n.r > 12;
        if (!isHi && !big) continue;
        if (groups.size > 0 && !groups.has(n.group)) continue;
        const label = n.id;
        ctx.fillStyle = dark ? "#edecee" : "#1b1a23";
        ctx.globalAlpha = isHi || big ? 0.95 : 0.6;
        ctx.fillText(label, n.x, n.y + n.r + fontPx);
      }

      ctx.restore();
      raf = requestAnimationFrame(draw);
    };

    // Warm up the layout before first paint so it doesn't visibly explode.
    for (let i = 0; i < 220; i++) sim.tick();
    const loop = () => {
      if (sim.alpha() > 0.005) sim.tick();
      draw();
    };
    raf = requestAnimationFrame(function spin() {
      loop();
      raf = requestAnimationFrame(spin);
    });

    // Interactions
    let dragNode: GNode | null = null;
    let panning = false;
    let last = { x: 0, y: 0 };

    const onMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const sx = e.clientX - rect.left;
      const sy = e.clientY - rect.top;
      if (dragNode) {
        const w = toWorld(sx, sy);
        dragNode.fx = w.x;
        dragNode.fy = w.y;
        sim.alpha(0.3).restart();
        tooltip.current = { x: sx, y: sy };
        return;
      }
      if (panning) {
        view.current.x += sx - last.x;
        view.current.y += sy - last.y;
        last = { x: sx, y: sy };
        return;
      }
      const hit = nodeAt(sx, sy);
      canvas.style.cursor = hit ? "pointer" : "grab";
      tooltip.current = hit ? { x: sx, y: sy } : null;
      if ((hit?.id ?? null) !== hoveredRef.current) {
        setHovered(hit?.id ?? null);
        force((n) => n + 1);
      } else if (hit) {
        force((n) => n + 1);
      }
    };

    const onDown = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const sx = e.clientX - rect.left;
      const sy = e.clientY - rect.top;
      const hit = nodeAt(sx, sy);
      if (hit) {
        dragNode = hit;
        hit.fx = hit.x;
        hit.fy = hit.y;
        sim.alphaTarget(0.3).restart();
        canvas.style.cursor = "grabbing";
      } else {
        panning = true;
        last = { x: sx, y: sy };
        canvas.style.cursor = "grabbing";
      }
    };

    const onUp = () => {
      if (dragNode) {
        dragNode.fx = null;
        dragNode.fy = null;
        sim.alphaTarget(0);
      }
      dragNode = null;
      panning = false;
      canvas.style.cursor = "grab";
    };

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const sx = e.clientX - rect.left;
      const sy = e.clientY - rect.top;
      const v = view.current;
      const factor = Math.exp(-e.deltaY * 0.0015);
      const k = Math.max(0.3, Math.min(4, v.k * factor));
      const wx = (sx - width / 2 - v.x) / v.k;
      const wy = (sy - height / 2 - v.y) / v.k;
      v.k = k;
      v.x = sx - width / 2 - wx * k;
      v.y = sy - height / 2 - wy * k;
    };

    const onLeave = () => {
      tooltip.current = null;
      setHovered(null);
    };

    canvas.addEventListener("mousemove", onMove);
    canvas.addEventListener("mousedown", onDown);
    window.addEventListener("mouseup", onUp);
    canvas.addEventListener("wheel", onWheel, { passive: false });
    canvas.addEventListener("mouseleave", onLeave);

    const ro = new ResizeObserver(resize);
    ro.observe(wrap);

    return () => {
      cancelAnimationFrame(raf);
      sim.stop();
      canvas.removeEventListener("mousemove", onMove);
      canvas.removeEventListener("mousedown", onDown);
      window.removeEventListener("mouseup", onUp);
      canvas.removeEventListener("wheel", onWheel);
      canvas.removeEventListener("mouseleave", onLeave);
      ro.disconnect();
    };
  }, [nodes, links, neighbors]);

  const hoveredNode = hovered
    ? data.nodes.find((n) => n.id === hovered)
    : null;

  const toggleGroup = (g: string) => {
    setActiveGroups((prev) => {
      const next = new Set(prev);
      if (next.has(g)) next.delete(g);
      else next.add(g);
      return next;
    });
  };

  return (
    <div className={cn("not-prose", className)}>
      <div className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 border-b border-border px-4 py-2.5 text-xs text-muted-foreground">
          <span className="font-medium text-foreground">{data.meta.source}</span>
          <span>{data.meta.modules} modules</span>
          <span>{data.meta.edges} import edges</span>
          <span>{data.meta.files.toLocaleString()} files</span>
          <span className="text-aura-green">
            parsed in {data.meta.parse_seconds}s
          </span>
        </div>

        <div
          ref={wrapRef}
          className="relative h-[34rem] w-full bg-[radial-gradient(circle_at_center,rgba(162,119,255,0.05),transparent_70%)]"
        >
          <canvas ref={canvasRef} className="block touch-none" />

          {hoveredNode ? (
            <div
              className="pointer-events-none absolute z-10 w-56 rounded-lg border border-border bg-popover/95 p-3 text-xs shadow-xl backdrop-blur"
              style={{
                left: Math.min(
                  (tooltip.current?.x ?? 0) + 14,
                  (wrapRef.current?.clientWidth ?? 0) - 232
                ),
                top: (tooltip.current?.y ?? 0) + 14
              }}
            >
              <div className="mb-1.5 flex items-center gap-2">
                <span
                  className="size-2.5 rounded-full"
                  style={{ background: colorFor(hoveredNode.group) }}
                />
                <span className="font-mono font-medium text-foreground">
                  {hoveredNode.id}
                </span>
              </div>
              <dl className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-muted-foreground">
                <dt>Imported by</dt>
                <dd className="text-right font-medium text-foreground">
                  {hoveredNode.inbound}
                </dd>
                <dt>Imports out</dt>
                <dd className="text-right font-medium text-foreground">
                  {hoveredNode.outbound}
                </dd>
                <dt>Files</dt>
                <dd className="text-right font-medium text-foreground">
                  {hoveredNode.files}
                </dd>
                <dt>Symbols</dt>
                <dd className="text-right font-medium text-foreground">
                  {hoveredNode.symbols.toLocaleString()}
                </dd>
                <dt>Lines</dt>
                <dd className="text-right font-medium text-foreground">
                  {hoveredNode.loc.toLocaleString()}
                </dd>
              </dl>
            </div>
          ) : null}

          <div className="pointer-events-none absolute bottom-3 left-3 select-none text-[0.7rem] text-muted-foreground">
            scroll to zoom · drag a node · drag canvas to pan
          </div>
        </div>

        <div className="flex flex-wrap gap-1.5 border-t border-border px-4 py-3">
          {data.groups.map((g) => {
            const on = activeGroups.size === 0 || activeGroups.has(g);
            return (
              <button
                key={g}
                type="button"
                onClick={() => toggleGroup(g)}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors",
                  on
                    ? "border-border bg-secondary text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                )}
              >
                <span
                  className="size-2 rounded-full"
                  style={{ background: colorFor(g), opacity: on ? 1 : 0.4 }}
                />
                {g}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
