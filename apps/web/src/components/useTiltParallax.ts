"use client";

/** Pointer tilt parallax (plan §1.4): ±2° max, rAF-throttled, disabled under
 *  prefers-reduced-motion. Writes --tilt-x/--tilt-y on the strata element. */
import { useEffect, useRef } from "react";

export default function useTiltParallax() {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (mq.matches) return;

    let raf = 0;
    let tx = 0;
    let ty = 0;
    const onMove = (e: PointerEvent) => {
      const nx = e.clientX / window.innerWidth - 0.5;
      const ny = e.clientY / window.innerHeight - 0.5;
      ty = Number((nx * 4).toFixed(2)); // ±2deg
      tx = Number((-ny * 2.4).toFixed(2));
      if (!raf) {
        raf = requestAnimationFrame(() => {
          el.style.setProperty("--tilt-y", `${ty}deg`);
          el.style.setProperty("--tilt-x", `${tx}deg`);
          raf = 0;
        });
      }
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => {
      window.removeEventListener("pointermove", onMove);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  return ref;
}
