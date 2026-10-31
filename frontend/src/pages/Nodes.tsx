import { useCallback, useEffect, useRef, useState } from "react"
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { RadialGauge } from "@/components/panels/RadialGauge"
import { HelpTooltip } from "@/components/shared/HelpTooltip"
import { bridge, type DeviceEtaMap, type DeviceInfo, type GraphDefinition, type Language } from "@/lib/api"
import { isVoiceNode, projectGraphNode } from "@/lib/graph-config"
import { requestGraphChange } from "@/lib/graph-actions"
import { buildRenderParams } from "@/lib/render-params"
import { StageNode, type StageNodeData } from "@/components/panels/StageNode"
import { useRenderJob } from "@/lib/use-render"
import { useQueue } from "@/lib/use-queue"
import { STAGE_NODE_MAP, setStageFromNode, updateConfig, useRenderConfig } from "@/lib/use-render-config"
import { confirmAction } from "@/lib/use-confirm"
import { loadGaugeColor } from "@/lib/gauge-color"
import { formatDuration, relativeSpeedPercent, projectedLoadPercent, jobMemoryBudget } from "@/lib/eta"
import { cn } from "@/lib/utils"

const nodeTypes = { stageNode: StageNode }
const PARALLEL_WORKER_OPTIONS = [1, 2, 3, 4]

