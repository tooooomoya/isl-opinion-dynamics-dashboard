# 2026-10-12 — Stage A implemented (branch `attention-economy`, uncommitted)

Implements spec rev 9 of `2026-10-12-attention-economy-model-spec-and-code-change-plan.md` (d = 1,
absolute-distance similarity, uniform init, 2-hop rewire, mu = 0, state-based Q-learning with a
global reward). Build: `javac` per OPERATIONS.md. `test.ModelTests`: ALL PASS (new suite).
Smoke: n=300, steps=3000, ~4 s, 0 assertion errors (out-degree conserved every 1000 steps), no
NaN/Inf in any of the 115 metric columns.

## What changed
- **Agent** (rewritten): one action per visit from {post, like, reshare, rewire} by softmax over a
  private 9x4 Q table. State = (identity-fit level, recognition level). Reward = identity fit +
  recognition, both in [0,1]; Q updated at the next visit from the transition (stateful Q-learning).
  Bounded confidence, block, follow/unfollow/eviction, comfort-driven posting rate, reshare
  distortion, per-agent stubbornness: removed.
- **Post**: likes, last-reaction step, alive test. A reshare is a new post (same X, author =
  resharer, creation step = reshare step); likes on it are the resharer's.
- **AdminOptim**: follow sets are insertion-ordered queues (random initial order); `touchFollowee`,
  `frontFollowee`; alive-post pool with `sweepDead` replaces the `VELOCITY_WINDOW` cutoff (the For-You
  candidate pool is now every alive post, originals and reshares); dead posts never reach a feed.
- **OpinionDynamics**: single-action step loop; Q-learning; new metrics (below).
- **ExperimentConfig/SimParams**: rewritten; new keys `beta_h dead_after l_ref q_eta q_gamma q_tau
  q_init i_edge_lo/hi l_edge_lo/hi mu`; defaults `init_dist=uniform`, `mu=0`. Removed keys are
  silently ignored, so old `scripts/` still parse but their removed knobs are inert.
- **New metrics**: `actionShare_{post,like,reshare,rewire}`, `meanIdentityFit`, `meanRecognition`,
  `meanQ_*`, `rewire`, `likeCount`, `visitCount`, `attnGini`, `attnTop1pctShare` (cumulative
  likes+reshares received per author), `alivePosts/createdPosts/diedPosts`, `postsPerVisit`.
  Removed: follow/unfollow/block/eviction columns, bc and comfort families.

## Choices not fixed by the spec (flag if wrong)
- Rewire candidate set is built from ALL current followees including the one about to be dropped
  (the dropped agent is in the followee set, so it cannot be re-added in the same move).
- Interaction ("repost") network edge for a reshare goes resharer -> source author.
- `l_ref=300`, `dead_after=50`, `beta_h=3`, `q_eta=0.1`, `q_gamma=0.9`, `q_tau=0.5`: placeholders.
- State-bin edges are fixed thirds for now; smoke shows identity fit ~0.67-0.72, i.e. typical agents sit
  at the mid/high edge, as predicted. Edges should be set from a pilot distribution.

## First smoke observations (n=300, one seed; indicative only)
- Mean learned value of all four actions rises together (~0.46 at step 3000) and is nearly equal
  across actions: with a global reward, action values differ only through where each action leads,
  and averaged over all nine states they are not separable. Need the per-state view
  (P(rewire | low identity fit) etc.) before reading anything into action shares.
- Action shares at the end: post 0.24, like 0.33, reshare 0.14, rewire 0.29. Early steps are post/rewire
  heavy because an empty feed leaves only those two available.
- `attnGini` ~0.93 and top-1% share ~0.24 of cumulative reactions at n=300; `alivePosts` ~770 with
  L=50 and ~35 visits per step, so supply/demand (postsPerVisit ~0.38) is not yet > 1 in reactions.
  Competition for the single reaction per visit exists only through the feed's capacity truncation.

## Not done / next
- No per-state logging of the Q table or action choice yet; add before the pilot.
- Scripts and dashboard not re-tested against the new CSV columns; `scripts/` calibration code refers to removed knobs.
- Nothing committed.

## Update: per-state logging added and first pilot (default parameters)
Logging: `metrics/state_action.csv` (per 500-step window: choices per state x action, population-mean Q),
`metrics/fit_quantiles.csv` (quantiles of identity fit and recognition at visit time).
Pilot: seeds 0-4, n=1000, steps=20000, defaults (beta_h=3, L=50, l_ref=300, eta=0.1, gamma=0.9, tau=0.5, mu=0,
alpha=0.7). Output `results/pilot_stageA_default/` (not version-controlled). 0 assertion errors in all runs.
Means over seeds; values in steps 15000-20000 unless noted.

