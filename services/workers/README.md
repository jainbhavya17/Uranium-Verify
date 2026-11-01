# Processing worker boundary

Run the Phase 3 persistent worker from the repository root with `PYTHONPATH=services/api python -m uranium.worker` (PowerShell: set `$env:PYTHONPATH='services/api'` first). `--once` processes at most one pending job. API and worker must use the same DATABASE_URL and private STORAGE_ROOT.

Configure real ClamAV definitions and Tesseract first; defaults retain quarantine on scanner failure. Leased job claims, three-attempt retry limits, interruption recovery, OS resource caps, immutable extraction and saved precheck inputs are implemented. Controlled MOCK fixtures do not run extraction. See [Phase 3 handoff](../../docs/PHASE_3_HANDOFF.md) for exact platform setup, contracts, fixtures and limitations.
