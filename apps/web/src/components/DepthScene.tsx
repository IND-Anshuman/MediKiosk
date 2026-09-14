/** Strata depth scene (plan §1.4) — fixed background, three drifting planes.
 *  Pure CSS animation; tilt vars applied by useTiltParallax on the parent. */
export default function DepthScene() {
  return (
    <div className="strata strata-tilt" aria-hidden="true" data-testid="depth-scene">
      <i />
      <i />
      <i />
    </div>
  );
}
