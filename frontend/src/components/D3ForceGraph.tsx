import * as d3 from "d3"
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react"
import { cn } from "@/lib/utils"
import type { GraphLink, GraphNode } from "@/types/contract"

// Node type → shape/color (kept in sync with the legend's shape+color+label triple encoding)
const TYPE_STYLE: Record<
  GraphNode["type"],
  { color: string; shape: "circle" | "square" | "diamond"; r: number }
> = {
  regulation: { color: "#2563eb", shape: "circle", r: 10 },
  jurisdiction: { color: "#16a34a", shape: "square", r: 9 },
  topic: { color: "#ea580c", shape: "diamond", r: 10 },
  source: { color: "#9ca3af", shape: "circle", r: 5 },
}

const LEGEND_ITEMS: { type: GraphNode["type"]; label: string }[] = [
  { type: "regulation", label: "Regulation" },
  { type: "jurisdiction", label: "Jurisdiction" },
  { type: "topic", label: "Topic" },
  { type: "source", label: "source" },
]

type SimNode = GraphNode & d3.SimulationNodeDatum
type SimLink = Omit<GraphLink, "source" | "target"> & d3.SimulationLinkDatum<SimNode>

// After forceLink resolves, link.source/target may already be node objects — normalize to id
function endpointId(end: string | number | SimNode | undefined): string {
  if (end == null) return ""
  return typeof end === "object" ? end.id : String(end)
}

function NodeShape({ type, emphasized }: { type: GraphNode["type"]; emphasized: boolean }) {
  const { color, shape, r } = TYPE_STYLE[type]
  const stroke = emphasized ? "#0f172a" : "none"
  const strokeWidth = emphasized ? 2 : 0
  if (shape === "circle") {
    return <circle r={r} fill={color} stroke={stroke} strokeWidth={strokeWidth} />
  }
  if (shape === "square") {
    return <rect x={-r} y={-r} width={r * 2} height={r * 2} fill={color} stroke={stroke} strokeWidth={strokeWidth} />
  }
  return <polygon points={`0,${-r} ${r},0 0,${r} ${-r},0`} fill={color} stroke={stroke} strokeWidth={strokeWidth} />
}

export interface D3ForceGraphProps {
  nodes: GraphNode[]
  links: GraphLink[]
  onNodeClick: (node: GraphNode) => void
  onNodeHover?: (node: GraphNode | null) => void
  maxNodes?: number
  className?: string
}

