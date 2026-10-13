# 2026-10-13 — Parameter search for a "good" attention-economy setting (autonomous run)

Launched while the user was away. Driver: [scripts/attention_search.py](../../scripts/attention_search.py) (resumable; summaries append to `results/search/summary.jsonl`, final table `results/search/ranking.csv`, per-run logs `logs/search/`, driver log `logs/search/driver.out`, code snapshot compiled to `bin_search/`).

## Why a search, and what "good" means
The standing problem: learned action values are nearly equal (gaps ≈ 1% of the value), so the actions do not matter. The user asked for "good" settings without defining the criterion, so I fixed one (changeable):
- **Feasible** (the system is healthy): 0 assertion errors; mean feed size ≥ 0.6 × capacity and ≤ 15% empty feeds (feeds not starved by the see-once rule); mean recognition in [0.05, 0.8] (neither absent nor saturated); attention Gini ≤ 0.9 (not total concentration); alive posts > 0.
- **Rank among feasible by the relative Q gap** = visit-weighted mean over states of (max − min Q over the available actions) ÷ mean Q at the end of the run (a unitless "how much do actions differ"). Reported next to it: Q drift over the last 5000 steps (stability), mean per-agent Q range, action-share skew (1 − normalised entropy), identity fit, assortativity, estimate error.
- Caveats: the Q gap is a population mean over agents of Q (opposite agent preferences cancel; the per-agent range is also reported); a high gap says actions are valued differently, not that the setting is sociologically interesting; single seeds in stages 1–2.

## Design (all with the see-once feed rule, one-reaction-per-post, fixed Q-target; static network unless stated; 20000 steps)
Base: q_tau 0.1, q_init 7, q_eps 0.05, q_gamma 0.9, q_eta 0.1, l_ref 1000, identity-fit bins 0.63/0.71 (not recomputed), feed 10, access 0.1, β_h 3, ρ_L 0.05, ρ_R 0.10, fy_beta 3.
- **Stage 1 (42 runs, seed 0):** screen {chrono; Trend 0.7 hop 1; Trend 0.7 hop 4; For You 0.7 hop 1 / 2 / 4 (Trend off); mix For You 0.35 hop 2 + Trend 0.35 hop 4} × start network {WS, directed BA} × post life L {50, 100, 200}.
- **Stage 2 (≈ 3 × 17 runs):** one-factor-at-a-time around the top-3 stage-1 settings: q_tau {0.03, 0.3}, q_gamma {0, 0.5}, q_init 0, q_eps {0.02, 0.1}, q_eta {0.03, 0.3}, feed capacity {5, 15}, access prob {0.05, 0.2}, β_h {1, 8}, and for settings with For You: fy_beta {1, 8}, (ρ_L, ρ_R) {(0.02, 0.05), (0.2, 0.4)}.
- **Stage 3:** the overall top-4 with seeds 1 and 2; the top-2 also with rewire on (similarity-gated), seeds 0 and 1.
Resources: 16 parallel JVMs × 2 GB (32 cores / 120 GB available); run dirs are pruned to metrics/ + degrees/ (~16 MB each).

## Results
Finished 14:14 (99 runs, 0 failures, ~1 h). Full table: `results/search/ranking.csv`; raw: `results/search/summary.jsonl`. rel-gap = relative Q gap (see rubric); drift = relative change of mean Q over the last 5000 steps.

