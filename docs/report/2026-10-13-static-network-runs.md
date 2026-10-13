# 2026-10-13 — Static network (rewire off)

## Decision (user)
Stop rewire for now: static follow network. Run on WS and directed-BA (`dba`) starts. Rationale: the Q values stayed even (all actions ≈ same), and the rewire channel confounds the diagnosis; with a static network the three remaining actions (post, like, reshare) can be examined on their own. Supersedes the rewire-gate pilots as the working configuration (the gate stays in the code, used when `rewire=true`).

## Implementation
- New key `rewire` (default true). `rewire=false` removes rewire from the available actions ([Agent.chooseAction](../../src/agent/Agent.java)); exploration and softmax run over post/like/reshare. The Q table keeps its 4th column (never visited, stays at q_init).
- ModelTests: ALL PASS (new test: rewire never chosen).

## Pilots (seed 0, 20000 steps, feed 10, q_tau 0.1, q_init 7, same bins as before)
`static_ws_hop1`, `static_ws_hop4`, `static_dba_hop1`, `static_dba_hop4` — results below once finished.

## Results (seed 0, 20000 steps; end-of-run values)
| run | post / like / reshare share (end) | identity fit | recognition | attnGini / top-1% attn | Q post / like / reshare |
|---|---|---|---|---|---|
| static_ws_hop1 | .35 / .26 / .39 | .69 | .30 | .34 / .04 | 8.11 / 8.01 / 8.12 |
| static_ws_hop4 | .30 / .31 / .38 | .68 | .09 | .28 / .03 | 7.42 / 7.38 / 7.41 |
| static_dba_hop1 | .42 / .26 / .32 | .66 | .10 | .86 / .40 | 7.39 / 7.37 / 7.41 |
| static_dba_hop4 | .43 / .20 / .37 | .65 | .08 | .88 / .39 | 7.29 / 7.27 / 7.31 |

Per-agent Q minus the agent's own mean over (post, like, reshare), by follower tier (dba; WS agents all fall in 10–49 followers):
| tier | n | post | like | reshare | mean recognition (hop1) |
|---|---|---|---|---|---|
| 0 followers | 104 | −.001 | −.001 | +.002 | 0.00 |
| 1–9 | 532 | +.005 | −.006 | +.002 | .03 |
| 10–49 | 301 | +.009 | −.050 | +.041 | .21 |
| 50+ | 63 | −.001 | −.076 | +.076 | .67 |
(WS hop1: post +.031, like −.071, reshare +.041.)
- With a static network a signal appears: **like is consistently the lowest-valued action, and the gap grows with follower count** (hubs: like −.08 to −.17, reshare +.08 to +.15). Agents with no followers stay exactly indifferent (no one can like them, so no action changes recognition).
- Reshare ≥ post for hubs: a reshare is a new post of the same X, so it can earn its own likes without the originator-competition of an original; post does not beat reshare in any tier.
- The Q means are still rising at 20000 steps (WS hop1 7.4 → 7.7 → 8.1): learning has not converged, so the gaps are lower bounds.
- Attention: WS is flat (Gini .3, top-1% 4%), dba concentrates (Gini .86, top-1% 40%) exactly as built, now without any rewiring collapse.

## 2026-10-13 — Post life L: 100 and 200 (user)
- Decision: keep the reaction-based post life (alive iff step − lastReactionStep ≤ L). A display-based clock (die when not shown for D steps, grace D) was discussed and deferred. Supersedes nothing; L = 50 stays the default.
- Pilots (static network, rewire off, hop 1, feed 10, seed 0, 20000 steps, same Q settings/bins as static_*): `life100_dba_hop1`, `life200_dba_hop1`, `life100_ws_hop1`, `life200_ws_hop1`; compare with `static_dba_hop1` / `static_ws_hop1` (L = 50).