export default function D3ForceGraph({
  nodes,
  links,
  onNodeClick,
  onNodeHover,
  maxNodes = 100,
  className,
}: D3ForceGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const zoomGroupRef = useRef<SVGGElement>(null)
  const nodeLayerRef = useRef<SVGGElement>(null)
  const linkLayerRef = useRef<SVGGElement>(null)

  const simulationRef = useRef<d3.Simulation<SimNode, SimLink> | null>(null)
  const nodeElsRef = useRef<SVGGElement[]>([])
  const linkElsRef = useRef<SVGLineElement[]>([])
  const sizeRef = useRef({ width: 0, height: 0 })

  const [size, setSize] = useState({ width: 0, height: 0 })
  const [ready, setReady] = useState(false)
  const [graphData, setGraphData] = useState<{ nodes: SimNode[]; links: SimLink[] }>({
    nodes: [],
    links: [],
  })
  const [highlightId, setHighlightId] = useState<string | null>(null)

  // Click a Regulation → go to detail; click any of the other three types → highlight only one-hop neighbors (no navigation)
  const activate = (n: SimNode) => {
    if (n.type === "regulation") {
      setHighlightId(null)
      onNodeClick(n)
    } else {
      setHighlightId((prev) => (prev === n.id ? null : n.id))
    }
  }

  const idToNode = useMemo(() => {
    const m = new Map<string, SimNode>()
    for (const n of graphData.nodes) m.set(n.id, n)
    return m
  }, [graphData.nodes])

  const neighborIds = useMemo(() => {
    if (!highlightId) return null
    const set = new Set<string>([highlightId])
    for (const l of graphData.links) {
      const s = endpointId(l.source)
      const t = endpointId(l.target)
      if (s === highlightId) set.add(t)
      if (t === highlightId) set.add(s)
    }
    return set
  }, [highlightId, graphData.links])

  // Measure container size: fill the parent, height calc(100vh - 260px) / min 480px
  useLayoutEffect(() => {
    const container = containerRef.current
    if (!container) {
      console.log('[D3ForceGraph] No container ref')
      return
    }
    const measure = () => {
      const rect = container.getBoundingClientRect()
      const next = {
        width: Math.max(600, Math.floor(rect.width)), // Ensure minimum width
        height: Math.max(480, Math.floor(rect.height)), // Ensure minimum height
      }
      console.log('[D3ForceGraph] Measured container:', next, 'nodes:', nodes.length, 'ready before:', ready)
      sizeRef.current = next
      setSize(next)
      if (!ready) {
        console.log('[D3ForceGraph] Setting ready=true')
        setReady(true)
      }
    }
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(container)
    return () => ro.disconnect()
  }, [nodes, links, ready])

  // Zoom/pan: pressing a node drags only that node and is not passed to zoom-pan; the wheel always zooms
  useEffect(() => {
    const svg = svgRef.current
    if (!svg) return
    const zoomBehavior = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 8])
      .filter((event) => {
        if (event.type === "wheel") return true
        const target = event.target as Element | null
        return !target?.closest(".node")
      })
      .on("zoom", (event) => {
        zoomGroupRef.current?.setAttribute("transform", event.transform.toString())
      })
    const sel = d3.select(svg).call(zoomBehavior)
    return () => {
      sel.on(".zoom", null)
    }
  }, [])

  // Build the force simulation (once data/size are ready); stop the old sim before teardown/rebuild
  useEffect(() => {
    console.log('[D3ForceGraph] Simulation effect:', { 
      ready, 
      width: sizeRef.current.width, 
      height: sizeRef.current.height, 
      nodes: nodes.length, 
      links: links.length,
      willRun: ready && sizeRef.current.width > 0 && sizeRef.current.height > 0
    })
    if (!ready || sizeRef.current.width === 0 || sizeRef.current.height === 0) {
      console.log('[D3ForceGraph] Skipping simulation - not ready or zero dimensions')
      return
    }

    // ★ d3.forceLink rewrites link.source/target in place from id strings into node objects,
    // so feeding the raw nodes/links would mutate the caller's React state and crash on re-render.
    // All fields are primitives, so a shallow copy is a full deep copy and the original props stay immutable.
    const simNodes: SimNode[] = nodes.map((n) => ({ ...n }))
    const simLinks: SimLink[] = links.map((l) => ({ ...l }))
    const idMap = new Map(simNodes.map((n) => [n.id, n]))

    const collideR = maxNodes > 0 ? Math.max(12, Math.round(1800 / maxNodes)) : 16
    const sim = d3
      .forceSimulation<SimNode, SimLink>(simNodes)
      .force("link", d3.forceLink<SimNode, SimLink>(simLinks).id((d) => d.id).distance(80).strength(0.6))
      .force("charge", d3.forceManyBody().strength(-240))
      .force("center", d3.forceCenter(sizeRef.current.width / 2, sizeRef.current.height / 2))
      .force("collide", d3.forceCollide().radius(collideR))
      .alpha(1)
      .alphaDecay(0.02)  // Slower decay for smoother animation

    // Pre-warm: run simulation for a few ticks before displaying
    for (let i = 0; i < 50; i++) sim.tick()

    sim.on("tick", () => {
      linkElsRef.current.forEach((el, i) => {
        const l = simLinks[i]
        const s = idMap.get(endpointId(l.source))
        const t = idMap.get(endpointId(l.target))
        if (!s || !t) return
        el.setAttribute("x1", String(s.x ?? 0))
        el.setAttribute("y1", String(s.y ?? 0))
        el.setAttribute("x2", String(t.x ?? 0))
        el.setAttribute("y2", String(t.y ?? 0))
      })
      nodeElsRef.current.forEach((el, i) => {
        const n = simNodes[i]
        if (!n) return
        el.setAttribute("transform", `translate(${n.x ?? 0},${n.y ?? 0})`)
      })
    })

    simulationRef.current = sim
    setGraphData({ nodes: simNodes, links: simLinks })

    return () => {
      sim.stop()
      if (simulationRef.current === sim) simulationRef.current = null
    }
  }, [nodes, links, ready, maxNodes])

  // After render, collect node DOM so tick can write positions directly, and bind drag
  useEffect(() => {
    const nodeLayer = nodeLayerRef.current
    const linkLayer = linkLayerRef.current
    if (!nodeLayer || !linkLayer) return
    nodeElsRef.current = Array.from(nodeLayer.querySelectorAll<SVGGElement>("g.node"))
    linkElsRef.current = Array.from(linkLayer.querySelectorAll<SVGLineElement>("line.link"))

    const drag = d3
      .drag<SVGGElement, SimNode>()
      .on("start", (event, d) => {
        if (!event.active) simulationRef.current?.alphaTarget(0.3).restart()
        d.fx = d.x
        d.fy = d.y
      })
      .on("drag", (event, d) => {
        d.fx = event.x
        d.fy = event.y
      })
      .on("end", (event, d) => {
        if (!event.active) simulationRef.current?.alphaTarget(0)
        d.fx = null
        d.fy = null
      })

    nodeElsRef.current.forEach((el, i) => {
      const n = graphData.nodes[i]
      if (n) d3.select(el).datum(n).call(drag)
    })
  }, [graphData])

  // On resize (window zoom) only update the center force and restart, to avoid a rebuild resetting the layout
  useEffect(() => {
    sizeRef.current = { width: size.width, height: size.height }
    const sim = simulationRef.current
    if (!sim || size.width === 0 || size.height === 0) return
    sim.force("center", d3.forceCenter(size.width / 2, size.height / 2))
    sim.alpha(0.3).restart()
  }, [size.width, size.height])

  return (
    <div
      ref={containerRef}
      className={cn("relative w-full h-full overflow-hidden bg-white", className)}
      style={{ minHeight: "480px" }}
    >
      <svg
        ref={svgRef}
        width={size.width}
        height={size.height}
        className="block"
        style={{ touchAction: "none" }}
        onClick={() => setHighlightId(null)}
      >
        <g ref={zoomGroupRef}>
          <g ref={linkLayerRef}>
            {graphData.links.map((l, i) => {
              const s = idToNode.get(endpointId(l.source))
              const t = idToNode.get(endpointId(l.target))
              const linkHi =
                highlightId !== null &&
                (endpointId(l.source) === highlightId || endpointId(l.target) === highlightId)
              const linkDim = neighborIds !== null && !linkHi
              return (
                <line
                  key={i}
                  className="link"
                  x1={s?.x ?? 0}
                  y1={s?.y ?? 0}
                  x2={t?.x ?? 0}
                  y2={t?.y ?? 0}
                  stroke={linkDim ? "#e2e8f0" : linkHi ? "#334155" : "#cbd5e1"}
                  strokeWidth={linkHi ? 2 : 1}
                  strokeOpacity={linkDim ? 0.12 : 1}
                />
              )
            })}
          </g>
          <g ref={nodeLayerRef}>
            {graphData.nodes.map((n) => {
              const dim = neighborIds ? !neighborIds.has(n.id) : false
              const emphasized = neighborIds ? neighborIds.has(n.id) : false
              return (
                <g
                  key={n.id}
                  className="node"
                  tabIndex={0}
                  role="button"
                  aria-label={`${n.type}: ${n.label}`}
                  transform={`translate(${n.x ?? 0},${n.y ?? 0})`}
                  style={{ cursor: "pointer", opacity: dim ? 0.15 : 1 }}
                  onMouseEnter={() => {
                    if (n.type === "regulation") onNodeHover?.(n)
                  }}
                  onMouseLeave={() => {
                    if (n.type === "regulation") onNodeHover?.(null)
                  }}
                  onClick={(e) => {
                    e.stopPropagation()
                    activate(n)
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault()
                      activate(n)
                    }
                  }}
                >
                  <NodeShape type={n.type} emphasized={emphasized} />
                  <text
                    x={0}
                    y={TYPE_STYLE[n.type].r + 14}
                    textAnchor="middle"
                    className="pointer-events-none select-none"
                    fontSize={10}
                    fill={dim ? "#94a3b8" : "#475569"}
                    fontWeight={500}
                  >
                    {n.label.length > 30 ? n.label.slice(0, 27) + '...' : n.label}
                  </text>
                </g>
              )
            })}
          </g>
        </g>
      </svg>

      <div className="absolute left-3 top-3 flex flex-wrap gap-x-4 gap-y-1 rounded-md bg-white/85 p-2 text-xs text-slate-700 shadow-sm backdrop-blur">
        {LEGEND_ITEMS.map((item) => (
          <div key={item.type} className="flex items-center gap-1.5">
            <svg width={16} height={16} viewBox="0 0 16 16" aria-hidden="true">
              <NodeShape type={item.type} emphasized={false} />
            </svg>
            <span>{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
