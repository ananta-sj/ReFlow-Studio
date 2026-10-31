/** Keep rapid changes and resets in submission order; a failed save cannot block later saves. */
export function createSettingsSaver() {
  let pending: Promise<void> = Promise.resolve()
  return function enqueue<T>(operation: () => Promise<T>): Promise<T> {
    const result = pending.then(operation)
    pending = result.then(() => undefined, () => undefined)
    return result
  }
}
