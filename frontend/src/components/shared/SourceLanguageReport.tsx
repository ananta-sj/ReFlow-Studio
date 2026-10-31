import type { SourceLanguageFeedback } from "@/lib/api"

export function SourceLanguageReport({ feedback }: { feedback: SourceLanguageFeedback }) {
  return (
    <div role="status" aria-live="polite" className="rounded-md border border-border p-3 text-xs">
      <p>Detected source: {feedback.detected_name ?? feedback.detected_language ?? "Unavailable"}
        {feedback.probability !== null
          ? ` · ${(Math.floor(feedback.probability * 10000) / 100).toFixed(2)}% confidence`
          : " · confidence unavailable"}</p>
      <p className="mt-1">{feedback.origin === "manual"
        ? `Translation source: ${feedback.source_name} (manual override)`
        : feedback.resolved
          ? `Translation source: ${feedback.source_name} (Auto)`
          : "Auto could not resolve the source. M2M100 and NLLB need a manual selection; prompt-based translators may infer it."}</p>
      <p className="mt-1 text-muted-foreground">Confidence does not guarantee accuracy or that every speaker uses the same language.</p>
    </div>
  )
}
