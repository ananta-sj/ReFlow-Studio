import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { RadialGauge } from "@/components/panels/RadialGauge"
import { CornerFrame } from "@/components/panels/CornerFrame"
import { AreaChart, Area } from "@/components/charts/area-chart"
import { Grid } from "@/components/charts/grid"
import { cn } from "@/lib/utils"
import { loadGaugeColor } from "@/lib/gauge-color"
import { useHardware } from "@/lib/use-hardware"
import type { DeviceInfo } from "@/lib/api"

interface HardwareIntelligenceProps {
  onDeviceSelected?: (deviceId: string) => void
}

function DeviceRow({
  device,
  selected,
  onSelect,
}: {
  device: DeviceInfo
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "flex w-full items-center gap-2 rounded-md border px-3 py-2 text-left text-xs transition-colors",
        selected
          ? "border-primary bg-primary text-primary-foreground shadow-[0_0_10px_-2px_var(--primary)]"
          : "border-border text-muted-foreground hover:border-muted-foreground/40"
      )}
    >
      <span
        className={cn(
          "h-2.5 w-2.5 shrink-0 rounded-full border",
          selected ? "border-primary-foreground bg-primary-foreground" : "border-muted-foreground"
        )}
      />
      <span className="truncate">{device.label}</span>
      <span
        className="ml-auto shrink-0 text-[10px] uppercase opacity-70"
        style={{ fontFamily: "var(--font-mono)" }}
      >
        {device.kind}
      </span>
    </button>
  )
}

export function HardwareIntelligence({ onDeviceSelected }: HardwareIntelligenceProps) {
  const [selectedDeviceId, setSelectedDeviceId] = useState<string | null>(null)
  const { snapshot, history } = useHardware(selectedDeviceId)

  function selectDevice(id: string) {
    setSelectedDeviceId(id)
    onDeviceSelected?.(id)
  }

  const ramPercent = snapshot ? (snapshot.ram_used_gb / snapshot.ram_total_gb) * 100 : 0

  return (
    <div className="flex flex-col gap-4">
      <CornerFrame>
        <Card className="border-border bg-card">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-semibold tracking-wide text-muted-foreground">
              05 // HARDWARE INTELLIGENCE
            </CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-around pt-2">
            <RadialGauge
              percent={snapshot?.cpu_percent ?? 0}
              label="CPU LOAD"
              sublabel={snapshot?.cpu_name ?? "…"}
              color={loadGaugeColor(snapshot?.cpu_percent ?? 0)}
            />
            <RadialGauge
              percent={ramPercent}
              label="RAM LOAD"
              sublabel={snapshot ? `${snapshot.ram_used_gb} / ${snapshot.ram_total_gb} GB` : "…"}
              color={loadGaugeColor(ramPercent)}
            />
          </CardContent>
        </Card>
      </CornerFrame>

      <Card className="border-border bg-card">
        <CardHeader className="pb-2">
          <CardTitle className="text-xs font-semibold tracking-wide text-muted-foreground">
            06 // GPU SELECTOR
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-1.5 pt-2">
          {snapshot?.devices.map((device) => (
            <DeviceRow
              key={device.id}
              device={device}
              selected={(selectedDeviceId ?? snapshot.default_device_id) === device.id}
              onSelect={() => selectDevice(device.id)}
            />
          ))}
        </CardContent>
      </Card>

      <Card className="border-border bg-card">
        <CardHeader className="pb-2 flex flex-row items-center justify-between">
          <CardTitle className="text-xs font-semibold tracking-wide text-muted-foreground">
            07 // RESOURCE USAGE
          </CardTitle>
          <span className="text-[10px] font-semibold text-primary" style={{ fontFamily: "var(--font-mono)" }}>
            LIVE
          </span>
        </CardHeader>
        <CardContent className="pt-2">
          {history.length > 1 && (
            <AreaChart data={history} aspectRatio="3 / 1" margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
              <Grid />
              <Area dataKey="cpu" stroke="var(--primary)" />
            </AreaChart>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