export function NodesPage() {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([])
  const render = useRenderJob()
  const cfg = useRenderConfig()
  const nodesRef = useRef(nodes)
  nodesRef.current = nodes
  const cfgRef = useRef(cfg)
  cfgRef.current = cfg
  const graphRequest = useRef(0)
  const [languages, setLanguages] = useState<Language[]>([])
  const queue = useQueue()
  const videoPath = queue[0]?.input_path ?? null
  const displayedInput = render.isRunning ? render.inputPath : videoPath
  const [devices, setDevices] = useState<DeviceInfo[]>([])
  const [selectedDeviceId, setSelectedDeviceId] = useState("cpu")
  const [deviceEtas, setDeviceEtas] = useState<DeviceEtaMap>({})
  const [selectedVram, setSelectedVram] = useState<{ used: number | null; total: number | null }>({
    used: null, total: null,
  })
  const castKey = JSON.stringify(nodes.filter(node => isVoiceNode(node.id)).map(node =>
    (node.data as StageNodeData).def.params.find(param => param.key === 'voice')?.default))

  useEffect(() => {
    bridge.listLanguages().then(setLanguages).catch(() => {})
    bridge.getHardwareSnapshot().then((snap) => {
      setDevices(snap.devices)
      setSelectedDeviceId(snap.default_device_id)
    })
  }, [])

  useEffect(() => {
    let cancelled = false
    setSelectedVram({ used: null, total: null })
    bridge.getHardwareSnapshot(selectedDeviceId).then((snap) => {
      if (!cancelled) setSelectedVram({ used: snap.vram_used_mb, total: snap.vram_total_mb })
    }).catch(() => {})
    return () => { cancelled = true }
  }, [selectedDeviceId])

  useEffect(() => {
    let cancelled = false
    setDeviceEtas({})
    if (!videoPath) {
      return
    }
    bridge
      .estimateJobAllDevices(videoPath, {
        ...buildRenderParams(cfg, selectedDeviceId, "video", cfg.lipsync ? "video_dub_lipsync" : "video_dub"),
      })
      .then((result) => { if (!cancelled) setDeviceEtas(result) })
      .catch(() => { if (!cancelled) setDeviceEtas({}) })
    return () => { cancelled = true }
  }, [videoPath, castKey, cfg, selectedDeviceId])

  const selectedBudget = jobMemoryBudget(deviceEtas[selectedDeviceId], selectedDeviceId)
  const loadPercent = projectedLoadPercent(selectedVram.used, selectedVram.total, selectedBudget)
  const loadTooHigh = loadPercent != null && loadPercent >= 95

  async function handleToggle(nodeId: string, enabled: boolean) {
    const result = await requestGraphChange(() => bridge.setNodeEnabled(nodeId, enabled))
    if (!result) return
    setNodes((prev) =>
      prev.map((n) => (n.id === nodeId ? { ...n, data: { ...n.data, enabled } as StageNodeData } : n))
    )
    // No-ops for nodes with no Dashboard equivalent (e.g. "subtitles") -
    // see STAGE_NODE_MAP. Doesn't call back into bridge.setNodeEnabled
    // itself (already done above), so this can't loop.
    setStageFromNode(nodeId, enabled)
  }

  async function handleParamChange(nodeId: string, key: string, value: string) {
    const result = await requestGraphChange(() => bridge.setNodeParam(nodeId, key, value))
    if (!result) return
    if (isVoiceNode(nodeId) && key === 'voice' && nodesRef.current.filter(node => isVoiceNode(node.id)).length === 1) {
      updateConfig({ voice: value })
    }
    setNodes((prev) =>
      prev.map((n) =>
        n.id === nodeId
          ? {
              ...n,
              data: {
                ...n.data,
                def: {
                  ...(n.data as StageNodeData).def,
                  params: (n.data as StageNodeData).def.params.map((p) =>
                    p.key === key ? { ...p, default: value } : p
                  ),
                },
              } as StageNodeData,
            }
          : n
      )
    )
  }

  // Adding/removing a node instance changes the node/edge SET (not just a
  // value on one), so a full reload from the server is the simplest way
  // to stay correct - unlike drag positions, this is infrequent enough
  // that a round-trip isn't a UX cost.
  const loadGraph = useCallback(() => {
    const request = ++graphRequest.current
    bridge.getGraphDefinition().then((def: GraphDefinition) => {
      if (request !== graphRequest.current) return
      const voices = def.nodes.filter(node => isVoiceNode(node.id))
      if (voices.length === 1 && nodesRef.current.filter(node => isVoiceNode(node.id)).length > 1) {
        const remaining = voices[0].params.find(param => param.key === 'voice')?.default
        if (typeof remaining === 'string') updateConfig({ voice: remaining })
      }
      setNodes(
        def.nodes.map((d) => ({
          id: d.id,
          type: "stageNode",
          position: { x: d.x, y: d.y },
          data: {
            def: d,
            enabled: d.enabled,
            active: render.activeStageId === d.id,
            onToggle: handleToggle,
            onParamChange: handleParamChange,
            onDuplicate: handleDuplicate,
            onRemove: handleRemove,
          } satisfies StageNodeData,
        }))
      )
      setEdges(
        def.edges.map((e) => ({
          id: `${e.source}-${e.target}`,
          source: e.source,
          target: e.target,
          animated: render.isRunning,
          style: { stroke: "var(--primary)" },
        }))
      )
    }).catch(error => {
      if (request !== graphRequest.current) return
      void confirmAction({ title: "Graph could not be loaded", description: String(error), alertOnly: true })
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function handleDuplicate(specId: string) {
    if (specId === 'tts_rvc' && nodesRef.current.filter(node => isVoiceNode(node.id)).length === 1) {
      const synced = await requestGraphChange(() => bridge.setNodeParam('tts_rvc', 'voice', cfgRef.current.voice))
      if (!synced) return
    }
    const result = await requestGraphChange(() => bridge.addNodeInstance(specId))
    if (result) loadGraph()
  }

  async function handleRemove(nodeId: string) {
    const result = await requestGraphChange(() => bridge.removeNodeInstance(nodeId))
    if (result) loadGraph()
  }

  useEffect(() => {
    loadGraph()
    return () => { graphRequest.current++ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Reflect the currently-executing stage / render animation without
  // touching node positions.
  useEffect(() => {
    setNodes((prev) =>
      prev.map((n) => ({
        ...n,
        data: { ...n.data, active: render.activeStageId === n.id } as StageNodeData,
      }))
    )
    setEdges((prev) => prev.map((e) => ({ ...e, animated: render.isRunning })))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [render.activeStageId, render.isRunning])

    const params = buildRenderParams(cfg, selectedDeviceId, "video", cfg.lipsync ? "video_dub_lipsync" : "video_dub")

  async function handleStart() {
    if (!videoPath) return

    if (loadTooHigh) {
      await confirmAction({
        title: "Projected load too high",
        description: `This job's projected VRAM usage is ${Math.round(loadPercent!)}% of "${devices.find((d) => d.id === selectedDeviceId)?.label ?? selectedDeviceId}"'s capacity - too close to the limit to safely start. Pick a different device, lower Parallel Workers, or disable a heavier stage.`,
        alertOnly: true,
      })
      return
    }

    const ok = await confirmAction({
      title: "Start video batch?",
      description: `Starts ${queue.length} pending video jobs in order. New jobs use ${devices.find((device) => device.id === selectedDeviceId)?.label ?? selectedDeviceId}, target language ${cfg.lang}, and the current graph settings. Previously accepted jobs retain their settings.`,
      confirmLabel: "Start Batch",
    })
    if (!ok) return
    const result = await render.startBatch(params, cfg.lipsync ? "video_dub_lipsync" : "video_dub", queue.map((job) => job.id))
    if (!result.ok) await confirmAction({ title: "Start unavailable", description: result.message ?? "The batch was not accepted.", alertOnly: true })
  }

  return (
    <div className="flex h-full min-h-0 w-full flex-col bg-background">
      <p className="px-4 py-2 text-xs text-muted-foreground">
        Fixed pipeline order. Extra Voice nodes alternate voices by transcript segment; speaker identification is not available.
        {render.isRunning && " Controls and estimates configure future jobs; accepted jobs retain their settings."}
      </p>
      <div className="flex min-h-0 flex-1">
        <div className="relative min-w-0 flex-1" aria-label="Pipeline canvas">
        <ReactFlow
          nodes={nodes.map(node => {
            const def = projectGraphNode((node.data as StageNodeData).def, cfg,
              nodes.filter(item => isVoiceNode(item.id)).length, languages, displayedInput, STAGE_NODE_MAP)
            return { ...node, data: { ...node.data, def, enabled: def.enabled,
              active: render.activeStageId === node.id } }
          })}
          edges={edges.map(edge => ({ ...edge, animated: render.isRunning }))}
          onNodesChange={onNodesChange}
          onNodeDragStop={async (_event, node) => {
            const result = await requestGraphChange(() => bridge.setNodePosition(node.id, node.position.x, node.position.y), "Layout could not be saved")
            if (!result) loadGraph()
          }}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          nodesDraggable
          nodesConnectable={false}
          edgesReconnectable={false}
          fitView
          minZoom={0.1}
          colorMode="dark"
        >
          <Background gap={24} color="var(--border)" />
          <Controls showInteractive={false} />
        </ReactFlow>
        </div>

        {/* Parallel processing + projected load - node-graph-specific,
            since parallel_workers only affects the tts_rvc stage's
            per-segment dubbing loop (see core/pipeline.py's
            _dub_all_segments) and this is where the user asked to see it. */}
        <aside aria-label="Render resources" className="w-72 shrink-0 overflow-y-auto border-l border-border p-3">
          <Card className="w-full border-border bg-card">
            <CardContent className="flex flex-col gap-3 py-3">
              <div className="flex flex-col gap-1.5">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs text-muted-foreground">Parallel Workers</span>
                  <HelpTooltip text="Overlaps preparation and mastering of transcript segments. Model inference stays serialized for safety on CPU and GPU. Speed depends on the workload; estimates do not assume a worker-count speedup. More workers can increase memory use." />
                </div>
                <Select
                  value={String(cfg.parallelWorkers)}
                  onValueChange={(v) => updateConfig({ parallelWorkers: Number(v) })}
                >
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {PARALLEL_WORKER_OPTIONS.map((n) => (
                      <SelectItem key={n} value={String(n)}>{n === 1 ? "1 (sequential)" : `${n} parallel`}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex flex-col gap-1.5">
                <span className="text-xs text-muted-foreground">Device</span>
                <Select value={selectedDeviceId} onValueChange={setSelectedDeviceId}>
                  <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {devices.map((d) => (
                      <SelectItem key={d.id} value={d.id}>{d.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {videoPath && (
                <div className="flex items-center justify-around pt-1">
                  <RadialGauge
                    percent={relativeSpeedPercent(deviceEtas, selectedDeviceId)}
                    label="EST. TIME"
                    sublabel="relative speed"
                    color="var(--secondary)"
                    centerLabel={formatDuration(deviceEtas[selectedDeviceId]?.eta_seconds)}
                    size={78}
                  />
                  {loadPercent == null ? (
                    <div className="flex w-[78px] flex-col items-center gap-1 text-center">
                      <div className="flex h-[78px] w-[78px] items-center justify-center rounded-full border border-dashed border-border p-2">
                        <span className="text-[9px] leading-tight text-muted-foreground">{selectedVram.total == null || selectedVram.used == null ? "VRAM unreadable" : "GPU budget unknown"}</span>
                      </div>
                      <span className="text-[10px] font-medium text-muted-foreground">LOAD</span>
                    </div>
                  ) : (
                    <div className="relative">
                      <RadialGauge
                        percent={loadPercent}
                        label="LOAD"
                        sublabel={`${Math.round((selectedVram.used ?? 0) + (selectedBudget ?? 0))} / ${selectedVram.total} MB`}
                        color={loadGaugeColor(loadPercent)}
                        size={78}
                      />
                      {loadTooHigh && (
                        <div className="pointer-events-none absolute inset-0 flex h-[78px] w-[78px] flex-col items-center justify-center rounded-full bg-destructive/85 text-center">
                          <span className="text-[8px] font-bold leading-tight text-white">
                            NOT<br />RECOMMENDED
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
              {videoPath && (
                <p className="text-[10px] text-muted-foreground">
                  Uncalibrated cumulative GPU budgets; downloads and service latency excluded.
                  {deviceEtas[selectedDeviceId]?.audio_buffer_ram_mb != null &&
                    ` Audio buffers: about ${Math.round(deviceEtas[selectedDeviceId].audio_buffer_ram_mb!)} MB RAM, plus model memory.`}
                </p>
              )}
              {videoPath && Object.entries(deviceEtas[selectedDeviceId]?.peak_vram_by_device_mb ?? {}).map(([device, budget]) => (
                <p key={device} className="text-[10px] text-muted-foreground">
                  {devices.find((item) => item.id === device)?.label ?? device}: {budget == null ? "GPU memory estimate unavailable" : `about ${Math.round(budget)} MB additional memory budget`}
                </p>
              ))}
              {videoPath && deviceEtas[selectedDeviceId]?.warnings?.map((warning) => (
                <p key={warning} className="text-[10px] text-amber-500">{warning}</p>
              ))}
            </CardContent>
          </Card>
        </aside>
      </div>

        {/* Same render controls as Dashboard's, so a graph edit doesn't
            require switching pages to actually run it. */}
        <div className="flex shrink-0 flex-col items-center gap-2 border-t border-border p-3">
          {render.status !== "idle" && (
            <Card className="pointer-events-auto w-full max-w-md border-border bg-card/95 backdrop-blur">
              <CardContent className="flex flex-col gap-2 py-3">
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">{render.statusText || render.status.toUpperCase()}</span>
                  <span className="text-primary">{render.percent}%</span>
                </div>
                <Progress value={render.percent} />
                {render.stillWorking && (
                  <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-warning" />
                    Still working - this stage can take a while depending on your hardware.
                  </div>
                )}
                {render.errorMessage && <div className="text-xs text-destructive">{render.errorMessage}</div>}
              </CardContent>
            </Card>
          )}

          {render.isRunning ? (
            <Button
              size="lg"
              variant="destructive"
              className="pointer-events-auto w-full max-w-md text-base font-bold tracking-widest shadow-lg [clip-path:polygon(0_0,100%_0,100%_calc(100%-14px),calc(100%-14px)_100%,0_100%)]"
              disabled={render.isStopping} onClick={() => render.stop()}
            >
              STOP RENDER
            </Button>
          ) : (
            <Button
              size="lg"
              className={cn(
                "pointer-events-auto w-full max-w-md text-base font-bold tracking-widest [clip-path:polygon(0_0,100%_0,100%_calc(100%-14px),calc(100%-14px)_100%,0_100%)]",
                loadTooHigh
                  ? "bg-destructive text-white shadow-[0_0_24px_-4px_var(--destructive)] hover:bg-destructive/90"
                  : "shadow-[0_0_24px_-4px_var(--primary)]"
              )}
              disabled={!videoPath}
              onClick={handleStart}
              title={videoPath ? undefined : "Select a video from Assets/Dashboard first"}
            >
              {loadTooHigh ? "LOAD TOO HIGH - NOT RECOMMENDED" : "START VIDEO BATCH"}
            </Button>
          )}
        </div>
    </div>
  )
}
