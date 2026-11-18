// Startup reads need a recovery path; long-running job calls do not use this.
export function withStartupTimeout<T>(operation: Promise<T>, message: string, timeoutMs = 30000): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(message)), timeoutMs)
    operation.then(value => { clearTimeout(timer); resolve(value) },
      error => { clearTimeout(timer); reject(error) })
  })
}
