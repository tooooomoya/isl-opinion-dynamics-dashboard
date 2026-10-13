# 2026-10-12 — Attention-economy model: agreed spec + code-change plan (DRAFT for approval)

Branch: `attention-economy` (cut from `master` @ 4671480; uncommitted dashboard/docs edits from master came along).
Status: **no code has been changed yet.** Revision 2 (same day) folds in the user's answers to D1/D5/D6/D8/D9 — see §2. **Rev 9 (§12) returns to d = 1 with absolute-distance similarity; it supersedes §11's d = 2 and cosine (the uniform init, 2-hop rewire and μ = 0 stay) and restores D9's scalar-first staging.** **Rev 8 (§11) fixes d = 2, uniform init, cosine similarity, 2-hop rewire candidates and μ = 0; it supersedes §1.5/§7.3 (OPEN-7, OPEN-13), D9's d=1-first staging and D10, and the distance-based formulas in §10.** **Rev 7 (§10) replaces the arm-wise bandit with state-based Q-learning and a global reward; it supersedes §7.2, §8 (learner/OPEN-10) and §9.1 wherever they conflict.** **Rev 6 (§9) adopts the user's bandit update rule and closes OPEN-11; where §9 conflicts with §7/§8, §9 wins.** **Rev 5 (§8) records the user's answers to OPEN-5/6/8 and refines the learner; where §8 conflicts with §7, §8 wins.** **Rev 4 (§7) restructures the agent loop around Q-learned action choice and supersedes §1.2, §1.4, §1.5 and §6 wherever they conflict.** Remaining open items are marked **OPEN**; unanswered rows keep my recommendation as the working default.

**Research question this model serves (user, 2026-10-12):** how *screen modelling* (what the feed/screen shows each user, i.e. the feed algorithm) and *network structure* affect the dynamics. Consequence: the feed machinery and network are the manipulated factors; the new attention/rewire mechanics are the substrate on which they act, and should stay as simple as possible.

## 0. What this supersedes

`2026-10-01-attention-economy-pivot.md` proposed "opinion → attention *vector*", endogenous intensity,
and actions {create, consume, idle}. The user's 2026-10-12 decisions replace those parts:

| 2026-10-01 pivot (superseded)                 | 2026-10-12 decision                                                        |
|-----------------------------------------------|----------------------------------------------------------------------------|
| X = attention vector                          | **X = values/perspective vector** (opinion-like; basis of homophily)        |
| attention is a property of the agent's state  | **attention is a scarce per-step resource**; posts compete for it           |
| intensity endogenous (habit/reward)           | **stubbornness stays an exogenous given parameter** (hard problem, deferred)|
| actions {create, consume, idle}               | **actions {like, reshare, post}**; like = pure consumption, reshare includes quote |
| follow/unfollow                               | **rewire** (single operation), driven by adaptive homophily on X            |

Not yet touched by any decision: the feed algorithms (Trend / For-You) — they remain the research
manipulation of interest and are carried over unchanged in Stage 1 (see §3.4).

## 1. Model specification (as I understand it — please correct)

**Plain-language definitions used below**
- *X* — agent *i*'s value/perspective vector x_i ∈ [−1,1]^d. Today's scalar `opinion` is the d=1 case.
- *Candidate set* — the posts the feed machinery (chrono-from-follows + For-You) delivers to agent *i* this step. Today this is `agent.feed`, and today the agent reads and acts on **all** of it.
- *Attention budget A* — the max number of candidate posts agent *i* can "do something with" (be influenced by, or reshare) in one step. A < |candidate set|, otherwise there is no competition.
- *Attended post* — a candidate post that won one of the A slots. Attending a post is itself the **like** action (pure consumption: the post influences x_i and counts as attention received by its author; nothing is re-broadcast).
- *Dead post* — a post that has been forgotten (see §1.3): it is removed from every pool and can never be seen or reshared again.

### 1.1 State
- Agent: x_i (current), x_i⁰ (intrinsic, fixed), stubbornness s_i (given), postProb_i, accessProb, out-neighbour set.
- Post: author, conveyed X, creation step, root/parent lineage, reshare count, **last-attended step**, alive flag.

