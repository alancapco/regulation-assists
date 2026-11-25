import * as d3 from "d3"
import { useEffect, useLayoutEffect, useRef, useState } from "react"
import { feature } from "topojson-client"
import type { Topology, GeometryCollection } from "topojson-specification"
import type { FeatureCollection } from "geojson"
import { cn } from "@/lib/utils"
import type { JurisdictionCount } from "@/types/contract"

// Numeric ISO 3166-1 code mapping for major jurisdictions (world-atlas uses numeric codes)
const JURISDICTION_TO_ISO_NUMERIC: Record<string, string> = {
  "United States": "840",
  "United Kingdom": "826",
  "China": "156",
  "Canada": "124",
  "Australia": "036",
  "Singapore": "702",
  "Japan": "392",
  "South Korea": "410",
  "India": "356",
  "Brazil": "076",
  "Germany": "276",
  "France": "250",
  "Italy": "380",
  "Spain": "724",
  "Netherlands": "528",
  "Switzerland": "756",
  "Sweden": "752",
  "Norway": "578",
  "Denmark": "208",
  "Finland": "246",
  "Poland": "616",
  "Belgium": "056",
  "Austria": "040",
  "Ireland": "372",
  "Portugal": "620",
  "Greece": "300",
  "Czech Republic": "203",
  "Romania": "642",
  "Hungary": "348",
  "New Zealand": "554",
  "South Africa": "710",
  "Mexico": "484",
  "Argentina": "032",
  "Chile": "152",
  "Israel": "376",
  "United Arab Emirates": "784",
  "Saudi Arabia": "682",
  "Turkey": "792",
  "Russia": "643",
  "Thailand": "764",
  "Malaysia": "458",
  "Indonesia": "360",
  "Philippines": "608",
  "Vietnam": "704",
  "Pakistan": "586",
  "Egypt": "818",
  "Nigeria": "566",
  "Kenya": "404",
  "Hong Kong": "344",
}

// Reverse mapping: numeric ISO code to jurisdiction name
const ISO_NUMERIC_TO_JURISDICTION: Record<string, string> = Object.fromEntries(
  Object.entries(JURISDICTION_TO_ISO_NUMERIC).map(([jurisdiction, iso]) => [iso, jurisdiction])
)

export interface D3GlobeMapProps {
  countries: JurisdictionCount[]
  className?: string
  onCountryClick?: (countryName: string) => void
}