### Result: post life L = 50 / 100 / 200 (static, hop 1, seed 0, end of 20000 steps)
| run | alive posts | mean recognition | attnGini / top-1% attn | Q−mean (post / like / reshare), 10–49 followers | same, 50+ followers |
|---|---|---|---|---|---|
| dba L50 | 3.8k | .10 | .86 / .40 | +.009 / −.050 / +.041 | −.001 / −.076 / +.076 |
| dba L100 | 7.5k | .19 | .86 / .38 | +.030 / −.081 / +.051 | +.078 / −.031 / −.046 |
| dba L200 | 14.5k | .27 | .86 / .39 | +.075 / −.122 / +.047 | +.072 / −.087 / +.015 |
| ws L50 | 4.4k | .30 | .34 / .04 | +.031 / −.071 / +.041 (all agents) | – |
| ws L100 | 8.2k | .43 | .40 / .04 | +.019 / −.025 / +.006 | – |
| ws L200 | 15.4k | .62 | .40 / .04 | +.006 / −.062 / +.056 | – |
- Alive posts scale ~linearly with L; recognition rises (more surviving likes) and saturates less for peripheral agents. Attention concentration does not change (fixed by the network).
- Like stays the lowest-valued action at every L; its gap in the 10–49 tier widens with L in dba (−.05 → −.08 → −.12).
- In dba, post overtakes reshare as L grows (post +.075 vs reshare +.047 at L200 in the 10–49 tier; at 50+ post +.07, reshare +.02) — with longer life an original post accumulates more likes before dying. In WS the order is not stable (reshare ≥ post at L50 and L200, post ahead at L100): single seed, treat as noise.

## 2026-10-13 — Trend rename + new "For You" (perspective similarity) with a platform-held estimate of X
Decisions (user): (1) the old "For You" is renamed **Trend** (popularity: reshare velocity, X-blind); (2) a new **For You** ranks by perspective similarity; (3) For You has its own hop filter; (4) the stage-2 idea is adopted from the start: the platform holds an *estimated* X per agent, random at the start, updated on like/reshare. (5) All existing `results/` deleted (20 GB; inherited alpha-dose-response runs included) to avoid confusion; run logs under `logs/` are kept.

