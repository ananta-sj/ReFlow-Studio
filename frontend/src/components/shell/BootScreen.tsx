import { motion, AnimatePresence } from "motion/react"

interface BootScreenProps {
  visible: boolean
  statusText: string
}

export function BootScreen({ visible, statusText }: BootScreenProps) {
  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-6 bg-background"
          initial={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.5, ease: "easeInOut" }}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.92 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.7, ease: "easeOut" }}
            className="text-5xl font-bold tracking-wide"
            style={{ fontFamily: "var(--font-display)" }}
          >
            <span className="text-foreground">ReFlow</span>{" "}
            <motion.span
              className="text-primary"
              animate={{
                textShadow: [
                  "0 0 10px var(--primary)",
                  "0 0 24px var(--primary)",
                  "0 0 10px var(--primary)",
                ],
              }}
              transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
            >
              Studio
            </motion.span>
          </motion.div>

          <div className="flex items-center gap-2 text-xs text-muted-foreground" style={{ fontFamily: "var(--font-mono)" }}>
            <motion.span
              className="h-1.5 w-1.5 rounded-full bg-primary"
              animate={{ opacity: [1, 0.3, 1] }}
              transition={{ duration: 1.1, repeat: Infinity, ease: "easeInOut" }}
            />
            <span>{statusText}</span>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
