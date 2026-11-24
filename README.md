# Fee-Market and Transaction-Pricing in postfiatd

How postfiatd prices transactions under load — fee escalation, the
transaction queue, load fees, and eviction — at commit
`0085a1ff885d6a446369cf73a4430f75af22be55` (2026-10-10).

## Headline findings

- **Escalation is quadratic, not exponential.** Above the target the
  required fee level is the median times the square of the
  open-ledger count over the square of the target
  (`TxQ.cpp:173-195`). The design document says "increases
  exponentially"; the code disagrees.
- **The 128,000 median floor makes the first escalated fee enormous.**
  A cold-start ledger's 33rd transaction needs fee level 136,125,
  about 5,317 drops at a 10-drop base (`TxQ.h:100`;
  scenario S-13).
- **Queue-full eviction judges a newcomer against the victim
  account's average fee level.** A mid-fee newcomer can displace a
  high-fee transaction that shares an account with cheap ones
  (`TxQ.cpp:1243-1320`; scenario S-03).
- **Sequence order beats fee order.** A high-fee transaction behind a
  low-fee predecessor stalls until the predecessor clears or is
  rescued by a series payment (`TxQ.cpp:1435-1560`; scenario S-05).
- **FeeEscalation.md is stale on the ledger-size bounds.** It says
  minimum 5 and target 50; the code says minimum 32 and target 256
  (`TxQ.h:103`, `:109`).
- **The load fee is local-only and needs two consecutive overload
  signals.** Privileged submitters pay the remote factor while local
  load stays below four times remote
  (`LoadFeeTrack.cpp:32-58`, `:84-112`; scenarios S-09/S-10).

## Contents

- 45 rules (VERIFIED 38, SPECIFIED 4, MODELLED 2, UNTESTABLE 1) —
  `configs/fee-market-rules.json`, with grep-verified file:line
  ranges and verbatim excerpts in `fixtures/source-excerpts/` (44
  excerpts, 8 source files).
- Deterministic simulator (`src/fee_market_model.py`) + scenario
  matrix — 13 scenarios, 18 runs: priced 5, queued 5, evicted 6,
  stalled 2.
- Claim-to-evidence index: 24 claims (VERIFIED 16, SPECIFIED 2,
  MODELLED 4, UNTESTABLE 2) — `docs/claim-index.md`.
- Findings: 12 (HIGH 3, MEDIUM 6, LOW 3) — `findings.json`.
- Risk register: 14 risks (HIGH 3, MEDIUM 8, LOW 3) —
  `docs/risk-register.md`. Gap register: 8 gaps —
  `docs/gap-register.md`.
- Operator decision memo (pricing, spikes, queue survival) —
  `docs/decision-memo.md`. Methodology — `docs/methodology.md`.
  Evidence index — `docs/evidence-index.md`.

## Reproduction

```bash
bash scripts/run_all.sh        # exit 0 only if every check passes
bash scripts/clean_reproduce.sh  # fresh-copy reproduction (run twice)
```

- Full suite: `run_all.sh` exits 0; probe 12/12 checks pass.
- `outputs/run.log` (unedited full-run log, 10 lines) SHA-256:
  `cd91e248f63528ae3f4c422b9dfe7ad3e873e7ced51c1d621207804f7423e711`
- Fresh-copy reproduction was run twice; both passed with
  byte-identical deterministic outputs. Fresh-clone run log:
  `outputs/fresh-clone-run.log` SHA-256:
  `FRESH_CLONE_cd91e248f63528ae3f4c422b9dfe7ad3e873e7ced51c1d621207804f7423e711`
  (identical to the shipped `run.log` digest — the first fresh copy
  reproduces the shipped log byte-for-byte). Second fresh-clone run
  log: `outputs/fresh-clone-2-run.log` SHA-256:
  `FRESH_CLONE_2_cd91e248f63528ae3f4c422b9dfe7ad3e873e7ced51c1d621207804f7423e711`
  (also identical).
- Digests: `fee-market-results.json`
  `09850198fa6f62d008e04d8900812aad157ce051e36cd1cec3045319ebc8249d`;
  `scenario-matrix.json`
  `4bf26daafcc637909e3bf414fe8c7c672861824bbb0d29073b0e21e551a1d6ba`.
- Verify all digests: `bash scripts/verify_digests.sh`. The full
  unedited output of that check is captured in
  `outputs/verify-digests.log` (SHA-256:
  `d3674c5818f6ce7f1d953a17f6fa2031af0309b1ef4a4d3b733d10972a690a32`)
  and its digest is recorded in `run-manifest.json`.

The logs are independently resolvable as raw files:

https://raw.githubusercontent.com/araupooo/postfiatd-fee-market-pricing/main/outputs/run.log
https://raw.githubusercontent.com/araupooo/postfiatd-fee-market-pricing/main/outputs/fresh-clone-run.log
https://raw.githubusercontent.com/araupooo/postfiatd-fee-market-pricing/main/outputs/fresh-clone-2-run.log
https://raw.githubusercontent.com/araupooo/postfiatd-fee-market-pricing/main/outputs/probe-run.log
https://raw.githubusercontent.com/araupooo/postfiatd-fee-market-pricing/main/outputs/verify-digests.log

## CI

Continuous integration runs the same suite on every push; see the
workflow runs page:

https://github.com/araupooo/postfiatd-fee-market-pricing/actions/workflows/verify.yml
