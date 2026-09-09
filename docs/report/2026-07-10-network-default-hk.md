# 2026-07-10 — Default initial network switched: dcsbm → hk

**Decision:** `ExperimentConfig.networkType` default changed from `dcsbm` to `hk` (Holme-Kim,
`m=3, A=1, pt=0.3` — already implemented in `NetworkFactory.java`, just not previously the
default). Matches the `journal.tex` (Latex-Journal-June) baseline network exactly: that paper's
stylized-fact validation and backfire-effect demonstration both use "Holme–Kim network with
`p_t = 0.3`" (`docs/journal.tex:723,818`).

**Rationale (per user instruction):** DC-SBM was this paper's (wssit2026/moderate-conduit study)
own network, adopted specifically to host mid-scale hubs at equilibrium
(`docs/research-direction.md` §1 "network = precondition"). It was never validated as a
general-purpose default — it was a study-specific structural requirement. For redoing the
validation/calibration work (stylized-fact checks, parameter sweeps), HK is the network the prior
`journal.tex` study already validated against, so it's the more defensible starting point before
re-establishing whether DC-SBM (or any other topology) is actually needed for the moderate-conduit
question specifically.

**Scope of this change (2026-07-10 session): config only.** Per explicit instruction, this is
*only* the default-value flip in `ExperimentConfig`/`NetworkFactory`'s docstring — no sweep, no
pilot, no validation-gate run has been redone against it yet. Everything in
`docs/report/2026-07-08-validation-gate-pilot.md` and `2026-07-09-oat-sweep-findings.md` (gate 1-3
results, OAT robustness findings, the alpha/hub-growth fix, the heavy-tail-at-n1000 check) was
produced under `network=dcsbm` and does **not** carry over to `hk` — those need to be re-run
against the new default before being treated as current. **Supersedes** `docs/research-direction.md`
§1a's DC-SBM-specific framing ("network is a precondition... must host mid-scale moderate hubs at
equilibrium... the current winner-take-all network does not [without DC-SBM]") as the *default*
network story; that framing was true for the DC-SBM-based validation work done so far but is not
automatically true under HK — needs re-establishing, not assumed to hold.

**Not changed:** `INITIAL_STUBBORNNESS` (currently `0.7` in this codebase vs. journal.tex's
`Stubbornness = 0.8`) and other Const-level baseline parameters were left as-is — only the network
generator default was in scope for this instruction. Flagging the stubbornness mismatch here since
it's adjacent to "align with the journal-June baseline" but wasn't part of what was asked.

**Verified:** recompile clean, `ModelTests` 28/28 pass (no test asserted `dcsbm`-specific
behavior), smoke run (`n=100, steps=200`) confirms `network.NetworkFactory` now constructs
`Holme-Kim network (m=3, A=1, gamma=2.33, pt=0.3)` by default and the run folder tag carries no
`_nw-` suffix (hk is silent as the new default, same DEFAULTS-comparison convention as every other
field per the 2026-07-10 tag() consolidation).

**Next (not done yet, per "config only" instruction):** re-run the validation-gate pilot and OAT
sweep against `network=hk` before treating any Step-2 gate conclusion as current.
