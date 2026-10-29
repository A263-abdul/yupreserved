/** Motion primitives: calm scroll reveals and page transitions. */
import { motion, type HTMLMotionProps } from "motion/react";
import type { ReactNode } from "react";

const EASE = [0.22, 1, 0.36, 1] as const;

export function Reveal({ children, delay = 0, y = 28, className = "", ...rest }:
  { children: ReactNode; delay?: number; y?: number; className?: string } & HTMLMotionProps<"div">) {
  return (
    <motion.div
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.9, delay, ease: EASE }}
      className={className}
      {...rest}
    >
      {children}
    </motion.div>
  );
}

/** Words of a headline rise one after another, like type set on a press */
export function SetType({ lines, className = "", delay = 0.1 }: { lines: ReactNode[]; className?: string; delay?: number }) {
  return (
    <span className={className}>
      {lines.map((line, i) => (
        <span key={i} className="block overflow-hidden pb-[0.08em]">
          <motion.span className="block" initial={{ y: "105%" }} animate={{ y: 0 }}
            transition={{ duration: 1.1, delay: delay + i * 0.12, ease: EASE }}>
            {line}
          </motion.span>
        </span>
      ))}
    </span>
  );
}

export function Page({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <motion.main
      id="main"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.45, ease: EASE }}
      className={className}
    >
      {children}
    </motion.main>
  );
}
