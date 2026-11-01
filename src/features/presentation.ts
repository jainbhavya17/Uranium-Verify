/** Human-readable labels; persisted identifiers and verification outcomes stay unchanged. */
export function label(input: string | null | undefined) {
  if (!input) return "Not available";
  const special: Record<string, string> = {
    EOA: "Extension of Approval",
    MOCK: "Demonstration",
    MOCK_TEST: "Test scanner",
    SYNTHETIC: "Sample record",
    SYNTHETIC_FIXTURE: "Sample attachment",
    MOCK_FIXTURES_NO_OCR: "Sample attachment · extraction not run",
    PROCESSED: "Ready for checks",
    UPLOADED: "Queued for processing",
    SAFETY_UNAVAILABLE: "Safety check unavailable",
    MANUAL_REVIEW: "Review needed",
    NEEDS_REUPLOAD: "Upload a clearer document",
    PROCESSING_FAILED: "Processing failed",
    QUARANTINED_PENDING_SAFETY: "Waiting for safety checks",
    NOT_RUN: "Not checked",
    NOT_CONFIGURED: "Connection not configured",
    INSUFFICIENT_EVIDENCE: "More evidence needed",
    NOT_APPLICABLE: "Not required",
    PENDING_REVIEW: "Waiting for review",
  };
  return (
    special[input] ??
    input
      .replaceAll("_", " ")
      .toLowerCase()
      .replace(/^./, (c) => c.toUpperCase())
  );
}
