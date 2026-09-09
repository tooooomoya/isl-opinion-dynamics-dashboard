# 2026-07-08 — Relay/reattribution ablation diagnostic

**Context:** `docs/research-direction.md` §3 items 1–2 identify relay distortion (quote-repost /
λ-blend) plus the reattribution bypass (`relAttrib`) as the mechanism required to sustain Type-2
(connected-but-hostile) polarization — without it, §2's diagnosis predicts the model collapses to
slow Type-1 fragmentation ("naively run, it produces Type 1 and only looks like Type 2").

## Observation prompting this entry

Running without relay distortion, Type-2-*looking* outcomes (network stays connected, hostility
persists) were still observed. Working hypothesis for why: in a sparse network, the number of
backfire/unfollow opportunities is bounded, and combined with `p_u`, the run reaches a frozen state
**before** full structural separation completes — i.e. the system may be caught mid-transition
toward Type 1, not resting at a genuine Type-2 equilibrium.

**This is not yet validated.** It matches the exact failure mode `research-direction.md` §2 warns
about (a transient state that only *resembles* Type 2). Before treating "no relay needed" as a
finding, still need to check:
1. Whether structural-separation metrics (modularity / assortativity / cross-cutting-edge fraction)
   are still trending at `t_max`, or have plateaued (plateau = real equilibrium; still-trending =
   caught mid-transition).
2. Whether the same run at 2–3× `steps` still looks like Type 2, or resolves to Type 1.
3. Network density/sparsity at the time of the observation — §4 names network sparsity as the
   single riskiest unknown in the whole redesign.

None of this has been checked yet. The ablation below is to generate runs to check it with, not a
conclusion that relay is unnecessary.

## Decision

Added `relayEnabled` (`ExperimentConfig.java`, `SimParams.java`), a single boolean master switch
covering relay distortion + reattribution + misrepresentation grievance together:

- `relayEnabled=false`: `Agent.relay()` returns a verbatim copy (`conveyed = original opinion`,
  `attrib = original author`, regardless of `couple_relay_distortion` / `rel_attrib` settings);
  the misrepresentation-grievance check in `Agent.repost()` is explicitly skipped (not just
  incidentally silenced by a zero diff).
- `relayEnabled=true`: unchanged existing behavior (distortion per `coupleRelayDistortion` /
  `relayDistortionStrength`; attribution per `relAttrib`; misrepresentation grievance active).

**Default set to `false` for this diagnostic pass** — a plain `./run.sh` now runs without relay.
This is a temporary default change, not a supersession of §3 items 1–2; it exists to produce the
comparison runs needed to check the two items above. Revert by flipping the default back to `true`
in `ExperimentConfig.java` (single line), or override per-run with `relay_enabled=true`.

Folder tag: `_norelay` when disabled (only appears when non-default, per existing `tag()`
convention).

## What this does NOT change

