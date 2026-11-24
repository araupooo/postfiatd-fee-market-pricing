# Evidence index

Where every piece of evidence in this pack lives, and how to check it.

## Rules and scenarios

- `configs/fee-market-rules.json` — 45 rules (VERIFIED 38, SPECIFIED 4,
  MODELLED 2, UNTESTABLE 1), each with a file:line source and an
  excerpt id, or an external documentation quote.
- `configs/scenarios.json` — 13 scenarios, 18 runs, with the pinned
  constants (base level 256, minimum escalation multiplier 128,000,
  minimum 32 / target 256 transactions per ledger, 20 ledgers in
  queue, minimum queue size 2,000, 10 per account, 10 retries, 25%
  replacement premium, 2-ledger buffer, load factor 256 / step 1/4 /
  maximum 256,000,000, privileged cap 4x, series guard 2^21).

## Excerpts

- `fixtures/source-excerpts/E01.txt` … `E44.txt` — verbatim excerpts
  from the pinned commit, each headed with repo, commit, file, lines,
  source SHA-256, git blob SHA, and size. See `docs/excerpts.md` for
  the per-excerpt digest table.
- `fixtures/source-hashes.json` — SHA-256, git blob SHA, line count,
  and size for every excerpt and every cited source file (8 files).
- `fixtures/excerpts-manifest.json` — the extraction manifest
  (file, lines, anchor) that `scripts/extract_excerpts.py` enforces
  against the pinned checkout.

## Simulator outputs

- `outputs/derived/fee-market-results.json` — per-scenario runs with
  computed required levels, minimum processing levels, outcomes, and
  reasons, plus the threshold and limits tables.
- `outputs/derived/scenario-matrix.json` — one row per run. See
  `docs/scenario-matrix.md`.
- `outputs/derived/run-summary.json` — step statuses for the full run.
- `outputs/derived/probe-results.json` — the 12 probe checks and
  their pass/fail detail.
- `outputs/run.log` — the unedited full-run log with the full 64-char
  SHA-256 of every deterministic output.
- `outputs/probe-run.log` — the unedited probe log.
- `outputs/verify-digests.log` — the full unedited output of
  `scripts/verify_digests.sh`.
- `outputs/fresh-clone-run.log`, `outputs/fresh-clone-2-run.log` —
  the two fresh-copy reproduction logs, with matching probe and
  compare logs and derived files under the `fresh-clone-` and
  `fresh-clone-2-` prefixes.

## Verification

- `run-manifest.json` — counts, the results and matrix digests, the
  verify-digests digest, and the two reproduction log digests.
- `SHA256SUMS` — SHA-256 for every shipped file; check with
  `bash scripts/verify_digests.sh`.
- `.github/workflows/verify.yml` — the CI workflow: check out the
  pinned postfiatd commit, verify shipped digests, run the full suite,
  check the run summary and manifest, verify regenerated digests.

## How to re-verify a single claim

1. Find the claim in `docs/claim-index.md` and its rule in
   `configs/fee-market-rules.json`.
2. Read the excerpt in `fixtures/source-excerpts/<id>.txt`; its header
   gives the file, lines, and blob SHA.
3. Confirm the blob with
   `git -C ~/workspace/postfiatd-pin-0085a1f hash-object -- <file>`
   and the lines with `sed -n '<start>,<end>p'` on that checkout.
