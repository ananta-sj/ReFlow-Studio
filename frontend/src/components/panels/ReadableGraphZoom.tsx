import { Panel, useReactFlow } from "@xyflow/react"
import { Button } from "@/components/ui/button"

export function ReadableGraphZoom() {
  const { zoomTo } = useReactFlow()
  return (
    <Panel position="top-left">
      <Button type="button" variant="outline" size="sm"
        title="Show nodes at actual size. Pan to explore; Fit shows the entire pipeline."
        onClick={() => { void zoomTo(1) }}>
        Readable zoom (100%)
      </Button>
    </Panel>
  )
}