export default function D3GlobeMap({ countries, className, onCountryClick }: D3GlobeMapProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const [size, setSize] = useState({ width: 0, height: 0 })
  const [ready, setReady] = useState(false)
  const [worldData, setWorldData] = useState<FeatureCollection | null>(null)
  const [hoverCountry, setHoverCountry] = useState<string | null>(null)
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 })
  const rotationRef = useRef<[number, number, number]>([0, -10, 0])
  const [scale, setScale] = useState(250)

  // Build jurisdiction → regulation count map from countries prop
  const countByJurisdiction = new Map<string, number>()
  
  countries.forEach((country) => {
    countByJurisdiction.set(country.jurisdiction, country.count)
  })

  console.log('[D3GlobeMap] Jurisdiction regulation counts:', Object.fromEntries(countByJurisdiction))

  // Load world data
  useEffect(() => {
    fetch("https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json")
      .then((res) => res.json())
      .then((topology: Topology) => {
        const countries = feature(
          topology,
          topology.objects.countries as GeometryCollection
        ) as FeatureCollection
        setWorldData(countries)
      })
      .catch((err) => console.error("Failed to load world data:", err))
  }, [])

  // Measure container
  useLayoutEffect(() => {
    const container = containerRef.current
    if (!container) return
    const measure = () => {
      const rect = container.getBoundingClientRect()
      const next = {
        width: Math.max(600, Math.floor(rect.width)),
        height: Math.max(500, Math.floor(rect.height)),
      }
      setSize(next)
    }
    measure()
    setReady(true)
    const ro = new ResizeObserver(measure)
    ro.observe(container)
    return () => ro.disconnect()
  }, [])

  // Render globe
  useEffect(() => {
    if (!ready || !worldData || size.width === 0 || size.height === 0) return

    const svg = d3.select(svgRef.current)
    svg.selectAll("*").remove()

    const width = size.width
    const height = size.height

    // Color scale: REVERSED - more regulations = DARKER (white → black)
    const maxCount = Math.max(...Array.from(countByJurisdiction.values()), 1)
    console.log(`[D3GlobeMap] Max regulation count: ${maxCount}`)
    
    const colorScale = d3.scaleLinear<string>()
      .domain([0, maxCount])
      .range(["#ffffff", "#000000"])

    // Projection - use persisted rotation and dynamic scale
    const projection = d3.geoOrthographic()
      .scale(scale)
      .translate([width / 2, height / 2])
      .rotate(rotationRef.current)
      .clipAngle(90)

    const path = d3.geoPath(projection)

    // Ocean background - white
    svg.append("circle")
      .attr("cx", width / 2)
      .attr("cy", height / 2)
      .attr("r", scale)
      .attr("fill", "#ffffff")
      .attr("stroke", "#94a3b8")
      .attr("stroke-width", 1.5)

    // Countries
    const countries = svg.append("g")
      .selectAll("path")
      .data(worldData.features)
      .join("path")
      .attr("d", path as any)
      .attr("fill", (d: any) => {
        let count = 0
        
        // Check if any jurisdiction matches this country (d.id is numeric ISO code)
        for (const [jurisdiction, jCount] of countByJurisdiction.entries()) {
          const isoNumeric = JURISDICTION_TO_ISO_NUMERIC[jurisdiction]
          if (isoNumeric && d.id === isoNumeric) {
            count = jCount
            console.log(`[D3GlobeMap] Country ${d.properties?.name} (${d.id}) matched to ${jurisdiction}: ${count} regulations`)
            break
          }
        }
        
        const color = count > 0 ? colorScale(count) : "#f5f5f5"
        if (count > 0) {
          console.log(`[D3GlobeMap] ${d.properties?.name}: count=${count}, color=${color}`)
        }
        return color
      })
      .attr("stroke", "#d1d5db")
      .attr("stroke-width", 0.5)
      .style("cursor", "pointer")
      .on("mouseenter", function(event: any, d: any) {
        const countryName = d.properties?.name
        setHoverCountry(countryName)
        setMousePos({ x: event.pageX, y: event.pageY })
        d3.select(this)
          .attr("stroke", "#0f172a")
          .attr("stroke-width", 2)
      })
      .on("mousemove", function(event: any) {
        setMousePos({ x: event.pageX, y: event.pageY })
      })
      .on("mouseleave", function() {
        setHoverCountry(null)
        d3.select(this)
          .attr("stroke", "#d1d5db")
          .attr("stroke-width", 0.5)
      })
      .on("click", (event: any, d: any) => {
        // Check if this was a drag (mouse moved significantly)
        if (event.defaultPrevented) return
        
        // Use numeric ISO code to find jurisdiction name
        const isoNumeric = d.id
        const jurisdiction = ISO_NUMERIC_TO_JURISDICTION[isoNumeric]
        
        if (onCountryClick && jurisdiction) {
          onCountryClick(jurisdiction)
        }
      })

    // Simple drag implementation (based on Michael Keith example)
    const sensitivity = 75

    const drag = d3.drag<SVGSVGElement, unknown>()
      .on("drag", (event) => {
        const rotate = projection.rotate()
        const k = sensitivity / projection.scale()
        projection.rotate([
          rotate[0] + event.dx * k,
          rotate[1] - event.dy * k
        ])
        countries.attr("d", path as any)
      })
      .on("end", () => {
        // Persist the final rotation so it doesn't reset on re-render
        rotationRef.current = projection.rotate() as [number, number, number]
      })

    svg.call(drag as any)

    // Mouse wheel zoom
    svg.on("wheel", (event: WheelEvent) => {
      event.preventDefault()
      const delta = -event.deltaY
      const zoomFactor = delta > 0 ? 1.1 : 0.9
      const newScale = Math.max(200, Math.min(1000, scale * zoomFactor))
      setScale(newScale)
    })
  }, [ready, worldData, size, countByJurisdiction, onCountryClick, scale])

  // Find regulation count for hovered country
  const getCountForCountry = (countryName: string): number => {
    for (const [jurisdiction, count] of countByJurisdiction.entries()) {
      if (jurisdiction.toLowerCase().includes(countryName.toLowerCase()) ||
          countryName.toLowerCase().includes(jurisdiction.toLowerCase())) {
        return count
      }
    }
    return 0
  }

  const handleZoomIn = () => {
    setScale(prev => Math.min(1000, prev * 1.2))
  }

  const handleZoomOut = () => {
    setScale(prev => Math.max(200, prev / 1.2))
  }

  return (
    <div ref={containerRef} className={cn("relative w-full bg-white", className)} style={{ height: "600px" }}>
      <svg
        ref={svgRef}
        width={size.width}
        height={size.height}
        className="block"
        style={{ touchAction: "none" }}
      />

      {/* Zoom Controls */}
      <div className="absolute right-3 top-3 flex flex-col gap-2">
        <button
          onClick={handleZoomIn}
          className="flex h-8 w-8 items-center justify-center rounded-md bg-white/90 text-slate-700 shadow-md backdrop-blur hover:bg-white hover:text-slate-900 transition-colors"
          aria-label="Zoom in"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
        </button>
        <button
          onClick={handleZoomOut}
          className="flex h-8 w-8 items-center justify-center rounded-md bg-white/90 text-slate-700 shadow-md backdrop-blur hover:bg-white hover:text-slate-900 transition-colors"
          aria-label="Zoom out"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
          </svg>
        </button>
      </div>

      {/* Legend */}
      <div className="absolute left-3 top-3 rounded-md bg-white/90 p-3 text-xs shadow-md backdrop-blur">
        <div className="font-semibold mb-2">Regulation Count</div>
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <div className="w-6 h-3 rounded" style={{ backgroundColor: "#e5e5e5" }} />
            <span>1-5</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-3 rounded" style={{ backgroundColor: "#a3a3a3" }} />
            <span>6-20</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-3 rounded" style={{ backgroundColor: "#525252" }} />
            <span>21-50</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-3 rounded" style={{ backgroundColor: "#171717" }} />
            <span>50+</span>
          </div>
        </div>
      </div>

      {/* Tooltip */}
      {hoverCountry && (
        <div
          className="pointer-events-none fixed z-50 rounded-md bg-slate-900 px-3 py-2 text-sm text-white shadow-lg"
          style={{ left: mousePos.x + 10, top: mousePos.y + 10 }}
        >
          <div className="font-semibold">{hoverCountry}</div>
          <div className="text-slate-300">{getCountForCountry(hoverCountry)} regulations</div>
        </div>
      )}
    </div>
  )
}