- **Learning does not differentiate actions.** Shares stay at post 0.26 / like 0.24 / reshare 0.26 / rewire 0.23.
  In the two populated states (identity fit mid/high, recognition low: 5.1M of 5.2M visits) per-action Q
  differ by <= 0.15 around ~3.0 (post and reshare slightly above rewire and like) while tau = 0.5, so
  the softmax is almost uniform. Action values did not separate because the reward is nearly the same
  whichever action was taken.
- **Recognition is ~0 for almost every agent**: median and 90th percentile are 0, mean 0.02. Likes are
  rare and concentrated, so the recognition half of the state is effectively constant (level low in 97% of visits).
- **Identity fit sits in a narrow band**: quantiles 10/33/50/67/90 = 0.52/0.63/0.67/0.71/0.76. The "low" level
  (< 1/3) is visited 0.06% of the time, so the learned "low fit => rewire" policy cannot emerge. Edges
  at the 33rd/67th percentiles are 0.63 and 0.71.
- **Attention is extremely concentrated and gets more so**: attention Gini 0.95 -> 0.98 and top-1% share of
  reactions 0.45 -> 0.69 over the run (consistent with the rich-get-richer risk recorded for beta_s and the
  velocity ranking; not yet separated from the feed's effect).
- **Network homophily rises then collapses**: opinion assortativity of the follow graph peaks at 0.55 around step 500
  and decays to 0.15 by step 20000 (disagreement 0.30 -> 0.64). Hypothesis (untested): in-edges concentrate on a few
  hubs that appear in everyone's two-hop set, overpowering the similarity weight.
- **Churn is high**: ~23 successful rewires per step with 1000 agents x 15 followees, i.e. every edge is replaced about 30 times per run.
- Supply/demand: posts per visit 0.52, ~2700 alive posts.

Implications for the next step (recommendations, not yet applied): lower tau (e.g. 0.05-0.1) or scale rewards so
Q gaps matter; set the identity-fit edges from the pilot quantiles; lower l_ref (e.g. 10-30) so recognition
spans its range; check the assortativity collapse with alpha=0 (no For-You) and a larger beta_h before reading anything into it.

## Update: pilot B (tuned learning knobs + two one-factor arms), 5 seeds each, n=1000, 20000 steps
Common change vs pilot A: q_tau=0.1, i_edge=0.63/0.71 (pilot-A terciles), l_ref=20. Arms: B_tuned (alpha=0.7,
beta_h=3), B_alpha0 (alpha=0, no For-You), B_betah8 (beta_h=8). 0 assertion errors. Seed means, steps 15000-20000.

| arm | post | like | reshare | rewire | attn Gini | top-1% reactions | assortativity (peak 500-1500 -> end) | in-degree Gini t0 -> end | top-10 followers share t0 -> end |
|---|---|---|---|---|---|---|---|---|---|
| A default | .263 | .241 | .262 | .234 | .978 | .691 | .48 -> .16 | .83 -> .97 | .28 -> .53 |
| B tuned | .254 | .249 | .245 | .253 | .971 | .743 | .21 -> .10 | .83 -> .92 | .28 -> .47 |
| B alpha=0 | .309 | .176 | .190 | .325 | .931 | .433 | .37 -> .12 | .83 -> .95 | .28 -> .51 |
| B beta_h=8 | .263 | .247 | .246 | .243 | .966 | .635 | .29 -> .13 | .83 -> .92 | .28 -> .45 |

Reading (observations; mechanisms are hypotheses unless stated):
1. **State bins now work** (identity-fit visits split 1.7M / 1.9M / 1.4M over low/mid/high), but **action choice is still
   ~uniform in every state** under alpha=0.7: per-agent Q gaps are noise-sized (the population-mean Q shown in
   state_action.csv hides per-agent differences; those are not yet logged).
2. **Only the alpha=0 arm (no For-You stream; the chronological feed from follows remains, so every agent still has a feed) learns a visibly different policy**: post .31 and rewire .33 up, like .18 and reshare .19
   down, mean rewire rate 32 vs 25 per step. With no For-You slots the feed is built from follows only, so rewiring
   directly changes what the agent sees (hypothesis: under alpha=0.7 most of the feed is independent of the agent's own
   follow list, so action -> state transitions are weak and the reward carries little action-specific information).
3. **Follower concentration rises in every arm** (in-degree Gini .83 -> .92-.97; top-10 accounts' share of follows
   .28 -> .45-.53), including alpha=0 and beta_h=8, so it is not caused by the For-You feed alone. **The assortativity
   collapse also survives alpha=0 and beta_h=8**. This is consistent with the two-hop rewire pool feeding
   preferential attachment (well-followed agents sit in many candidate sets), but no arm yet removes the two-hop pool, so
   that is untested. Follower count is not related to extremity (corr 0.04), so the hubs are not a similarity effect.
4. Attention concentration (Gini, top-1% share) is lowest with alpha=0 (.93 / .43) and highest with tuned alpha=0.7
   (.97 / .74): the feed algorithm matters for reaction concentration, though the follow-graph hubs are present in all arms.

Next candidates (not run): `rewire_pool=global` (uniform candidate) or drop-by-dissimilarity as a test of 3; log per-agent
policy dispersion; rerun the learning comparison at several alpha values (0, .3, .7) since alpha, not tau, drives point 2.

## Update: dashboard adapted to the current model
- Server and front end read the new `results.csv` columns unchanged (the CSV tail parser is column-agnostic). Changed:
  obsolete metric descriptions removed, new ones added; default cards = action shares, identity fit, recognition,
  assortativity, disagreement, attention Gini/top-1%, alive posts, posts per visit, rewire; node attributes
  `bc/pp` -> `fit/rec` (GEXF columns renamed `identityFit`/`recognition`); repost-edge homophily/hostile colouring hidden;
  `agent_snapshot_*.csv` now has `identityFit,recognition,qPost,qLike,qReshare,qRewire` instead of `bc,avgComfortRate`.
- `run.sh --name NAME` writes `logs/NAME_seed<seed>_NAME.log` so each arm is a separate dashboard run set (the dashboard
  pairs a run set with `results/<results_subdir>/` through the tag in the log name, so use `results_subdir=NAME`).
  Retroactive log stubs were created for the four pilot arms (`pilot_stageA_default`, `pilot_B_tuned`, `pilot_B_alpha0`, `pilot_B_betah8`).
- Verified: every `/api/*` endpoint returns 200 with valid JSON on a 500-agent, 10000-step GEXF-enabled run; inline JS passes `node --check`.
  Not verified: visual rendering in a browser. The pilots were run with `log_gexf=false`, so their Network tab is empty.

## Update: why adaptive homophily is weak (diagnostic on `viz_tuned`, seed 0)
The new followee IS chosen with weight exp(-beta_h * |x_i - x_m|) (Agent.rewire); the DROP is not similarity-based (oldest-reacted
followee first; with 1 reaction per visit and ~70% of the feed from For-You, followees are reacted to rarely, so the queue is
close to follow-time order). Measured over 200 sampled agents on the follow graph:

| step | two-hop pool size | top-10 hubs' share of pool | best available |dx| | expected |dx| of the pick (beta_h=3) | mean |dx| over follow edges (random = 0.667) |
|---|---|---|---|---|---|
| 0 | 46.5 | 0.14 | 0.03 | 0.28 | 0.69 |
| 5000 | 16.4 | 0.39 | 0.34 | 0.49 | 0.62 |
| 20000 | 14.8 | 0.42 | 0.39 | 0.54 | 0.63 |

The candidate pool collapses from ~47 to ~15 agents and 40% of it is the same ten hubs, so even the most similar available candidate is
0.39 away on average: the similarity weight has little to select from. Conclusion: the weakness is in the candidate pool (and the blind drop), not in the
weighting formula. Candidate fixes (not applied): wider pool (global or mixed with feed authors), similarity-based drop, larger beta_h only helps if the pool is wider.

## Update: is 20000 steps enough for the agents to learn Q? (viz_tuned, seed 0)
No, but length is not the bottleneck; the learner locks in.
- Budget: ~2000 visits per agent over 20000 steps; ~95% fall in three states (0, 3, 6; ~134 / 105 / 235 updates per action). The six rarer
  states get 8-29 visits per agent in the whole run (2-7 per action), so they are unlearnable at any practical length.
- Controlled test (one agent, constant feed with identity fit 0.67, same parameters, tau = 0.1, Q initialised to 0): within ~300 visits one action reaches
  Q = 6.70 (= r/(1-gamma), the fixed point) and the other three stay at 0.0-0.2 and are never tried again. With rewards >= 0 and Q starting at 0, whichever
  action happens to be tried first looks best forever. Population-mean Q in the busy states (~1.5) is that picture averaged: one action near 6.7 and three near 0 (6.7/4 = 1.7).
- This matches the Q map: each agent has a strong favourite (lead 0.56) but the favourites are spread evenly (251/278/225/246), i.e. arbitrary, set by early random choices.
  So the action shares in pilots A and B do not measure learned preferences at all.
- Same test with q_init = 7 (optimistic start): all four actions stay equal at 6.70 (no lock-in; with a constant environment no action is better, as it should be).
Recommended before any further pilot: optimistic init (q_init ~ r/(1-gamma) ~ 7, or lower gamma and scale accordingly) and/or an exploration floor; decide bin edges so the busy states are distinct;
consider whether the rare states are worth keeping.

## Update: exploration floor added (`q_eps`, default 0.05)
With probability `q_eps` an agent picks uniformly among its available actions; otherwise softmax as before. Tagged in the folder name when non-default;
ModelTests cover the floor (`ALL PASS`). Single-agent lock-in test (constant feed, tau = 0.1, Q initialised to 0) re-run with the floor (Q of post/like/reshare/rewire in the visited state):
visit 300: 1.5 / 2.2 / 1.3 / 6.3; visit 1000: 4.2 / 4.3 / 2.7 / 6.7; visit 2000: 5.9 / 6.1 / 5.7 / 6.7; visit 3000: 6.7 / 6.7 / 6.6 / 6.7.
The floor works (the untried actions catch up through bootstrapping) but slowly: at the ~2000 visits an agent gets in a 20000-step run, the first-chosen
action still leads by ~0.6, which at tau = 0.1 is still a near-deterministic choice. The floor alone therefore removes permanent lock-in but not the early-choice bias;
pairing it with an optimistic start (`q_init` ~ 7) or a higher `q_tau` would remove it. Not yet re-piloted.

## Update: pilot C (exploration floor), 5 seeds each, n=1000, 20000 steps, tuned knobs (tau 0.1, edges 0.63/0.71, l_ref 20), q_eps = 0.05
Arms: `pilot_C_eps` (floor alone) and `pilot_C_eps_opt` (floor + q_init = 7). 0 assertion errors. Seed means, steps 15000-20000.

| | action shares (post/like/reshare/rewire) | Q in busy state 6 (post/like/reshare/rewire) | per-agent lead of top action over runner-up | agents' favourites (post/like/reshare/rewire, 5 seeds pooled) | assortativity early -> end |
|---|---|---|---|---|---|
| B tuned (no floor) | .254/.249/.245/.253 | 1.51/1.56/1.49/1.47 (mean over agents of a one-hot-like pattern) | 0.56 (single seed) | 251/278/225/246 (single seed) | .21 -> .10 |
| C floor | .249/.251/.245/.255 | 3.98/3.92/3.98/4.02 | 0.45 | 1262/1215/1235/1288 | .25 -> .21 |
| C floor + q_init 7 | .252/.249/.250/.249 | 7.14/7.13/7.14/7.14 | 0.021 | 1318/1234/1254/1194 | .55 -> .02 |

Reading: the floor removes lock-in (value of every action is now ~equal in every state, per agent and in the population). With the optimistic start the four
values agree to within ~0.02, i.e. each agent's lead over its runner-up (0.021) is noise-sized: **agents learn that the four actions are worth the same.**
That is a finding about the model as specified, not a fault of the learner: reward = identity fit + recognition is set by the feed (platform-built, mostly independent
of the agent's own last action) and by rare likes, so no action reliably changes the next state. Action shares sit at exactly 25% in every seed. The homophily collapse
persists (assortativity 0.02 at the end with the optimistic start).
Open question for the design: what should make an action matter? Earlier pilot B suggested the For-You share (alpha) does: at alpha = 0 rewire/post gained share. Not re-run with the lock-in fix.

## Update: do high-follower agents learn "post"? (pilot C final snapshots, 5 seeds x 1000 agents)
Per-agent quantities from `agent_snapshot_final.csv`; postAdv = Q(post) - mean Q(other three), each averaged over the agent's 9 states.
| follower group | n | mean followers | recognition | postAdv (floor) | share preferring post (floor) | postAdv (floor + q_init 7) | share preferring post (floor + q_init 7) |
|---|---|---|---|---|---|---|---|
| bottom 50% | 4033 | 0 | 0.00 | -0.02 | .24 | 0.00 | .26 |
| 50-90% | 500 | 1 | 0.02 | +0.07 | .28 | - | - |
| 90-99% | 417 | 74 | 0.22 | +0.32 | .34 | +0.31 | .43 |
| top 1% (top 10 per seed) | 50 | 867 / 949 | 0.94 / 0.97 | +0.81 | .42 | +0.43 | .44 |
Reading: the expected direction holds (advantage rises with followers; corr(log followers, postAdv) = 0.27 / 0.44; recognition tracks followers, corr 0.85 / 0.97),
but even the top-10 hubs prefer post only 42-44% of the time vs 25% chance, so post is not a major strategy for them.
Likely reasons (hypotheses): (1) hubs' recognition is already saturated (0.94-0.97 with l_ref = 20), so another post cannot raise reward;
(2) half the population has zero followers and a post then reaches others only through the For-You stream, which ranks by reshare velocity and so never surfaces a fresh post from a small account (cold start);
(3) the reward is a stock (likes on surviving posts), not the gain from the action.
Candidate checks/changes (not applied): raise l_ref (300-1000) to remove saturation; give the For-You stream a cold-start slot for fresh posts.

## Update: Watts-Strogatz start + rewire candidates = originators of feed posts not yet followed (spec change, user 2026-10-12)
- `network=ws` is now the default (`ws_out=15` out-degree for every agent, `ws_beta=0.1`; note the existing WS generator adds edges only to the next K/2 agents, so the factory passes K = 2*ws_out).
  At t = 0: in-degree Gini 0.06, max followers 20 (no initial hubs).
- Rewire candidates: originators (`Post.getRootAuthorId()`; for a reshare, the author of the post it traces back to, not the resharer) of posts in the agent's current feed, excluding self and current followees;
  new followee drawn with weight exp(-beta_h * |x_i - x_m|); the dropped followee is still the front of the queue. Replaces the two-hop pool.
- Tests: ALL PASS (new rewire and WS tests).
- Smoke (seed 0, n=1000, 20000 steps, tuned knobs + q_eps 0.05 + q_init 7, 0 assertion errors; run set `ws_orig`):
  follower in-degree Gini 0.06 -> 0.983, **97% of agents end with zero followers**, max followers 987 of 1000 (a star-like collapse onto a few accounts);
  assortativity 0.11 (step 100) -> 0.51 (step 500) -> 0.10 (step 20000); attention Gini 0.84 -> 0.98, top-1% share of reactions 0.64.
  Reading (hypothesis): 70% of each feed is the For-You stream, which ranks by reshare velocity, so every agent sees the same few popular posts and picks followees from the same
  few originators; popularity then compounds. The similarity weight cannot help because the candidate set is the same for everyone.

## Update: restricting the For-You reach to near hops (`hop`), WS start, rewire from feed originators; seed 0, n=1000, 20000 steps
Common: tuned knobs (tau 0.1, edges 0.63/0.71, l_ref 20), q_eps 0.05, q_init 7, alpha 0.7, `feed_decay_mode=exp`, lambda 0.11. Only `hop` differs (it caps the BFS depth over the follow graph from which For-You candidates are drawn).
Run sets: `ws_orig` (hop 4, the default), `ws_hop2`, `ws_hop1`. One seed each: read as indicative, not as a comparison with error bars.
| | hop 4 | hop 2 | hop 1 |
|---|---|---|---|
| follower in-degree Gini (end) | .983 | .983 | .976 |
| agents with zero followers | 97% | 97% | 85% |
| max followers / top-10 share of follows | 987 / .64 | 982 / .62 | 958 / .55 |
| assortativity at 500 / 5000 / 20000 | .51 / .24 / .10 | .50 / .14 / .08 | .41 / .51 / .36 |
| disagreement (end) | .61 | .54 | .38 |
| mean identity fit (steps 15000-20000) | .67 | .70 | .74 |
| rewires per step | 20 | 13 | 6 |
| action shares post/like/reshare/rewire | .26/.25/.25/.24 | .26/.25/.25/.25 | .27/.24/.26/.23 |
Reading: hop 2 behaves like hop 4 (same collapse onto a few accounts). Only hop 1 keeps homophily (assortativity ends at .36, not .10) and softens, but does not remove, the concentration
(still Gini .976, a few accounts followed by ~95% of agents). Hypothesis: at hop >= 2 the For-You stream reaches the already-popular accounts through followees-of-followees, so everyone
meets the same originators; at hop 1 the only strangers an agent can meet are originators of posts reshared by its followees.
Action shares remain ~25% each in all three: the "actions do not matter" result is unchanged by the hop.

## Update: random start network (`network=random`, new key `random_p`, default 0.015 = mean out-degree ~15), seed 0, same settings as the WS runs
Run sets `rand_hop4`, `rand_hop1`. Directed Erdos-Renyi: out-degree mean 14.9 (min 5), initial in-degree Gini 0.15 (WS: 0.06). Tests ALL PASS.
| | WS hop 4 | WS hop 1 | random hop 4 | random hop 1 |
|---|---|---|---|---|
| zero-follower agents (end) | 97% | 85% | 94% | 80% |
| in-degree Gini (end) | .983 | .976 | .983 | .975 |
| top-10 share of follows | .64 | .55 | .62 | .59 |
| assortativity 500 / 5000 / end | .51 / .24 / .10 | .41 / .51 / .36 | .39 / .11 / .08 | .47 / .54 / .33 |
| disagreement (end) | .61 | .38 | .52 | .39 |
| identity fit | .67 | .74 | .70 | .75 |
| rewires per step | 20 | 6 | 13 | 4 |
Reading: the start network barely matters; `hop` does. Both start networks collapse onto a few accounts at hop 4 and keep homophily (assortativity ~.33-.36) at hop 1. Action shares ~25% each in all four. One seed each.

## Update: recognition made steeper for small audiences (new keys `recog_lambda`=2, `recog_mix`=0.5; `l_ref` now scales the slow term)
recognition = mix * (1 - exp(-likes/lambda)) + (1 - mix) * min(1, ln(1+likes)/ln(1+l_ref)). One like is worth 0.24 at l_ref = 1000 (it was 0.23 at l_ref = 20 under the pure log but saturated after ~20 likes); 100 likes 0.62 vs 1000 likes 1.0, so influencers still differ. Tests ALL PASS.
Run `ws_hop1_rec` (WS, hop 1, seed 0, l_ref 1000) vs `ws_hop1` (pure log, cap 20). Final agents by follower count:
| followers | n (old / new) | share with any recognition (old / new) | mean recognition (old / new) |
|---|---|---|---|
| 0 | 850 / 803 | 0 / 0 | 0 / 0 |
| 1-9 | 98 / 128 | .03 / .05 | .007 / .012 |
| 10-99 | 24 / 45 | .58 / .51 | .20 / .17 |
| 100+ | 28 / 24 | .96 / .96 | .79 / .70 (p90 1.00 / .87) |
Action shares and the preferred-action split are unchanged (~25% each). Conclusion: reshaping the reward does not reach peripheral agents because ~80-97% of them have zero followers and so get zero likes: there is nothing for any reward shape to
scale. The blocker is exposure of their posts (the For-You stream ranks by reshare velocity, so a fresh post from a small account is never surfaced), not the reward function.

## Update: homophilous start network (`network=homophily`, keys `hom_out`=15, `hom_gamma`=2); seed 0, 20000 steps
Every agent follows exactly `hom_out` others drawn without replacement with weight exp(-hom_gamma*|x_i - x_j|) (Efraimidis-Spirakis sampling); agents are now created before the network (other start networks unaffected: separate RNG streams).
Initial assortativity: gamma 0 -> 0.01, 2 -> 0.64, 10 -> 0.97 (gamma 5 ~0.9). Default 2. In-degree is not controlled (central agents get a few more followers: initial in-degree Gini 0.16). Tests ALL PASS.
Run sets `hom_hop4`, `hom_hop1` (tuned knobs, l_ref 1000, q_init 7, one seed each); random-start runs repeated for reference.
| | random hop 4 | random hop 1 | homophily hop 4 | homophily hop 1 |
|---|---|---|---|---|
| assortativity step 0 / 500 / 5000 / end | -.01 / .39 / .11 / .08 | -.01 / .47 / .54 / .33 | .64 / .72 / .21 / .11 | .64 / .76 / .67 / .62 |
| disagreement start -> end | .68 -> .52 | .68 -> .39 | .23 -> .55 | .23 -> .26 |
| zero-follower agents (end) | 94% | 80% | 97% | 74% |
| top-10 share of follows | .62 | .59 | .60 | .48 |
| identity fit (steps 15000-20000) | .70 | .75 | .70 | .79 |
Reading: with a 4-hop For-You reach, a homophilous start is destroyed (.72 -> .11) by the same pile-up onto a few accounts; with a 1-hop reach it is kept (.64 -> .62). So the 1-hop reach preserves homophily that is already there
and builds only part of it from a random start (random hop 1 ends at .33).

## Update: Q values in the homophily-start runs (final window, q_init 7, tau 0.1, eps 0.05; seed 0)
Population-mean Q in the busy state (identity fit high, recognition low; 41k visits in the last 500-step window for hom_hop1): post 8.21 / like 8.09 / reshare 8.13 / rewire 8.09. Other states: leads of 0.00-0.02.
State values rise with identity fit (hom_hop1: 7.0 in the low-fit state, 7.2 mid, 8.2 high), i.e. the learner has learned the value of being in a well-matched feed, not what to do about it.
Action gaps are <= 0.12 on values of 7-8 (about 1%). Per-agent: mean lead of an agent's top action over its runner-up 0.11 (hom_hop1) / 0.04 (hom_hop4) / 0.08 (ws_hop1);
favourites spread evenly (241/236/274/249). The one consistent hint across runs: post is (slightly) best in the busy high-fit state (+0.09 hom_hop1, +0.05 hom_hop4, +0.05 ws_hop1).
Interpretation unchanged: the four actions are worth about the same to an agent under the current reward and exposure.

## 2026-10-12 — Feed capacity default 15 → 5 (user decision)
- `feed_capacity` default is now **5** ([ExperimentConfig.java:58](../../src/experiment/ExperimentConfig.java#L58)). At alpha = 0.7 the split is floor(0.7·5) = **3 For-You + 2 chrono**. (At 15 it was 10 + 5.)
- The chrono window (`postCash`, a FIFO) is also sized by `feed_capacity`, so it shrinks from 15 to 5 posts.
- Why: a smaller feed makes attention scarcer, so the competition for the few slots is sharper. This also gives each post a bigger share of the one reaction per visit.
- Supersedes: the "max feed 15" figure in earlier pilots. All earlier pilots (hom_hop1, hom_hop4, ws_hop1 etc.) used 15 and are not comparable without re-running. Pass `feed_capacity=15` to reproduce them; the run tag adds `_fc-15` for non-default values.
- `ModelTests`: ALL PASS after the change.

### Feed 5 vs 15 (homophily start, seed 0, 20000 steps; run sets fc5_hop1 / fc5_hop4 vs hom_hop1 / hom_hop4)
Values at step 20000 (assortativity also at step 10000). Action shares are single-step values, so they are noisy.
| run | assort@10k / end | identity fit | attnGini | top-1% attn share | Q post / like / reshare / rewire |
|---|---|---|---|---|---|
| hom_hop1 (15) | .64 / .62 | .78 | .93 | .64 | 7.28 / 7.26 / 7.28 / 7.26 |
| fc5_hop1 (5) | .64 / .53 | .75 | .90 | .63 | 7.34 / 7.28 / 7.31 / 7.29 |
| hom_hop4 (15) | .15 / .11 | .69 | .97 | .69 | 7.08 / 7.06 / 7.07 / 7.06 |
| fc5_hop4 (5) | .20 / .12 | .66 | .95 | .78 | 7.12 / 7.09 / 7.11 / 7.10 |
- Feed size 5 does not change the picture: hop 1 holds homophily, hop 4 destroys it; attention stays concentrated (Gini .9+).
- Post leads the other Q by 0.03–0.06 in all four runs (about 0.05 larger spread than before at hop 1), still ~1% of the value: no real action learning yet.
- Hop 1 assortativity decays somewhat faster at 5 (.53 vs .62).

## 2026-10-12 — Feed capacity back to 10; directed scale-free start network (`network=dba`)
- `feed_capacity` default **5 → 10** (user decision). At alpha 0.7: 7 For-You + 3 chrono. Supersedes the 5 setting above; the fc5 runs stay as a comparison only.
- New start network `dba` ([DirectedBANetwork.java](../../src/network/DirectedBANetwork.java)): growth model. Agents arrive in id order (independent of X, so no initial homophily); each follows exactly `ba_out` (15) earlier agents drawn without replacement with probability ∝ in-degree + `ba_attract`. The first 16 agents follow each other. Everyone has out-degree 15 (rewire conserves it); only followers are heavy-tailed.
- `ba_attract` sets initial unfairness (n = 1000, out 15): 0 → max followers 957, top-1% of agents hold 63% of follows (extreme); 5 → 394 / 24%; **15 (default) → 222 / 14%, median 6, 10% have zero followers**; 50 → 141 / 8.5%; uniform attachment → 91 / 5.5%. Default 15 chosen as "not too strong".
- Pilots `dba_hop1`, `dba_hop4` (seed 0, 20000 steps, same settings as the homophily pilots: q_tau 0.1, q_init 7, l_ref 1000, i-edges .63/.71).
- ModelTests: ALL PASS (new directed-BA test).

### dba pilots (feed 10, seed 0, 20000 steps) — result
| run | assort 0 / 5k / end | followers: max / top-1% share / zero-follower share (t0 → end) | attnGini / top-1% attn | Q post / like / reshare / rewire (end) |
|---|---|---|---|---|
| dba_hop1 | .01 / .21 / .12 | 222 / .14 / .10 → 999 / .66 / .79 | .98 / .84 | 7.05 / 7.04 / 7.06 / 7.04 |
| dba_hop4 | .01 / .08 / .04 | 222 / .14 / .10 → 998 / .65 / .98 | .99 / .79 | 7.00 / 6.99 / 7.00 / 6.99 |
- The moderate scale-free start (top 1% hold 14% of follows) collapses to a near-star: one agent ends with ~999 of 1000 followers, 79% (hop 1) to 98% (hop 4) have no followers. Same rich-get-richer collapse as with the other starts, only faster; so the collapse is produced by the dynamics, not by the start.
- Opinion assortativity rises a little under hop 1 (.01 → .21 at 5k), then decays to .12; no stable clusters.
- Q gaps ≤ 0.02: no action learning.

## 2026-10-12 — Rewire gate: only swap if the candidate is more similar (user decision)
- [Agent.rewire](../../src/agent/Agent.java): the candidate is still drawn from the not-yet-followed originators of feed posts, weighted exp(−β_h|x_i−x_m|). New: it replaces the front followee **only if |x_i−x_cand| < |x_i−x_front|** (strict). Otherwise nothing changes: follow list and queue order stay as they are.
- Choice made: one candidate is drawn (kept stochastic), then compared with the front; not "best candidate in the pool". Say if you want the best-of-pool version.
- Effect on metrics: `rewire` column = executed rewires only; the chosen-action share still counts all selections, so (chosen − executed) is the refusal rate. Rewire is now a cheap action with a built-in similarity filter, so it should no longer pump follows toward popular agents that are far in X.
- Supersedes the unconditional replacement. ModelTests: ALL PASS (new refusal test).
- Pilots `gate_hop1`, `gate_hop4` (dba start, feed 10, otherwise identical to dba_hop1/4) running.

### Rewire gate pilots (dba start, feed 10, seed 0, 20000 steps) — result
| run | assort 5k / 10k / end | executed rewires (total; per step, last 2000) | followers at end: max / top-1% share / zero-follower share | attnGini / top-1% attn | Q post / like / reshare / rewire (end) |
|---|---|---|---|---|---|
| dba_hop1 (no gate) | .21 / .16 / .12 | 29.8k; 1.56 | 999 / .66 / .79 | .98 / .84 | 7.05 / 7.04 / 7.06 / 7.04 |
| gate_hop1 | .61 / .70 / **.78** | 15.3k; 0.27 | 932 / .41 / .44 | .96 / .70 | 7.29 / 7.25 / 7.27 / 7.25 |
| dba_hop4 (no gate) | .08 / .05 / .04 | 102k; 3.44 | 998 / .65 / .98 | .99 / .79 | 7.00 / 6.99 / 7.00 / 6.99 |
| gate_hop4 | .78 / .83 / **.87** | 20.7k; 0.23 | 697 / .34 / .50 | .96 / .55 | 7.20 / 7.17 / 7.19 / 7.17 |
- The gate turns the dynamics from collapse into sorting: assortativity RISES from ≈0 (random-X scale-free start) to .78–.87 and keeps growing; follower concentration and zero-follower share fall a lot. Clusters form from a start with no homophily. Hop 4 now sorts better than hop 1.
- Rewires executed drop to about 0.25 per step (from 1.5–3.4); selections of rewire stay ≈ 22–28%, so most are refused once the follow list is similar.
- A star still exists (max followers 700–930) but far fewer agents are left isolated.
- Q gaps are still ≤ 0.04 on values of ≈ 7.2: action learning remains absent. Post leads by ~0.03.