**Feed.** capacity S = 10 splits into chrono (remainder, followees' posts), Trend (floor(trend_share·S)) and For You (floor(foryou_share·S)). Default trend_share = 0.7, foryou_share = 0 (so old configurations behave as before).

**For You, per visit of agent i.** Candidates = alive posts of authors within foryou_hop hops on the follow graph (out-edges, same BFS as Trend; foryou_hop ≤ 0 = every author, network ignored), minus own posts, minus roots already in the feed. Draw foryou slots posts without replacement with probability ∝ exp(−fy_beta·|X̂_i − X_post|) × reach-decay(d) (same decay mode as Trend). Cost is small at hop 1 (a smoke test of 3000 steps took 11 s).

**Estimate.** X̂_i starts U[−1,1] independent of the true X_i; on a like of post p: X̂_i ← (1−ρ_L) X̂_i + ρ_L X_p; on a reshare ρ_R; post leaves it unchanged (rewire is the same when on). Placeholders: **ρ_L = 0.05, ρ_R = 0.10, fy_beta = 3 (= β_h)** — not tuned, to be revisited. `fy_profile=false` scores against the true X instead (control).

Keys: `trend_share` (alias `alpha`), `trend_hop` (alias `hop`), `foryou_share`, `foryou_hop`, `fy_beta`, `fy_profile`, `rho_l`, `rho_r`. Tag adds `_fy-<share>_fyh-<hop>` (+`_fyb-`, `_fytrue`, `_rl-`, `_rr-` when non-default). `trend_share + foryou_share ≤ 1` is enforced.

Metrics: `feedTrendCountMean_*` (renamed from feedForYouCountMean), new `feedForYouCountMean_*`, new `estError` = mean |X̂ − X| (NaN when no estimates).

Smoke test (WS start, static network, trend 0, For You 0.7 at hop 1, 3000 steps, old bins): identity fit 0.78 (static Trend runs: 0.69), estError 0.27 → 0.18 (the estimates are converging toward the true X), 0 assertion errors. ModelTests: ALL PASS (new tests: hop gate, own posts, root dedup, sharp beta picks the near post, estimate update, share validation).

## 2026-10-13 — Experiment: the advantage of the new For You (Trend off)
Question (user): with Trend off, what does For You add? Design: static network (rewire off), trend_share = 0, feed 10, L = 50, 20000 steps, seeds 0–2, Q settings/bins as in the static pilots (bins not yet recomputed).
- Factor "screen" (4 arms) × start network (WS, directed BA): `chrono` (foryou_share 0: followees' posts only), `fy_h1` (For You 0.7, hop 1, estimated X̂), `fy_h2` (hop 2), `fy_h1true` (hop 1 scored against the true X: control for the cost of estimation).
- Run sets: `fyexp_<arm>_<ws|dba>_seed_...`. Outcomes: identity fit, recognition, attention Gini/top-1%, out-group exposure, opinion assortativity, estError, Q gaps by follower tier.

## 2026-10-13 — Review fixes (two model bugs) and rerun
1. **Q-learning bootstrapped from actions that cannot be taken.** The target r + γ max_a' Q(s',a') maximised over all four actions. An unavailable action (rewire when `rewire=false`; like/reshare with an empty feed) is never updated, so its Q stays at q_init; with optimistic init (q_init = 7) that frozen value floors the target and biases the other Qs (e.g. dba_hop4 had state values ≈ 7.0, i.e. right at q_init). **Fix:** [Agent.observeAndLearn](../../src/agent/Agent.java) maximises over the actions available at s' only (0 if none). Availability is now one function (`availableActions`) shared with `chooseAction`.
2. **Repeated reactions to one post.** `pickFromFeed` could return a post the agent had already liked/reshared, so the same agent could like one post many times, inflating the author's recognition and refreshing the post's life; the same for reshares (several copies of one story). **Fix:** a post can be liked at most once per agent (by post id); an agent holds at most one copy of a story (reshare once per root post; its own stories included). `pickFromFeed(action)` draws only among eligible posts; like/reshare are unavailable when no feed post is eligible (this also feeds the bootstrap target above).
- ModelTests: ALL PASS (new tests: one reaction per post; the bootstrap target ignores unavailable actions).
- **Everything measured before this fix (static, life, gate, dba, … pilots and the first fyexp runs) was generated with both bugs.** Qualitative statements in the earlier sections (e.g. "like is the lowest-valued action", Q gaps) must be re-checked; the first fyexp batch was deleted and is being rerun.

### Addendum (user): each post is shown to an agent at most once
The root of the repeated-like problem is repeated display, not only the pick. **Rule:** a post is shown in an agent's feed at most once; Agent keeps a BitSet of shown post ids, set when the post enters the feed ([Agent.addPostToFeed](../../src/agent/Agent.java)). The chrono, Trend and For You builders skip posts the reader has seen. (Chrono already showed each delivered post once because the post cache is cleared at every visit.) The like/reshare guards from the previous fix stay as a second line (one like per post; one copy per story).
- Unit is the **post**, not the story: a reshare of a story the agent already saw is a different post and can still appear (the within-feed root de-duplication is unchanged). Say if the unit should be the root post instead.
- Consequence to watch: feeds can now run short (an active agent has seen up to ~20k feed slots over a run; the alive pool is ~4–15k posts). Check the mean feed size and the share of empty feeds in the new runs; if feeds starve, the pool/reach (hop, L) becomes the binding constraint.
- ModelTests: ALL PASS (new test: six visits never repeat a post and exhaust the pool exactly). The `fyexp` rerun was restarted from scratch with this rule (a half-run batch with only the first fix was discarded).
