import type { JobActionResult } from "./api"
import { confirmAction } from "./use-confirm"

/** Do not update local graph/config state until the bridge acknowledges an edit. */
export async function requestGraphChange<T extends JobActionResult>(
  request: () => Promise<T>,
  title = "Node change unavailable",
): Promise<T | null> {
  try {
    const result = await request()
    if (result.ok) return result
    await confirmAction({ title, description: result.message ?? "The change was rejected.", alertOnly: true })
  } catch (error) {
    await confirmAction({
      title,
      description: `The graph request failed: ${String(error)}. Refresh the graph before retrying; the backend may have received the request.`,
      alertOnly: true,
    })
  }
  return null
}
