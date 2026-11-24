# Gap register

Things this pack does not establish, because the pinned source alone
cannot decide them. Every gap is source-only: it names what is missing
from the code or the evidence, not what a live deployment might show.

| Gap | Gap | Why it is a gap |
| --- | --- | --- |
| G-01 | No live node was run: actual fee levels paid and queue occupancy in production are unmeasured. | The simulator models the code's arithmetic; it cannot observe a running network (claim C-23). |
| G-02 | No live-network load test: whether peers with identical open ledgers reach identical queue decisions is untested. | Queue decisions depend on each peer's local open ledger and load; the code asserts convergence but no run demonstrates it (claim C-24). |
| G-03 | FeeEscalation.md is not verified against the code by any test in the pinned tree. | The document's minimum 5 / target 50 contradicts the code's 32 / 256 (F-05); nothing in the tree fails when the document drifts. |
| G-04 | No measurement of real queue occupancy or eviction frequency in production. | The queue maximum and eviction rules are code-derived; their operating frequency is unknown. |
| G-05 | The 2^21 series-overflow guard is untested in practice. | The guard exists in code (TxQ.cpp:197-232, E12) but no realistic series reaches it; its behaviour at the boundary is modelled, not observed. |
| G-06 | Which accounts hold privileged (tapUNLIMITED) submission rights is deployment configuration, not code. | The code only checks the flag (LoadFeeTrack.cpp:84-112, E36); the pack cannot say who holds it on any deployment. |
| G-07 | The fee-vote path that sets the 10-drop base fee is outside TxQ and LoadFeeTrack. | The base fee is a ledger parameter (Fees.h, E44); how it changes under fee voting is not covered here. |
| G-08 | The escalation multiplier has no ceiling in update(): sustained overload can push the median without bound. | update() floors the multiplier at 128,000 but never caps it (TxQ.cpp:84-170, E10); the long-run behaviour is modelled, not observed. |
