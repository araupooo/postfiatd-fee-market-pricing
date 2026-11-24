# Risk register

Fee spikes, queue saturation, low-fee spam, and priority inversion in
the postfiatd fee market. Severity is judged by impact on a
transaction's chance of reaching a ledger and on the network's ability
to keep moving legitimate transactions under load.

| Risk | Severity | Risk | Evidence / mitigation in the pinned code |
| --- | --- | --- | --- |
| K-01 | HIGH | Fee-spike pricing-out: at twice the target the required fee level is four times the median, so ordinary users are priced out of the open ledger during a flood. | Quadratic escalation (R-08, F-01); scenarios S-01/S-02. Mitigation: read the `fee` command before submitting and pay above the open-ledger level, or queue and wait. |
| K-02 | HIGH | Cold-start floor shock: the first escalated fee on a cold ledger is about 136,125, so a user submitting just past the target overpays by orders of magnitude. | Median floor 128,000 (R-06, R-07, F-02); scenario S-13. Mitigation: do not submit bulk transactions against a cold ledger; let the median warm up. |
| K-03 | HIGH | Queue-full eviction of high-fee transactions: a newcomer is judged against the victim account's average fee level, so a high-fee transaction sharing an account with cheap ones can be displaced. | Account-average comparison (R-33, F-03); scenario S-03. Mitigation: keep each account's queued transactions at similar fee levels. |
| K-04 | MEDIUM | Priority inversion stall: a high-fee transaction behind a low-fee predecessor cannot apply until the predecessor clears. | Sequence order beats fee order (R-30, F-04); scenario S-05 run A. Mitigation: submit sequences in order, or pay for a series rescue. |
| K-05 | MEDIUM | Stale documentation misleads operators: FeeEscalation.md says minimum 5 and target 50, the code says 32 and 256. | Doc/code divergence (R-09, R-12, F-05). Mitigation: price from the code and the `fee` command, not the document. |
| K-06 | MEDIUM | Local load-fee divergence: each server tracks its own load, so a transaction meeting one server's load fee may be dropped by others. | Load factor is the max of local, remote, cluster (R-17); SPECIFIED rule R-41. Mitigation: pay above the load fee a majority of servers would require. |
| K-07 | MEDIUM | Coordinated low-fee spam fills the queue: the per-account cap is 10, but 200 accounts can still fill the 2,000 minimum queue. | Per-account cap (R-23, F-07); scenarios S-03/S-04. Mitigation: pay above the minimum processing level when the queue is near full. |
| K-08 | MEDIUM | Series rescue lets a well-funded submitter jump the queue: one rich transaction clears a whole stuck account queue. | Series rescue (R-34, F-08); scenario S-05 run B. Mitigation: none in the code; monitor for rescue-sized fees during floods. |
| K-09 | MEDIUM | Sticky retry and drop penalties: one expired transaction marks the account, and its later transactions get dropped when the queue is 95% full. | Retry/drop penalties (R-31, R-32, F-09); scenario S-08. Mitigation: set an adequate LastLedgerSequence and avoid submitting transactions likely to fail. |
| K-10 | MEDIUM | Slow consensus halves the target and spikes required fees for the same load. | TimeLeap cut (R-11, R-13); scenario S-12. Mitigation: expect fee spikes during slow consensus and re-read the `fee` command. |
| K-11 | MEDIUM | Multi-sign underpricing: multi-signed transactions look cheap in drops but rank low by fee level. | Base fee grows per signer (R-04, R-05, F-12); scenario S-11. Mitigation: compute the fee level, not the drop count, before submitting. |
| K-12 | LOW | Tie-break unpredictability: equal fee levels order by transaction ID XOR the parent hash, changing every ledger. | OrderCandidates (R-20, F-10). Mitigation: pay a distinct fee level to order deterministically. |
| K-13 | LOW | Fee RPC staleness: the `fee` command result is instantaneous and can be out of date the moment it is read. | doRPC (R-37, F-11). Mitigation: re-read the fee immediately before submitting. |
| K-14 | LOW | No per-account fee fairness beyond the 10-transaction cap: nothing stops many accounts of one operator from dominating the queue. | Per-account cap only (R-23, F-07). Mitigation: none in the code. |