- `coupleOutOfBCRepost` / `outOfBCRepostProb` (§3 item 1's `P_r^out`, the ε-gate lift) is untouched
  — reposting of out-of-tolerance content still happens at the configured rate; only the *content
  distortion and attribution* of any repost is disabled.
- The contact-valence hostility channel (`updateMyself`) is untouched — only the
  misrepresentation-grievance channel goes silent, since it depends on relay distortion existing.

## Next step

Run the two checks above (separation-metric trend at `t_max`; robustness to longer `steps`) before
deciding whether §3 items 1–2 are actually load-bearing for this network/parameter regime, or
whether the sparse-network dynamics alone are sufficient. If checks show a still-trending /
non-robust result, restore `relayEnabled=true` as the default and treat this as a closed diagnostic,
not a model simplification.

---

## Addendum: block-forgetting (R8) removed entirely

**Decision:** deleted `blockRecoveryRate` / `blockedList` / the geometric-forgetting sweep from
`ExperimentConfig`, `SimParams`, and `Agent` (was `p_forget`, renamed `block_recovery_rate` earlier
this session before removal). Not a diagnostic toggle — physically removed, no revert flag.

**Why this is safe to remove outright (unlike the relay ablation above):**
1. Defaulted to `0.0` (inert) already; no run to date depended on it being non-zero.
2. Not referenced anywhere in `research-direction.md` §3's causal DAG (items 1–7). The DAG's actual
   "recovery" channel is the asymmetric-ε mechanism (§3 item 3, `bcIncRate` — tolerance recovering
   on comfortable contact), which is a distinct, load-bearing mechanism and is **untouched** by this
   removal. Block-forgetting (a specific severed tie un-severing) and ε-recovery (general tolerance
   recovering) were two separate mechanisms; only the former is removed.
3. Real-SNS grounding: blocking is observationally close to irreversible, so fixing it at "never
   recovers" (rather than sweeping a recovery-rate knob) is the more defensible default, not a
   simplifying assumption that trades away realism.

**Consequence:** `Agent.blockedUserList` (the O(1) block/candidate-exclusion membership array,
renamed from `unfollowList` earlier this session) is now the sole block-tracking structure — the
reverse-index list (`blockedList`) it existed to support is gone, so the two-structure
index/reverse-index pattern discussed earlier this session no longer applies.

---

## Addendum 2: `hostilityActive` also set to `false` (out of scope alongside relay)

**Decision:** `ExperimentConfig.hostilityActive` default changed `true` → `false`.

**Reasoning:** `hostility` has two update channels (`Agent.java`): contact valence
(`updateMyself`, independent of relay) and misrepresentation grievance (`receiveMisrepresentation`,
relay-dependent). With `relayEnabled=false`, the misrepresentation channel was already inert
(guarded explicitly in `Agent.repost()`), but the contact-valence channel was still live —
`hostility` was still being tracked, just through one channel instead of two. That's a partial,
easy-to-miss state: "relay off" did not mean "hostility off."

Per this session's working decision to strip the model back to the minimal opinion-propagation
question first (§ this doc's opening discussion), `hostilityActive=false` now turns off **both**
channels — `hostility` stays frozen at `0.0` for the whole run. This is grouped with the relay
ablation (same "out of scope for now, not deleted" status) since hostility-as-affective-polarization
measurement (`research-direction.md` §3 item 5) is the same y-axis the relay/reattribution mechanism
was built to sustain — reconsider both together when revisiting Type-2 measurement.

**Knobs now inert as a result (unchanged code, no effect while `hostilityActive=false`):** `lUp`,
`lDown` (contact-valence rates — `lMis` was already inert via the relay ablation above).
`bcGateAssim` is unrelated (gates FJ assimilation by bc, not hostility) and remains live.

---

## Addendum 3: Type-2 redefined — this is no longer an open ablation, it's the new frame

**This resolves the "pending validation" status of Addendums 1–2.** The relay/hostility ablation
above was originally framed as a diagnostic to check whether Type-2-*looking* outcomes (per the old
hostility-centric definition in `research-direction.md` §1) were a real equilibrium or a
mid-transition artifact. That question is now moot: **Type 2 has been redefined** (see
`research-direction.md` §1a, added 2026-07-08).

**New definition:** Type 1 (structural separation) is the base equilibrium state; Type 2 is a
moderate hub creating cross-cutting opinion flow *between* separated communities, measured
structurally (cross-cutting exposure / cross-repost fraction attributable to the hub) — not via
affective hostility escalation. Working hypothesis: this requires a scale-free-like (heavy-tailed
degree) topology.

**Consequence for `relayEnabled` / `hostilityActive`:** both stay `false`, but the justification
changes — not "temporarily disabled pending a robustness check" but **"not load-bearing for the
redefined, purely structural question."** Verbatim repost (no content distortion) already delivers
opposing-camp content to a hub's audience; that is sufficient for the cross-cutting-flow question.
Distortion and affective hostility were mechanisms specific to the old backfire/reattribution-bypass
story, which is no longer the object of study.

**Next step:** enter the Step-2 validation-gate phase (`research-direction.md` §0's working method)
under this new definition — confirm the network reaches a structurally-separated (Type-1) base
state, and that a moderate hub produces measurable cross-cutting exposure attributable to it,
ideally checked across network types (scale-free-like vs. not) to test the scale-free dependency
hypothesis.
