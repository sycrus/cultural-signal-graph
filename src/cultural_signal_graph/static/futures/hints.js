/* Plain-language hints for the marks a projection can carry (wording follows
   CONTEXT.md's glossary) — shared by the detail panel and every lens, so a tag
   means the same thing wherever you hover it. */

export const TAG_HINTS = {
  baseline: "Baseline — the business-as-usual branch every exploration has; the reference the alternatives are read against. Not a probability claim.",
  discontinuity: "Discontinuity — anchored to evidence and breaking from trend; the generator includes at least one per order.",
  "timing conflict": "Timing conflict — starts before what it grows from: the dates are off, the content still stands.",
  stale: "Stale — something it grows from changed after this was generated.",
};

export function marksText(p) {
  return [
    p.baseline && TAG_HINTS.baseline,
    p.discontinuity && TAG_HINTS.discontinuity,
    p.timing_conflict && TAG_HINTS["timing conflict"],
    p.stale && TAG_HINTS.stale,
  ].filter(Boolean).join("\n");
}

export function nodeTitle(p) {
  const marks = marksText(p);
  return marks ? `${marks}\n${p.statement}` : p.statement;
}
