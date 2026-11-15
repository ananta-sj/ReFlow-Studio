export function ErrorDetails({ message }: { message: string }) {
  const first = message.split('\n')[0].replace(/Traceback \(most recent call last\):?\s*$/, '').trim()
  return <div role="alert" className="break-words text-xs text-destructive">
    <p>{first || 'Processing stopped. Open the details below.'}</p>
    {message.includes('\n') && <details className="mt-1 text-muted-foreground">
      <summary className="cursor-pointer">Technical details</summary>
      <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-words font-mono">{message}</pre>
    </details>}
  </div>
}
