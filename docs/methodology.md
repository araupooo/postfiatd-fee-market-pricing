# Methodology

## Pinned source

All source findings are pinned to postfiatd commit
`0085a1ff885d6a446369cf73a4430f75af22be55` (2026-10-10). Every cited
line was verified with `grep -n` on a local checkout of that commit
(`~/workspace/postfiatd-pin-0085a1f`); no line number comes from a web
fetch. The 44 verbatim excerpts in `fixtures/source-excerpts/` were
extracted by `scripts/extract_excerpts.py` from that checkout, and
`fixtures/source-hashes.json` records the SHA-256, git blob SHA, and
size of every excerpt and every cited source file.

## How the rules were built

1. Read the fee-market code paths end to end:
   `TxQ.h` (setup defaults, fee metrics, queue ordering, retry and
   drop penalties), `TxQ.cpp` (fee-level computation, escalation,
   queue admission, draining, eviction, series rescue, direct apply,
   metrics, RPC, configuration), `LoadFeeTrack.h` and
   `LoadFeeTrack.cpp` (local/remote/cluster load factors, raise and
   lower, load scaling), `LoadManager.cpp` (the overload trigger),
   `Transactor.cpp` (base fee per signer, minimum fee),
   `FeeEscalation.md` (the in-tree design document, checked against
   the code line by line), and `Fees.h` (the ledger fee parameters).
2. Every rule carries a file:line range and a verbatim excerpt. Where
   the document and the code disagree, the pack follows the code and
   records the divergence as a finding (F-01, F-05).
3. Absence findings were checked with `grep` over the pinned tree
   (probe I-01): no exponential function in the escalation path, no
   ceiling on the escalation multiplier, no per-account fee
   discount, no queue-size hard cap beyond the dynamic maximum.

## How the simulator works

`src/fee_market_model.py` reads `configs/scenarios.json` and applies
the pinned arithmetic with integer math, exactly as the C++ does:
required level 256 at or below target, otherwise multiplier times
current squared over target squared; fee level is fee drops times 256
over the base fee (10 drops times one plus the signer count); load
scaling multiplies by the factor over 256 with the privileged 4x cap;
the minimum processing level is the lowest queued level plus one when
the queue is full. Outcomes are classified priced / queued / evicted /
stalled by applying the code's checks in the order the code applies
them. No live node is involved.

## What is modelled vs verified

- VERIFIED: read from the pinned source, with a grep-verified
  citation and a verbatim excerpt.
- SPECIFIED: stated in the cited public documentation and
  cross-checked against code where the code speaks to it.
- MODELLED: an output of the deterministic simulator on the stated
  inputs, using only pinned constants.
- UNTESTABLE: not decidable from the pinned source alone; recorded
  as a gap, never asserted as a fact.

## Reproduction

```bash
bash scripts/run_all.sh         # exit 0 only if every check passes
bash scripts/clean_reproduce.sh # fresh-copy reproduction (run twice)
bash scripts/verify_digests.sh  # every digest in SHA256SUMS must match
```

`run_all.sh` extracts the excerpts from the pinned checkout when it
is available, validates the model config, runs the simulator and the
probe, writes the run summary and manifest, and captures the full
`verify_digests.sh` output into `outputs/verify-digests.log`.
`clean_reproduce.sh` copies the pack to a throwaway directory, drops
all generated outputs, re-runs the suite from scratch twice, and
compares the fresh numbers with the shipped ones; the two fresh runs
are kept as `outputs/fresh-clone-*` and `outputs/fresh-clone-2-*`.

## Limits

No live node was run and no real network load test was performed
(gaps G-01, G-02). All load, queue, and pricing behaviour is derived
from the pinned code and modelled deterministically; real deployments
may differ where configuration overrides the defaults (every Setup
value is configurable) or where the fee vote changes the base fee.
