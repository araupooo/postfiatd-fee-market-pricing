# Claim-to-evidence index

Every claim in this pack, its status, and the exact evidence for it.
Status meanings: VERIFIED — read from the pinned source with a
grep-verified file:line citation; SPECIFIED — stated in the cited public
documentation and cross-checked against code; MODELLED — an output of
the deterministic simulator on the stated inputs; UNTESTABLE — not
decidable from the pinned source alone.

| Claim | Status | Claim | Evidence |
| --- | --- | --- | --- |
| C-01 | VERIFIED | Fee level is fee paid times 256 divided by the base fee. | R-02, E09: `TxQ.cpp:39-66`. |
| C-02 | VERIFIED | The base fee level is 256 for a single-signed reference transaction. | R-01, E01: `TxQ.h:42-64`. |
| C-03 | VERIFIED | Above the target, the required fee level grows with the square of the open-ledger count over the square of the target. | R-08, E11: `TxQ.cpp:173-195`. |
| C-04 | VERIFIED | The escalation multiplier is the median fee level of the last closed ledger, floored at 128,000. | R-06, R-07, E10, E02: `TxQ.cpp:84-170`, `TxQ.h:78-109`. |
| C-05 | VERIFIED | The documentation says the fee level "increases exponentially"; the code computes a quadratic. | R-09, E40: `FeeEscalation.md:14-68`; E11: `TxQ.cpp:173-195`. |
| C-06 | VERIFIED | The queue orders by fee level descending; equal levels order by transaction ID XOR the parent ledger hash. | R-20, E05: `TxQ.h:631-663`. |
| C-07 | VERIFIED | The maximum queue size is the larger of expected ledgers times ledgers-in-queue and the minimum queue size. | R-21, E24: `TxQ.cpp:1366-1425`. |
| C-08 | VERIFIED | One account may queue at most 10 transactions, except when filling an expiration-based sequence gap. | R-23, E15: `TxQ.cpp:384-462`. |
| C-09 | VERIFIED | A transaction with a LastLedgerSequence must promise at least 2 ledgers past the open ledger to be queueable. | R-24, E15: `TxQ.cpp:384-462`. |
| C-10 | VERIFIED | A replacement must pay strictly more than the old fee level plus 25%. | R-27, E21: `TxQ.cpp:875-935`. |
| C-11 | VERIFIED | A queued transaction gets 10 retry attempts; an account whose transaction retried out gives its other transactions at most 2 attempts. | R-31, E07, E06: `TxQ.h:575-590`, `:665-690`. |
| C-12 | VERIFIED | When the queue is full, a newcomer is admitted only if its fee level beats the lowest-fee account's average fee level. | R-33, E23: `TxQ.cpp:1243-1320`. |
| C-13 | VERIFIED | A series rescue clears a stuck account queue when the summed fee levels cover the escalated series level. | R-34, E17: `TxQ.cpp:518-560`. |
| C-14 | VERIFIED | Load constants: normal factor 256, raise and lower steps of 1/4, maximum factor 256,000,000. | R-14, E33: `LoadFeeTrack.h:141-148`. |
| C-15 | VERIFIED | A privileged submitter pays the remote factor while the local factor is below four times remote. | R-18, E36: `LoadFeeTrack.cpp:84-112`. |
| C-16 | VERIFIED | The local load fee rises only after two consecutive overload signals; the load manager triggers on job-queue overload. | R-15, R-19, E34, E37: `LoadFeeTrack.cpp:32-58`, `LoadManager.cpp:176-190`. |
| C-17 | SPECIFIED | Transaction fees are destroyed, not paid to anyone. | R-39, `docs/citations.md` S-01: transaction-cost documentation, 24 Nov 2026. |
| C-18 | SPECIFIED | A transaction submitted through an admin connection bypasses load scaling and needs only the un-scaled minimum fee. | R-40, `docs/citations.md` S-02: transaction-cost documentation, 24 Nov 2026. |
| C-19 | MODELLED | On a cold-start ledger the 33rd transaction needs fee level 136,125 (about 5,317 drops at a 10-drop base). | R-43; threshold table; scenario S-13; `outputs/derived/fee-market-results.json`. |
| C-20 | MODELLED | Slow consensus halves the expected ledger size and raises the required level for the same load from 46,080 to 184,320. | Scenario S-12; `outputs/derived/fee-market-results.json`. |
| C-21 | MODELLED | Against a full queue, a 512-level transaction displaces the cheapest transaction while a 256-level one is rejected. | Scenario S-03; `outputs/derived/fee-market-results.json`. |
| C-22 | MODELLED | A series rescue clears the account queue when the summed fee level 1,000,768 covers the escalated requirement 903,750. | Scenario S-05 run B; `outputs/derived/fee-market-results.json`. |
| C-23 | UNTESTABLE | Live network fee behaviour under real load: actual fee levels paid and queue occupancy in production. | R-45; no live node was run (gap G-01). |
| C-24 | UNTESTABLE | Real validator queue divergence under load: whether peers with identical open ledgers reach identical queue decisions. | No live deployment data (gap G-02). |
