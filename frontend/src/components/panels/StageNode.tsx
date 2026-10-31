import { Copy, X } from "lucide-react"
import { Handle, Position, type NodeProps } from "@xyflow/react"
import { Switch } from "@/components/ui/switch"
import { CornerFrame } from "@/components/panels/CornerFrame"
import { cn } from "@/lib/utils"
import type { GraphNodeDef } from "@/lib/api"

export interface StageNodeData extends Record<string, unknown> {
  def: GraphNodeDef
  enabled: boolean
  active: boolean
  onToggle: (nodeId: string, enabled: boolean) => void
  onParamChange: (nodeId: string, key: string, value: string) => void
  onDuplicate: (specId: string) => void
  onRemove: (nodeId: string) => void
}

export function StageNode({ data }: NodeProps) {
  const { def, enabled, active, onToggle, onParamChange, onDuplicate, onRemove } = data as StageNodeData
  const muted = def.mutable && !enabled

  return (
    <CornerFrame dim={!active}>
      <div
        className={cn(
          "w-[210px] rounded-lg border bg-card shadow-md transition-opacity",
          active ? "border-primary shadow-[0_0_18px_-2px_var(--primary)]" : "border-border",
          muted && "opacity-50"
        )}
      >
        <Handle type="target" position={Position.Left} className="!h-3 !w-3 !bg-secondary !shadow-[0_0_6px_var(--secondary)]" />
        <div
          className="flex items-center justify-between rounded-t-lg px-3 py-2 text-xs font-semibold text-white"
          style={{ backgroundColor: def.headerColor ?? "var(--muted)", fontFamily: "var(--font-display)" }}
        >
          <span className="truncate">{def.icon} {def.title}</span>
          <div className="nodrag flex items-center gap-1">
            {def.duplicable && (
              <button
                type="button"
                title="Add another instance (multi-cast)"
                onClick={() => onDuplicate(def.id.replace(/_\d+$/, ""))}
                className="rounded p-0.5 hover:bg-white/20"
              >
                <Copy className="h-3 w-3" />
              </button>
            )}
            {def.removable && (
              <button
                type="button"
                title="Remove this instance"
                onClick={() => onRemove(def.id)}
                className="rounded p-0.5 hover:bg-white/20"
              >
                <X className="h-3 w-3" />
              </button>
            )}
            {def.mutable && (
              <Switch checked={enabled} onCheckedChange={(v) => onToggle(def.id, v)} className="scale-75" />
            )}
          </div>
        </div>
        {def.params.length > 0 && (
          <div
            className="flex flex-col gap-1.5 px-3 py-2 text-[11px] text-muted-foreground"
            style={{ fontFamily: "var(--font-mono)" }}
          >
            {def.params.map((p) =>
              p.kind === "combo" ? (
                <div key={p.key} className="flex flex-col gap-0.5">
                  <span>{p.label}</span>
                  <select
                    className="nodrag w-full rounded border border-border bg-background px-1 py-0.5 text-[11px] text-foreground"
                    value={String(p.default ?? "")}
                    onChange={(e) => onParamChange(def.id, p.key, e.target.value)}
                  >
                    {p.options.map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </div>
              ) : (
                <div key={p.key} className="flex justify-between gap-2">
                  <span>{p.label}</span>
                  <span className="truncate text-foreground">{String(p.default ?? "")}</span>
                </div>
              )
            )}
          </div>
        )}
        <Handle type="source" position={Position.Right} className="!h-3 !w-3 !bg-primary !shadow-[0_0_6px_var(--primary)]" />
      </div>
    </CornerFrame>
  )
}