### 1.2 Per-step agent loop (replaces the current repost→follow→unfollow→post→update order)
1. Access gate (unchanged: `accessProb`).
2. Admin builds candidate set (unchanged machinery).
3. **Attention allocation:** agent keeps A of the candidates by a competition rule (§1.4). Each attended post gets `lastAttendedStep = t`.
4. **Like (consume):** every attended post is liked/consumed — it feeds step 7 and the author's attention tally. (Rev 3: superseded by the Q-learning proposal in §6 — like becomes a chosen action; until then automatic.)
4b. **Reshare:** for each attended post, additionally reshare with probability gated by homophily (in-bc: `repostProb`, out-of-bc: `outOfBCRepostProb`, as today). A reshare carries the original author's credit (`rel_attrib=original`, as today) and is re-broadcast to followers. "Quote" = reshare with distortion toward the resharer's own X (today's `relay()` with strength s); plain share = no distortion.
5. **Post:** with probability `postProb`, create a new original post (creative; new X = current x_i), broadcast to followers.
6. **Rewire:** with probability `rewireProb`, drop one out-neighbour and add one new out-neighbour (§1.5).
7. **X update:** x_i ← s_i·x_i⁰ + (1−s_i)·mean(X of *attended* posts) — the current rule restricted to attended posts. With bounded confidence off (D6) the mean is over **all** attended posts; homophily then enters only through which posts win attention (§1.4) and through rewire.
8. End of step: kill posts per §1.3.

### 1.3 Death of posts ("forgotten posts are dead")
A post is dead once it has gone **L consecutive steps without occupying any agent's attention slot**
(`now − lastAttendedStep > L`). Dead posts are purged from every agent's `PostCash`, the For-You
candidate window, and the velocity snapshots. This replaces two ad-hoc lifetime mechanisms that exist
today: the fixed FIFO of size `feedCapacity` in `PostCash`, and the fixed `VELOCITY_WINDOW=100` age cutoff
in `AdminOptim.pruneRecentPosts`. (Reshares keep the *root* alive: attention to a reshare refreshes the root's `lastAttendedStep`.)

### 1.4 Competition for attention (the attention-economy mechanism)
Within one agent's candidate set, the A slots are filled by sampling without replacement with weights

  w(post) ∝ exp( −β_h·‖x_i − x_post‖ ) · (1 + reshares(post))^{β_s}

- β_h = homophily pull, β_s = popularity/social-proof pull. β_h=β_s=0 ⇒ uniform sampling (no-competition null).
- Competition is *global* only through the candidate sets (a post that many agents' candidate sets contain, and which scores well, wins slots in many places and survives; others die). The concentration of attention on a few posts/authors is then an outcome, not an input.

### 1.5 Rewire (replaces follow + unfollow + block + eviction)
- Out-degree of each agent is **conserved** at its initial value (rewire swaps, never adds) — this removes `maxFollowCapacity`, eviction, and the unfollow-induced degree drift.
- Drop: one current out-neighbour *j*, sampled with P ∝ exp(β_r·‖x_i − x_j‖) (reuses today's `softmaxEvict`).
- Add: the author of one *attended, in-bc* post not already followed (reuses today's `follow()` candidate rule); if none exists, no rewire happens that step.
- "Adaptive homophily" = ties re-form toward similar X, X itself moving via §1.2 step 7.

## 2. Open decisions (each needs your answer; my recommendation first)

| # | Question | Recommendation |
|---|----------|----------------|
| D1 | Does posting consume an attention slot? | **DEFERRED by user.** Working default: separate Bernoulli (no code impact now). |
| D2 | Dead-post rule: "L steps unattended by *anyone*" (§1.3), or per-post decaying salience reaching a threshold? | L-steps rule; one parameter, easy to interpret. |
| D3 | Attention-competition weights (§1.4): homophily × popularity, both switchable? | Yes, as written; β_h, β_s are the sweepable knobs. |
| D4 | Rewire "add" source: authors of attended in-bc posts (§1.5) vs uniform random agent. | Attended in-bc authors (keeps it endogenous and local). |
| D5 | Block: remove with follow/unfollow? | **DECIDED: remove.** |
| D6 | Bounded confidence (bc), comfort-driven `postProb`, `vocalComfortRadius`? | **DECIDED (rev 3): bounded confidence OFF in all four roles (a–d, §2.1); comfort-driven `postProb` frozen at `initialPostProb` in Stage A.** |
| D7 | Keep **hubs/pinned-opinion/silent interventions** (`InterventionSetup`)? | Keep code, but mark out of scope; do not extend to vectors. |
| D8 | Keep the existing feed (chrono + velocity For-You, `feedCapacity` truncation) as candidate generator? | **DECIDED: keep.** Feed/screen design and network are the studied factors. |
| D9 | **Staging:** (A) attention budget + dead posts + rewire on scalar X (d=1), then (B) generalise X to d-dim. | **DECIDED: yes.** d=1 lets me regression-check against the current model (A ≥ |candidates|, β=0, L=∞ must reproduce today's reshare/post/update behaviour minus follow/unfollow). Doing vector + mechanism together makes bugs unattributable. |
| D10 | Vector distance metric & bc form for d>1: Euclidean/√d-normalised ball, or per-dimension? | Euclidean normalised by √d so bc keeps its [0,2]-scale meaning. Decide at Stage B. |
| D11 | Quote vs plain reshare: single reshare type with distortion s (today), or add `quoteProb` splitting s>0 / s=0? | Single type, s unchanged, in Stage 1. |

### 2.1 Resolved (rev 3): what "bounded confidence off" removes — all four roles, as recommended
bc currently does four jobs; "off" can mean any of these:
- (a) **Assimilation gate** — X averages only over posts within bc. Off ⇒ average over all attended posts.
- (b) **Reshare gate** — in-bc posts reshared at `repostProb`, out-of-bc at `outOfBCRepostProb`. Off ⇒ a single reshare probability (or reshare gated by the attention weight instead).
- (c) **Dynamic bc relaxation** (`bcDecRate`/`bcRecoveryRate`, per-agent bc shrinking with discomfort). Off ⇒ bc constant.
- (d) **Rewire "add" rule** (§1.5, authors of attended in-bc posts). Off ⇒ needs a different rule, e.g. attended posts weighted by exp(−β_h·distance).

My recommendation: turn off (a), (b), (c) entirely (no bc anywhere) and let homophily live in exactly two places — the attention weight β_h (§1.4) and the rewire drop weight β_r. For (d), choose the added neighbour from attended posts' authors with weight exp(−β_h·distance). Comfort-driven `postProb` is coupled to bc-era quantities (`vocalComfortRadius`); recommendation: freeze `postProb` at the constant `initialPostProb` for now (removing a second endogenous loop), unless you want it kept.

## 3. Code-change plan (by file; Stage A unless marked B)

### 3.1 Deleted / replaced
- `Agent.follow()`, `softmaxEvict` (moved), `unfollow()`, `block()`, `blockedUserList`, `lastBlocks` → replaced by `Agent.rewire()`.
- `OpinionDynamics.evolve()` follow/unfollow/block branch (lines ~308–326, 358–364) and counters `followActionNum/unfollowActionNum`; the metrics column `rewire` (currently hard-coded 0, line 459) becomes the real count; `follow/unfollow/blockCount/followCount/unfollowCount/evictionCount` columns removed.
- `AdminOptim.updateAdjacencyMatrix`, `addFollowEdge/removeFollowEdge` kept (rewire uses them); `maxFollowCapacity`, `pU`, `followProb`, `evictBeta` (renamed `rewireBeta`) config keys retired.
- `OpinionDynamics.pruneOverCapacity` (`init_prune`) — obsolete once out-degree is conserved.

### 3.2 Added
- `Agent`: `attendedFeed` (subset of `feed`), `allocateAttention(...)`, `rewire(...)`; `updateMyself` and `repost` iterate `attendedFeed` instead of `feed`. Pending OPEN-2: removal of the bc gate/relaxation code in `updateMyself` and `repost`, and (recommended) the comfort→`postProb` block.
- `Post`: `lastAttendedStep`, `alive`; `markAttended(step)`, `kill()`.
- `AdminOptim`: `purgeDead(step)` (clears dead posts from `recentPosts`, `velSnapshot`); `PostCash` gains `removeIf(!alive)`; the `VELOCITY_WINDOW` age cutoff and `PostCash` FIFO eviction are removed (replaced by §1.3) — *behaviour change, affects For-You candidate pool size*.
- `ExperimentConfig`/`SimParams`/`tag()` (the project's single-source-of-truth for knobs): `attention_budget` (A), `attn_beta_h`, `attn_beta_s`, `dead_after` (L), `rewire_prob`, `rewire_beta`.
- `StepStats`/`buildMetricsRow` new attention-economy outcomes (all *defined here* so they are not coined later):
  - `attnGini_author` — Gini of total attention slots received per author, over the last window.
  - `attnTop1pctShare` — share of all attended slots going to the top 1% of authors.
  - `postLifespanDist` — per-post (death step − creation step); mean and p90 logged per step for posts that died that step.
  - `aliveRatio` — alive posts / total ever created.
  - `supplyDemandRatio` — new candidate-set posts per step ÷ total attention slots (Σ_i A_i over active agents). Competition exists only if this is > 1.
  - `rewireCount`, and `followGraphXAssortativity` (existing `computeOpinionAssortativity` reused).

### 3.3 Stage B (vector X)
- `Agent.opinion`/`intrinsicOpinion` `double` → `double[d]`; `Post.postOpinion` → `double[d]`; distance helper `Dist.x(a,b)`; init sampler (empirical 7-bin survey sampler is 1-D only → d>1 uses an independent truncated Gaussian per dimension, or a correlated draw — decide at Stage B).
- `Analysis` (854 lines), `Writer`, `GraphVisualize`, `GephiReader`, dashboard: all assume scalar opinion & sign-based camps. For d>1 the camp/bin metrics are computed on coordinate 0 only, flagged in output, until a vector-native camp definition exists.
- `Const.EMPIRICAL_*` calibration targets are 1-D-only; they remain valid for the d=1 stage only.

### 3.4 Deliberately NOT changed in Stage A
Feed machinery (`AdminFeedback`, For-You velocity ranking, reach/decay — the studied 'screen' factor), network generators (the studied 'network' factor), `accessProb`, hub interventions, output folder layout, `randomGenerator` named streams.
New randomness (attention sampling, rewire) uses `randomGenerator.dynamics()`, so existing-stream draw order changes ⇒ **bit-for-bit reproduction of old runs is not possible after this branch, even in the regression-anchor setting**; the regression check is therefore statistical (distribution of metrics across ≥10 seeds), not exact.

## 4. Validation plan before any science
1. Unit/assertion: out-degree conserved at every step; dead posts absent from all pools; |attended| ≤ A; `AssertionCheck` updated.
2. Null limits: β_h=β_s=0 ⇒ attention is uniform; A ≥ |candidates| & L=∞ ⇒ today's behaviour minus follow/unfollow.
3. Competition exists: `supplyDemandRatio` > 1 in the default configuration — otherwise A is not binding and nothing is being tested.
4. Tautology guard (carried from the pivot report): check that attention concentration is not guaranteed by construction — compare against the β_s=0 run where popularity feedback is off.

## 5. Risks recorded
- **Rich-get-richer is built in via β_s and via For-You velocity.** Concentration in attention could be an artefact of that feedback. Need the β_s=0 / alpha=0 baselines in every comparison.
- **Two truncations stacked** (feed capacity then attention budget) make "who is competing with whom" harder to reason about; D8 keeps it for continuity, but collapsing them into one is cleaner if results are hard to interpret.
- **Validation targets still undefined** for the attention side (participation inequality, attention-to-creator heavy tail, post half-life — candidates from the pivot report). Not required to start Stage A.
- X dynamics are a placeholder (same as opinion); any "lock-in" finding under this rule is a statement about FJ-type updating, not about habit formation.

## 6. Proposal (user, 2026-10-12): Q-learning agents, reward = likes received — critique and open design

User proposal: agents choose among {like, reshare, post} by Q-learning, all three starting at equal probability, reward = likes received ("best for now"). Screen-vs-attention modelling choice to follow (user returns later).

**Assessment: workable as a first learning layer, but four things must be fixed or the result will be built in by construction.**
1. **Like has no reward under "likes received".** A like earns nothing for the liker, so Q(like) can never rise; every agent drifts away from consuming toward posting/resharing regardless of the environment. For a consume-vs-create question this is the tautology risk flagged on 2026-10-01 in a new form. Needed: an intrinsic consumption reward (e.g. similarity of the liked post to x_i, or a constant) in addition to likes received. **OPEN-3.**
2. **Post/reshare must cost something.** If posting is free and rewarded by likes ≥ 0, Q(post) ≥ Q(like) always. This forces D1 (deferred): without a cost or shared budget between consuming and creating, there is no trade-off to learn. Minimum: a per-action cost c_post, c_reshare. **OPEN-4** (it reopens D1).
3. **Delayed, non-stationary reward.** Likes arrive up to L steps after the post, from other agents who are themselves learning. Proposal: stateless (bandit-form) Q per agent, Q_i[a] ← Q_i[a] + α(r − Q_i[a]), applied *when each like arrives*, attributed to the action (post vs reshare) that created the liked item; γ = 0 (no state, no bootstrapping). Softmax or ε-greedy exploration with a floor so Q does not freeze.
4. **Reward depends on the studied factors, which is the point but also a confound.** Likes received scale with follower count and feed placement, so learned behaviour will differ by network position and by feed algorithm — this is the intended channel for "screen/network affects dynamics", but it means no learning-vs-no-learning result is interpretable without the fixed-probability baseline run on the same feed/network.

**Action granularity (proposed):** per attended post the agent chooses {like-only, reshare}; per step it separately chooses whether to post. Learned quantities replace `repostProb` and `postProb`; the initial uniform start means `repostProb=0.5`, post=0.5 until learning moves them — note this is far above today's calibrated rates, so the initial transient will be large.

**Staging (recommended):** A = attention budget + dead posts + rewire, fixed probabilities, bc off (as already agreed). A' = Q-learning layer on top, after A's null-limit checks pass. This keeps the competition/death mechanism testable on its own.

**Open items for the next session:** OPEN-3 intrinsic like reward; OPEN-4 action cost / D1; α, exploration rule and floor; "screen vs attention" modelling choice (user to decide); whether the reshare's likes are credited to the resharer, the original author, or split.

## 7. Rev 4 (user, 2026-10-12): Q-learned action choice, reward = identityFit + recognition − cost

### 7.1 Agent loop (supersedes §1.2/§1.4/§1.5/§6)
Per step, each agent accesses the platform with probability `accessProb` (unchanged), sees its feed (unchanged feed machinery, D8), and takes **exactly one action** chosen by its own Q-values over four actions:
- **post** — create an original post carrying the agent's current X.
- **like** — pick one feed post, weight ∝ exp(−β_h·d(x_i, x_post)); consume it. Records a like on that post, credited to the post's author.
- **reshare** — same weighted pick; creates a **new post** with the *original's X unchanged* (no distortion/quote), authored by the resharer. Likes it later receives go to the **resharer, not the original author**. Lineage (root id) is kept for dedup and for dead-post bookkeeping. "Reshare is a post whose content is borrowed."
- **rewire** — drop the first (oldest) entry of the agent's follow queue, follow one new agent (target rule: OPEN-7).
If the feed is empty, like/reshare are unavailable and the choice is restricted to {post, rewire}.

Consequences recorded:
- "Limited attention" is now literal: **one reaction per visit** (the old budget A with β_s popularity weight is dropped). Popularity bias enters only through the platform's feed (For-You velocity), not through the agent's own pick — which keeps the screen design as the studied factor.
- Reshare distortion (`relay_distortion`, `couple_relay_distortion`, `rel_attrib`, `relay_enabled`) and the bc-split reshare probabilities are deleted.
- Follow list = FIFO queue. Reacting (like or reshare) to a post authored by someone in the queue moves that author to the back. Out-degree is conserved (rewire = pop front + push one new). Reacting to a non-followee (e.g. via For-You) moves nothing.
- Dead-post rule (§1.3) retained: a post is dead after L steps without being picked by anyone.

### 7.2 Learning
Stateless Q per agent: Q_i[a] for a ∈ {post, like, reshare, rewire}, initialised equal (⇒ equal choice probabilities), updated Q_i[a] ← Q_i[a] + α(R − Q_i[a]); policy = softmax(Q/τ) (or ε-greedy) with an exploration floor. Reward:

  R_i(a,t) = identityFit + recognition − Cost,  Cost ≡ 0 for now.

Planned later use of Cost: an *effort* parameter that buys post quality, to study quality-vs-popularity under different feed designs (user's stated aim). Noted: quality is then a new post attribute and the exposure mechanism must read it; not in scope now.

### 7.3 Points where the reward as written cannot yet be coded (need your answer)
- **OPEN-5 — identityFit must depend on the action.** As stated ("summed over all posts in the feed, normalised") it is the same number whichever action is taken; a stateless Q-learner subtracts such a constant out, so it would have no effect on choice. Proposal: *like/reshare:* similarity of the post reacted to, s(x_i, x_post) = 1 − d/d_max ∈ [0,1]; *post:* mean similarity between the agent's own X and the posts in its current feed (how well it is expressing itself in the context it sees); *rewire:* the change in mean feed-similarity after the swap, observed next visit. Also the sign: "proportional to d(X_i−X_j)" taken literally rewards *dissimilar* content; I assume you mean similarity (decreasing in distance).
- **OPEN-6 — what "% of likes received" is a percentage of.** Options: (i) likes this post got ÷ number of agents who saw it (a per-exposure like rate, independent of reach); (ii) its share of all likes issued in the system that step (rewards reach, so hubs and algorithm-promoted posts win); (iii) likes ÷ author's follower count. (i) isolates content appeal; (ii) bakes reach into reward and so makes the feed-design effect on quality-vs-popularity strong but partly circular. Recommendation: (i) as the baseline reward with (ii) as a switchable variant. Also timing: likes arrive after the action; I would update Q when each like arrives, credited to the creating action (post or reshare), recognition for like and rewire actions being 0.
- **OPEN-7 — rewire target.** Recommendation: draw a post by the same d-weighted pick as like/reshare and follow its (resharer-or-original) author, excluding self and existing followees; if impossible, rewire is a no-op that still pops nothing.
- **OPEN-8 — X update rule.** Which posts move x_i: only the one post reacted to this step (like/reshare), or the whole feed (current code), or nothing on post/rewire visits? Recommendation: the single reacted-to post, x_i ← s_i·x_i⁰ + (1−s_i)·x_post, so X moves only by what the agent actually attended — consistent with "limited attention".
- **OPEN-9 — scale matching.** identityFit and recognition are both in [0,1] only if normalised; with Cost = 0 and posting free, the post-vs-like balance is decided purely by the ratio of the two scales (and α, τ). Need an explicit weight w on recognition, a sweepable knob, and a stated default.

### 7.4 Code-change delta from rev 4 (additions to §3)
- `Agent`: replace `repost/follow/unfollow/makePost` flow by `chooseAction()` + four action methods; add `double[4] q`, `likeRecentCredit` bookkeeping; delete bc state (`bc`, `bcDecRate`… ), comfort/`postProb` machinery, `blockedUserList`, `relay()` distortion.
- `AdminOptim`: follow sets become insertion-ordered (`LinkedHashSet`) so "move to back" = remove+add and "front" = first element; `rewire` uses `removeFollowEdge`/`addFollowEdge`.
- `Post`: add `likesReceived`, `exposureCount` (needed for OPEN-6 (i)), `lastAttendedStep`/`alive`; reshare constructor keeps parent's X and sets author = resharer.
- `OpinionDynamics.evolve`: single-action step; Q update at like arrival; per-step logging of action shares {post, like, reshare, rewire} and mean Q per action — these are the primary new outcomes alongside §3.2 concentration metrics.
- New config keys: `beta_h`, `q_alpha`, `q_tau` (or `q_eps`), `q_init`, `w_recog`, `recog_mode` (rate|share), `dead_after`.
- Validation additions: with `q_alpha=0` all four actions stay equiprobable (null); with `w_recog=0` post/reshare Q should fall below like/rewire iff identityFit favours them; check Q update credit goes to the resharer not the original author.

## 8. Rev 5 (user, 2026-10-12): answers to OPEN-5/6/8; learner = multi-armed bandit

- **OPEN-5 resolved:** identityFit is **similarity** (decreasing in distance), not distance. Action-dependent form as proposed in §7.3 stands unless you object: like/reshare = similarity of the post reacted to; post = mean similarity of own X to the current feed; rewire = change in feed similarity after the swap (observed at the next visit).
- **OPEN-6 resolved (replaces "percentage"):** recognition = **log(1 + Σ likes over the agent's surviving posts)**. Log compresses reach: 1→10 and 10→100 matter, 100→1000 barely does. Percentage/rate variants are dropped.
- **Death rule restated:** every post dies a fixed number of steps L after its **last like or reshare** (a post nobody ever reacts to dies L steps after creation). Reacting to a reshare-copy refreshes the copy; a reshare of a post counts as a reaction to the parent too (refreshes it). When a post dies, its likes leave the recognition sum, so recognition decays by forgetting.
- **OPEN-8 resolved:** X is updated from the **mean of all posts in the feed** (not just the one reacted to), with a **very small** influence weight μ.
- **Learner = multi-armed bandit.** Yes — the stateless Q-learner of §7.2 *is* a multi-armed bandit (γ = 0, four arms: post/like/reshare/rewire, one pull per visit), so no change of method, only of vocabulary. Two specifics: rewards are **non-stationary** (other agents learn too; posts die), so use a **constant step size α** (recency-weighted), not the 1/n sample average; and use softmax or ε-greedy with a floor rather than UCB/Thompson, whose confidence bounds assume stationary arms.

### 8.1 Two issues the new reward creates (need your decision)
- **OPEN-10 — recognition is a stock, not a consequence of the chosen arm.** "Sum of likes of surviving posts" is the same number whichever action the agent takes this visit, so as a reward for *this* pull it again carries no information about which arm to pull (same flaw as the constant identityFit in OPEN-5). Fix options: (a) **per-arm stock**: R_recog(post) = log(1 + likes on my surviving *original* posts), R_recog(reshare) = log(1 + likes on my surviving *reshare* posts), 0 for like/rewire; update only the pulled arm at pull time. Arms then carry a reputation signal for that kind of output. (b) **Increment**: reward the pulled arm with the *change* in log-stock since the last visit, attributed per arm. Recommendation: (a) — closest to your wording and cheapest; caveat: it rewards past success of that arm, so it is sticky (an agent whose old posts are still alive keeps a high Q[post] even if posting now would flop).
- **OPEN-11 — meaning of μ.** Either (i) μ is the existing influence weight 1−s, i.e. x_i ← (1−μ)·x_i⁰ + μ·mean(feed X), anchored to the intrinsic opinion (then stubbornness s = 1−μ is no longer a separate parameter), or (ii) unanchored drift x_i ← x_i + μ(mean(feed X) − x_i). (i) bounds X near its start; (ii) lets X wander over long runs and eventually consensus-drift if homophily is weak. Recommendation: (i) for now, since you want X nearly fixed while action/network dynamics are studied; consequence: initial X dispersion is essentially the homophily landscape, not an outcome.

### 8.2 Code deltas from rev 5
- `Post`: `lastReactionStep` (replaces `lastAttendedStep`); `alive` = `step − lastReactionStep ≤ L`; `likesReceived` kept; reshare copies refresh the parent.
- `Agent`: per-agent survivor lists by arm (original posts / reshare posts) for the per-arm log-stock; bandit update only on the pulled arm; feed-mean X update with μ replacing stubbornness-weighted FJ term.
- Remove from plan: `exposureCount` (needed only for the dropped percentage variant), `recog_mode`, `w_recog` stays (weight on recognition vs identityFit, OPEN-9 still open).

## 9. Rev 6 (user, 2026-10-12): bandit update rule adopted; OPEN-9 and OPEN-11 closed

User-specified learner (notation as given; I rename the weights w_I, w_L in code to avoid clashing with the homophily β_h and the earlier α):

  Q_i(a_t) ← Q_i(a_t) + η (r_{t+1} − Q_i(a_t)),   r_{t+1} = α·I_i(t+1) + β·L_i(t+1)

with η the (constant) step size, I_i = identity fit (similarity), L_i = recognition (log(1 + likes on surviving posts)). Only the arm pulled at t is updated, with the reward observed afterwards ("t+1" = the agent's **next visit**, since agents access the platform with probability accessProb, so the gap is random with mean ≈ 1/accessProb).
- **OPEN-9 closed (user, same day, amended):** the weights are **equal**, α = β (= 1). They are not separate knobs; the reward is the plain sum of identity fit and recognition. Consequence: identity fit ∈ [0,1] (similarity) and recognition = log(1+likes) (unbounded above) are on different scales, so recognition can outweigh identity fit once an agent has ≳ e−1 ≈ 1.7 likes on surviving posts; equal weights fix the *coefficients*, not the effective balance. Check the realised magnitudes in the pilot; if recognition dominates, normalise it (e.g. divide by log(1+likes_max)) rather than re-introducing a weight.
- **OPEN-11 closed:** μ is the influence weight of the existing X rule, anchored to the intrinsic value: x_i ← (1−μ)·x_i⁰ + μ·mean(X of all posts in feed), μ very small; stubbornness s = 1−μ is therefore not a separate parameter.

### 9.1 Assessment: right form, but two things in the reward must be pinned down
1. **Outcome-after-action rewards are only informative as differences.** I_i(t+1) and L_i(t+1) are levels of the agent's situation at the next visit, dominated by things the action did not cause (the feed algorithm, who follows me, posts already alive). Updating the pulled arm toward a level makes every arm converge to the same agent-level average, and the arm differences that remain are noise. Recommendation: use the change since the action, r_{t+1} = α·[I_i(t+1) − I_i(t)] + β·[L_i(t+1) − L_i(t)], so only what the action moved is credited. (Equivalent to the level form with a baseline subtracted; the level form is the special case with no baseline.)
2. **Identity fit at t+1 does not distinguish like/reshare/post.** The feed seen at the next visit is shaped by the platform and by rewire, not by whether I liked or posted last time. So under the formula as written, I rewards only rewire; **like has no source of reward at all** (it creates no posts, so L is unaffected) and its value stays at or below post/reshare — the same "consumption is never worth it" tautology as OPEN-3. Recommendation: define I_i(t+1) to include the immediate fit of what the action consumed or produced — like/reshare: similarity of the picked post to x_i; post: similarity of own X to the feed it was written into; rewire: change in mean feed similarity at the next visit — i.e. the action-dependent version in §7.3.
3. Delay: likes on a new post accrue over up to L steps, but the next visit comes soon, so ΔL at t+1 under-credits post/reshare (they look worse than their eventual payoff). Expected effect: a bias against creation that depends on accessProb and L; check it in the pilot by comparing against a variant that credits likes at arrival time.

## 10. Rev 7 (user, 2026-10-12): global reward + Q-learning over a two-variable state

### 10.1 Decision
- **Reward is global, not arm-specific** (user accepts the resulting bias as realistic): r_{t+1} = w·Ĩ_i(t+1) + w·L̃_i(t+1), equal weights, **both terms on the same [0,1] scale**:
  - Ĩ_i = identity fit of the feed = mean similarity between x_i and the posts in its current feed, similarity = 1 − d/d_max (d_max = 2 for X ∈ [−1,1]).
  - L̃_i = recognition = min(1, log(1 + Σ likes on i's surviving posts) / log(1 + L_ref)), L_ref a cap (likes at which recognition saturates; e.g. 100–1000, consistent with the user's "100 vs 1000 are similar").
  This closes the scale question left open in §9; it supersedes the §9.1 proposals (change-based reward, action-dependent identity fit) and the per-arm recognition stock of §8.1 (OPEN-10 withdrawn). Liking needs **no reward source of its own**.
- **Learner: Q-learning with state** s = (identity-fit level, recognition level) — the agent's own two reward ingredients, discretised (proposal: 3 × 3 bins, fixed thresholds on the [0,1] scales, e.g. low < 1/3 ≤ mid < 2/3 ≤ high ⇒ 9 states × 4 actions = 36 Q-values per agent). Update:
  Q_i(s_t,a_t) ← Q_i(s_t,a_t) + η [ r_{t+1} + γ·max_{a'} Q_i(s_{t+1},a') − Q_i(s_t,a_t) ],  s_{t+1} observed at the agent's next visit.
  Q initialised equal; policy softmax(Q/τ) or ε-greedy with floor.
- **Rewire uses d(x_i, x_j).** When identity fit is low the learner can discover that rewire raises the next state; rewire's *target* is chosen by similarity: weight ∝ exp(−β_h·d(x_i,x_j)) — same weighting as the like/reshare pick.

### 10.2 Why this is better than the arm-wise bandit
Because the reward is a function of the *next state*, an action is credited only through how it moves (identity fit, recognition): rewire can raise identity fit, post/reshare can raise recognition. This fixes the "every arm converges to the agent's average level" problem (§9.1.1) in the standard way — by letting the value depend on state and on where the action leads — and it makes "low identity ⇒ rebuild network" a *learned conditional policy* rather than a hand-written rule.

### 10.3 Consequences and remaining open points
- **Like is a near no-op for the state.** It doesn't change the feed (identity fit) or the agent's own posts (recognition), and X moves only through the tiny μ. Its learned value will therefore sit near the "do nothing" value and its frequency will be set largely by exploration/tie-breaking, *except* through one real effect already in the design: reacting to a followee's post moves that followee to the back of the FIFO follow queue, protecting that tie from the next rewire. Interpret like-share results with this in mind; do not read it as a preference for consumption.
- **OPEN-12 — which entry is dropped on rewire?** Either (a) the FIFO front, as decided earlier (least recently reacted-to followee), then a new follow chosen by similarity, or (b) the most dissimilar followee. Working default: (a) drop, with the similarity-weighted choice applied to the *new* follow only.
- **OPEN-13 — candidate pool for the new follow:** authors of posts in the current feed (local, uses only what the agent has seen) or any agent (global). Working default: feed authors, excluding self and current followees; if none, rewire is a no-op.
- **OPEN-14 — discretisation and γ:** bins/thresholds and γ (0 would reduce to a contextual bandit; > 0 gives genuine sequential credit). Working default: 3 × 3 bins, γ = 0.9 sweepable, η and τ sweepable.
- **Empty states:** identity fit is undefined for an empty feed (set Ĩ = 0, or skip the update); recognition is 0 for an agent with no surviving posts — most agents at start, so the initial state mass sits in (low-I?, low-L); check that the policy there is not dominated by exploration noise.
- **Pilot checks:** (i) η = 0 ⇒ action shares stay equal; (ii) distribution of realised Ĩ and L̃ (are both spanning [0,1], or is one saturated?); (iii) action-share trajectories by state, especially P(rewire | low Ĩ).

### 10.4 Code delta from rev 7 (additions to §7.4/§8.2)
- `Agent`: `double[9][4] q`, `stateOf(Ĩ, L̃)`, last (state, action) memory, update at next visit; remove per-arm survivor lists; keep one list of surviving own posts for L̃.
- `Post`: `likesReceived`, `lastReactionStep`, `alive`; author-credited likes (resharer for reshares).
- New config keys: `q_eta`, `q_gamma`, `q_tau`/`q_eps`, `l_ref`, `state_bins`, `beta_h`, `dead_after`, `mu`. Removed: any `w_recog`/`recog_mode` knob.

## 11. Rev 8 (user, 2026-10-12): d = 2, uniform init, cosine similarity, 2-hop rewire, μ = 0

### 11.1 Decisions
- **X ∈ [−1,1]², each axis i.i.d. U[−1,1] at t = 0.** Replaces the empirical 7-bin survey sampler. **This overrides D9's "scalar X first"**: the first build is already 2-D, so there is no d = 1 regression anchor against the inherited model (and the 1-D calibration targets `Const.EMPIRICAL_*` no longer apply). Validation therefore rests on the null-limit tests in §4 / §10.3 only.
- **Similarity = cosine.** cos(i,j) = x_i·x_j / (‖x_i‖‖x_j‖) ∈ [−1,1]. Resolves D10.
  - Identity fit uses the rescaled value sim = (1 + cos)/2 ∈ [0,1], so Ĩ and L̃ stay on the same scale (§10.1 requirement). Random pairs average cos = 0, i.e. Ĩ ≈ 0.5.
  - Feed-pick and rewire weights: P(j) ∝ exp(β_h·cos(x_i, x_j)) (the (1+cos)/2 shift cancels in the normalisation).
- **Rewire candidates = 2-hop set.** After dropping the front of the queue, C_i = (∪_{f∈Φ_i} Φ_f) ∖ ({i} ∪ Φ_i); new follow m ~ exp(β_h·cos) over C_i. Replaces OPEN-7/OPEN-13 (authors in the feed). Rewire no longer depends on the feed's contents. Empty C_i ⇒ no-op.
- **μ = 0 as baseline.** x_i = x_i⁰ forever; the drift rule is kept as a parameter (default 0) but inactive. All dynamics come from actions, the follow graph, post death and Q-learning.

### 11.2 Consequences to be aware of
1. **Cosine ignores vector length.** (0.1, 0.1) and (0.9, 0.9) are identical. "Values" become pure direction (stance); intensity/extremity is not modelled — consistent with the deferred-intensity decision, but it means two agents near the origin with noisy directions look as strongly (dis)similar as two extremists. Zero vector: define cos = 0 (measure-zero under U-init, but guard in code).
2. **Uniform axes do not give uniform directions.** On the square, the density of directions along the diagonals is about 2× that along the axes. If you want uniform direction, sample the angle instead (and decide separately about length); if you want uniform axes, keep it and expect a diagonal-heavy direction distribution.
3. **2-hop rewire = triadic closure with implicit popularity bias.** A person followed by many of my followees appears in my candidate set with multiplicity-in-neighbours, so high-in-degree agents are reached more often (preferential-attachment-like). Rewire stays local: it can never create a bridge to a distant community, so the follow graph can fragment into similarity-clustered components. The check on the multiplicity: sample candidates either as a *set* (each agent once, as written) or *with multiplicity* (weighted by the number of followees who follow it); the written spec uses the set, which damps the popularity bias. Say if you prefer multiplicity.
4. **Dropped followee excluded from candidates** in the same rewire (otherwise it can be re-added through a shared followee immediately).
5. **State bins vs cosine.** With random pairs, mean cosine ≈ 0 ⇒ Ĩ ≈ 0.5 for a typical feed and the "low identity" bin (Ĩ < 1/3, i.e. average cos < −1/3 over a whole feed) is almost never reached from the initial state, so the learned "low fit ⇒ rewire" policy may never get trained. Recommendation: set the identity-fit bin edges from the empirical distribution of Ĩ in a pilot run (terciles), not at fixed 1/3, 2/3. (Revises OPEN-14.)
6. **μ = 0 makes Ĩ depend only on feed composition**, not on agents' own change; with X static, differences between runs come from the feed algorithm and network — the studied factors — which is the intended attribution.

### 11.3 Code deltas from rev 8
- `Agent`: `opinion`/`intrinsicOpinion` `double` → `double[2]` (with `mu = 0`, `opinion` is never updated); init draws two i.i.d. U[−1,1]; `cosSim(a,b)` helper with zero-norm guard; remove `sampleEmpiricalOpinion`, truncated-Gaussian and clip init paths, `opinionClass`/bin machinery (sign-based camps are undefined for 2-D vectors).
- `Post`: `postOpinion` → `double[2]`; reshare copies the array.
- `AdminOptim`: `twoHopCandidates(i, dropped)`; follow sets insertion-ordered (`LinkedHashSet`).
- `Analysis`, `Writer`, `GraphVisualize`, `GephiReader`, dashboard: opinion-bin, sign-camp, Shannon/kurtosis metrics are scalar-only. Proposed interim: report mean pairwise cosine within follow edges (follow-graph direction assortativity) and an angular histogram; disable the scalar metrics for d = 2.
- Config: `d=2` fixed, `init_dist=uniform_axes`, `mu=0`; remove `init_opinion_dist=empirical|gaussian` options for this branch.

## 12. Rev 9 (user, 2026-10-12): back to d = 1, absolute-distance similarity

### 12.1 Decisions
- **d = 1.** X ∈ [−1,1], i.i.d. U[−1,1] at t = 0 (the existing `init_opinion_dist=uniform` path in `Agent`; I assume the uniform initial distribution from rev 8 stays). Vector X (Stage B) is deferred again, as in D9.
- **Similarity = 1 − |x_i − x_j| / 2 ∈ [0,1]** (absolute distance, rescaled so it shares a scale with L̃). Feed-pick and rewire weights: P(j) ∝ exp(−β_h·|x_i − x_j|).
- **Unchanged from rev 8 (assumed):** rewire candidates = 2-hop set C_i (dropped agent excluded, each candidate counted once); μ = 0 baseline.

### 12.2 Consequences
1. **The scalar analysis stack works again** (opinion bins, sign camps, kurtosis, assortativity, Gephi, dashboard) — the rev 8 code deltas for 2-D metrics are cancelled. The empirical 7-bin calibration targets still do not apply (uniform init).
2. **Regression anchor is partly back**, but only for infrastructure: the inherited model had bounded confidence, follow/unfollow and block, which are gone, so there is no like-for-like old-model comparison. Null-limit tests (§4, §10.3) remain the validation.
3. **Identity fit now depends on position in value space.** For U[−1,1] values, the expected similarity to a random agent is 0.75 for an agent at x = 0 and 0.50 for an agent at x = ±1 (mean over the whole population: 2/3). Central agents therefore get higher identity fit from a randomly mixed feed than extremists do, before any learning. This is a structural advantage for moderates in the reward and will shape which actions agents at different positions learn; keep it in mind when reading position-dependent behaviour (it is the opposite of the "vocal extremist" intuition and not an effect of the feed).
4. **Typical identity fit under random mixing is about 2/3**, so fixed thirds would put the typical agent on the mid/high boundary. State-bin edges should still come from a pilot distribution of Ĩ (as in §11.2.5), not fixed thirds.

### 12.3 Code deltas from rev 9 (replace §11.3)
- `Agent`: keep scalar `opinion`; `mu` parameter (default 0) gates the update; add `sim(a,b) = 1 − |a−b|/2`; init via the existing uniform path.
- `AdminOptim`: `twoHopCandidates(i, dropped)`, insertion-ordered follow sets (unchanged from rev 8).
- No change to `Post`, `Analysis`, `Writer`, Gephi or dashboard type signatures.