**Stage 1 (mean over the 6 runs of each screen):**
| screen | rel-gap | mean feed size | recognition | identity fit |
|---|---|---|---|---|
| chrono only | **0.071** | 6.5 | 0.28 | 0.64 |
| T1 (Trend hop 1) | 0.030 | 9.4 | 0.33 | 0.67 |
| T4 (Trend hop 4) | 0.017 | 9.6 | 0.20 | 0.68 |
| F1 (For You hop 1) | 0.036 | 9.3 | 0.32 | 0.70 |
| F2 (For You hop 2) | 0.023 | 9.6 | 0.31 | 0.79 |
| F4 (For You hop 4) | 0.026 | 9.6 | 0.34 | 0.79 |
| M (mix) | 0.018 | 9.4 | 0.28 | 0.73 |
By network: WS 0.036, dba 0.028 (recognition .36 vs .23). By post life: L50 0.028, L100 0.032, L200 0.035 (recognition .18 → .29 → .42). All 42 were feasible; the only effect of the see-once rule on feed size is for chrono (6.3–6.7 of 10 posts, ~4% empty feeds: a reader's 15 followees do not supply 10 unseen posts per visit).
- For You raises identity fit most (.79 at hop 2–4 vs .64 chrono / .67–.68 Trend) and fills the feed (9.3–9.6), as intended.

**Stage 2 (one-factor variations; the three bases were all chrono-only: chrono WS L200, WS L100, dba L200 — the ranking picked them, so For You/Trend were NOT varied; see the gap below):**
- **q_init = 0 gives rel-gap 0.39–0.48** (3 seeds consistent) — but its drift is 0.13 vs 0.02: those runs are **not converged** (Q still climbing from 0 toward ≈ 7); the gap there mostly reflects which action was tried first/more, so it is not evidence of learned preferences. I would not call it a win.
- Among converged runs (drift ≤ 0.05) the best is **chrono, WS, L200, q_eps 0.02: rel-gap 0.12 (seeds 0/1/2: 0.127/0.124/0.121)**, per-agent Q range 0.94, action-share skew 0.08–0.09. Next: L100 with q_eps 0.02 (0.10), q_tau 0.03 (0.097), baseline chrono WS L200 (0.097).
- q_gamma 0 or 0.5 *lowers* the gap (0.01–0.05; some become infeasible due to recognition > 0.5); q_tau 0.03/0.3, q_eta, β_h, feed capacity 5/15 and access prob change little (0.05–0.10).
- Rewire on (similarity-gated) with q_init 0: assortativity 0.73–0.90 emerges from a random-X start, gap 0.16–0.21 (also unconverged, drift 0.15); for q_init 7 rewire runs were not in the top set.

**Read-out.**
1. No setting makes actions strongly different: the best converged setting has actions valued ≈ 12% apart, and aggregate action shares stay within 8–9% of uniform (skew). With algorithmic feeds (Trend/For You) the gap is smaller (0.02–0.04) than with chrono (0.07).
2. Likely reason (hypothesis, not tested): algorithmic feeds fill the feed with posts that are already well matched and visible, so the next-visit reward (identity fit + recognition) depends even less on the agent's own action; chrono feeds are smaller and depend on the agent's followees' activity.
3. Longer post life (L200) raises recognition and the gap a little; more exploration floor-reduction (q_eps 0.02) helps.

**Limitations of this search (fix before trusting a ranking).** (a) The rank criterion rewards unconverged learners (q_init 0); a drift filter (≤ 0.05) is needed. (b) Stage 2 only explored chrono-based settings because stage 1 ranked them first — For You parameters (fy_beta, ρ) were never varied. (c) One seed per setting in stages 1–2. (d) Identity-fit bins were not recomputed, although For You shifts fit to ≈ 0.79 (most visits then fall in the top fit level, which flattens the state space).


## Correction (2026-10-13, from the new learning diagnostics): the Q values are NOT even at the agent level
New logging (metrics/td_log.csv, metrics/choice_gap.csv, degrees/q_table_final.csv; see the Attention Economy Model artifact) on `viz_chrono`, `viz_foryou`, `viz_chrono_q0` (WS, static, L = 200, q_init 7 or 0, seed 0). The `viz_trend` run was still going when this was written.
- **Population mean vs agent level.** Means of Q over agents (what the search ranked by, and what I reported as "gaps of 1–12%") are even because agents differ in which action they favour. Inside one agent and state, among 6,000–6,700 agent-states with ≥ 20 decisions per run, the best action leads the runner-up by a **median of 1.8 (chrono), 2.4 (For You) and 5.7 (chrono, q_init 0) Q-units** (Q ≈ 11) in 93–99% of them, and the favourite takes 84–90% of that agent's decisions. Favourites split post/like/reshare ≈ 52/18/30 % (chrono), 37/28/35 % (For You): arbitrary per agent.
- **Rewards do not depend on the action.** Mean immediate reward per action differs by at most 0.06 (post 1.108 / like 1.113 / reshare 1.102 in chrono; 1.254 / 1.202 / 1.263 with For You) against a single-decision sd of ≈ 0.2–0.27.
- **Choice vs gap.** 57–64% of all offered actions are > 0.6 below the best offered one in that decision and are chosen at the exploration floor (1.7%); the leading action is chosen 92–96% of the time. The empirical choice frequency matches the policy's theoretical probability in every bin (the policy is implemented as intended). A forced move (one available action) is excluded.
- **Why.** τ = 0.1 is small next to Q ≈ 10 (a 1% difference decides the choice) and q_init = 7 is *below* the converged value at L = 200 (r ≈ 1.1–1.3, Q* ≈ r/(1−γ) ≈ 11–12), so the first-tried action rises above untried ones and the others are left near their initial values: lock-in, not learned preference.
- **Consequence for this report.** The ranking metric (relative gap of population-mean Q) and the claim "actions are valued within 12%" describe the wrong level. A search should score agent-level quantities (lead of the favourite, share of decisions taken by it) *and* whether the favourite is justified (reward differences between actions), and q_init must be at least r_max/(1−γ) (≈ 20) to be optimistic. Earlier sections (Q gaps by follower tier, "like is the lowest-valued action") used tier means of Q and share this limitation.

### Policy by follower camp (directed-BA start, static, L = 200, seed 0; runs vizd_chrono / vizd_foryou / vizd_chrono_q0)
Five camps of 200 agents ordered by in-degree (camp 1: 0–1 followers … camp 5: 19–222). Last 5,000 steps, share of decisions post / like / reshare:
- chrono: camp 1 39/30/32 %, camp 3 51/19/30 %, camp 5 54/22/24 %; dominant action = post for 61–72 % of agents in every camp.
- For You: camp 1 35/31/34 %, camp 5 36/32/32 %; dominant action spreads across all three.
- chrono, Q from 0: camp 1 47/29/25 %, camp 5 52/25/23 %.
- **The hypothesis "low-follower agents only like" is not supported.** Camp 1 has the lowest post share and the highest like share but only by 5–10 points; its recognition is ~0.03 yet it still posts about 40 % of the time (posting is free and rewards do not depend on the action, so nothing teaches it to stop). Specialists (≥ 80 % one action): 1 % of camp 1 versus 12 % (chrono) / 28 % (For You) of camp 5.
- Q table: in 5.2–5.5 k agent-state cells with ≥ 20 decisions, the favourite leads by a median 1.3 (chrono), 1.5 (For You), 5.0 (Q from 0) Q-units and takes 69–89 % of that agent's decisions there.
- Logging added: metrics/agent_actions.csv (per agent and 500-step window), degrees/edges_final.csv. Shown in the Attention Economy Model artifact (agent-level Q map, policy by camp, network snapshot). The Trend run on this network was still running when this was written.

## 2026-10-13 — Runs on the Holme–Kim network (user): chrono / For You / Trend, rewire off
Sets `hk_chrono`, `hk_foryou`, `hk_trend` (dashboard run sets `hk_<arm>_seed_hk_<arm>`), seeds 0–2, static follow graph, `network=hk` (Holme–Kim, m = 15, A = 4, p_t = 0.05, i.e. the inherited default), 20,000 steps, post life 200, τ 0.1, Q₀ = 7, L_ref 1000, bins 0.63/0.71, feed 10. Chrono: no algorithmic share; For You: 70 % at hop 1 (Trend off); Trend: 70 % at hop 1 (For You off). Results below when finished.

### Result: Holme–Kim network, three screens × 3 seeds (hk_chrono / hk_foryou / hk_trend; static, L = 200, Q₀ = 7, τ 0.1)
Mean (seed sd) over the last 2,000 steps unless noted:
| screen | identity fit | recognition | attn Gini | post / like / reshare | reward spread between actions (single-reward sd) | favourite lead (Q-units) | favourite's share of decisions |
|---|---|---|---|---|---|---|---|
| chrono | 0.62 (.005) | 0.25 | 0.83 | 46 / 24 / 30 % | 0.076 (0.32) | 0.96 | 61 % |
| For You 70 % | 0.68 (.019) | 0.27 | 0.84 | 36 / 29 / 36 % | 0.035 (0.31) | 1.18 | 63 % |
| Trend 70 % | 0.64 (.012) | 0.26 | 0.86 | 36 / 30 / 34 % | 0.028 (0.31) | 1.02 | 61 % |
- For You raises identity fit by ~0.05 over chrono (many seed sds); Trend is in between. Recognition and attention concentration barely differ.
- Under chrono the camp with the fewest followers posts 36 %, the top camp 53 %; with Trend or For You all camps split about one third each (camp 1 and camp 5 differ by ≤ 2 points).
- Reward spread between actions is at most 0.08 in all screens and the favourite-action lock-in is present everywhere (lead ≈ 1, favourite takes ≈ 61–63 % of decisions); the screen does not change that.
- Artifact: the section "What the learner sees" was renamed **Results**, with the 3-seed table, a run picker over both networks (Holme–Kim, directed scale-free), and the agent-level views.

## 2026-10-13 — Holme–Kim, rewire ON (user): hkrw_chrono / hkrw_foryou / hkrw_trend, seeds 0–2
Same as the hk_* runs except `rewire=true` (similarity-gated: the drawn candidate replaces the oldest followee only if closer in X). Results appended below when finished.

### Result: Holme–Kim, rewire ON (hkrw_*, 3 seeds each; start → end)
| screen | identity fit | recognition | Gini | post / like / reshare / rewire | opinion assortativity | zero-follower agents | top-1 % share of follows | rewires per step | favourite lead / share |
|---|---|---|---|---|---|---|---|---|---|
| chrono | 0.78 | 0.14 | 0.92 | 32 / 19 / 25 / 24 % | −0.01 → 0.77 | 24 → 52 % | 28 → 36 % | 0.82 | 1.0 / 50 % |
| For You 70 % | 0.82 | 0.14 | 0.93 | 29 / 21 / 27 / 23 % | −0.01 → 0.72 | 24 → 50 % | 28 → 40 % | 0.74 | 0.9 / 47 % |
| Trend 70 % | 0.81 | 0.14 | 0.93 | 29 / 22 / 27 / 23 % | −0.01 → 0.76 | 24 → 51 % | 28 → 36 % | 0.84 | 0.9 / 47 % |
- The similarity gate sorts agents by value (assortativity ≈ 0.75) in every screen, but the follow graph concentrates (half of all agents end with no followers) and recognition falls from ≈ 0.26 (fixed graph) to ≈ 0.14. The screen matters little for these network outcomes; For You has slightly lower assortativity and the highest top-1 % share.
- Rewire is taken in 23–24 % of decisions; the favourite-action lock-in persists (reward spread between actions ≤ 0.065 vs sd ≈ 0.3).
- Artifact (Results): panels 2–4 now show all three feed algorithms side by side; the run picker has a "Holme–Kim, rewire on" group (camps from the follower counts at the end; snapshot = end graph).

### Rewire counts (hkrw_*, per run of 20,000 steps; three seeds)
Rewire chosen ≈ 480–515 k times per run (23–24 % of ~2 M decisions); executed (candidate found and closer than the oldest followee) ≈ 13.4–17.8 k, i.e. **2.8–3.6 % of the choices**, about 0.7–0.9 swaps per step or ~16 per agent over the run. 96–97 % of rewire choices change nothing. (Chrono 16.8 k / 15.7 k / 16.8 k; For You 13.4 k / 15.6 k / 15.5 k; Trend 17.8 k / 15.8 k / 16.6 k.) Shown in the artifact's rewire-on table and run strip.
