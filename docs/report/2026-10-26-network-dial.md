# 2026-10-26 — Start-network dial with rewiring OFF: why do extremes post more under For You on Holme–Kim?

**Observation (rewire ON, standing config).** Under For You, starting from the Holme–Kim (HK) network the extreme agents' share of POST actions rises
above the moderates'; from random / SBM / WS starts it stays below. The three non-HK follow graphs end as two homogeneous clusters; the HK graph stays connected.

**Hypotheses.**
- H_SF (hub): HK starts with hubs that exist *by construction* (not emerged through the run); hubs whose X is extreme form filter bubbles and collect the extremes' attention.
  Hub opinions are random (X ~ U[-1,1], independent of node index), so hubs of different opinions are wired to each other from t = 0.
- H_conn (findability): the effect comes from the graph resisting sorting into two clusters, not from the in-degree tail.
- Final-state in-degree Gini cannot separate them (rewiring makes a heavy tail everywhere); the *initial* structure and the *static* graph can.

**Design (decided 2026-10-26, user approved rewire-OFF + tail / clustering dials).** `scripts/network_dial_run.py`, ids `dial_<net>_<feed>`, 10 seeds, n = 1000, 20,000 steps.
Standing config of `standard_run.py` except `rewire=false` (static follow graph, so the start network is the whole network). Out-degree fixed at m = 15 in every HK variant.

| Dial | Nets | HK exponent γ = 2 + A/m |
|---|---|---|
| tail (pt = 0.05) | hkA1, hkA4 (= old default), hkA15, hkA40, hkA150 | 2.07, 2.27, 3.0, 4.7, 12 (≈ uniform attachment, light tail) |
| clustering (A = 4) | hkpt0, hkA4 (pt .05), hkpt50, hkpt95 | γ = 2.27 for all |
| no-hub reference | random (Poisson, start_deg 15) | – |

Feeds: For You (hop 5) and Chrono (the contrast isolates the feed). Fresh rewire-ON references: hkA4 and random under For You (`_on`), because earlier ON results predate current code.
Total 200 runs. Supersedes: reading the old `fcoff_*` (rewire-OFF) results, which are from an older model version.

**Outcome metrics (plain meaning).**
- *posting ratio* of a group = mean over agents of (POST actions / all actions) in the last 5,000 steps, groups by intrinsic |X|: neutral < 1/3, moderate 1/3-2/3, extreme ≥ 2/3 (as in `plot_feed_compare.py`).
- *extreme − moderate posting gap* = posting ratio(extreme) − posting ratio(moderate); the quantity that flips sign on HK.
- *hub* = top 1 % of agents by in-degree at t = 0; *hub-side mix* = share of hubs with |X| ≥ 2/3; *hub-hub cross-side share* = fraction of follow edges between two top-5 % hubs whose X have opposite sign.
- *sorting* = sign-modularity of the (static) follow graph and the share of an agent's followees on its own side of X = 0.

**Predictions.** H_SF: the gap grows monotonically as γ decreases and vanishes at hkA150 / random. H_conn: the gap tracks sorting / connectivity, may respond to pt, and may persist at light tails.

Results: see the entries below (appended when the runs finish).

## Result (2026-10-26, 200 runs done, 0 failed; full table: `2026-10-26-network-dial-table.txt`)

Extreme − moderate posting gap under For You (mean of 10 seeds, s.e. ≈ 0.003-0.006), rewire OFF unless marked:

| Start network | in-degree Gini | gap |
|---|---|---|
| HK A=1 (γ 2.07) | 0.93 | +0.012 |
| HK A=4 (γ 2.27, old default) | 0.83 | +0.003 |
| HK A=15 | 0.69 | +0.008 |
| HK A=40 | 0.61 | +0.003 |
| HK A=150 (γ≈12, light tail) | 0.55 | +0.004 |
| HK pt 0 / .05 / .5 / .95 | 0.82-0.90 | +0.007 / +0.003 / +0.010 / +0.008 |
| random (Poisson) | 0.15 | **−0.039** |
| HK A=4, rewire ON | 0.83 | **+0.021** |
| random, rewire ON | 0.15 | **−0.063** |

Reading.
1. **Tail heaviness is not the driver.** Across a 12-fold change in γ the HK gap stays ≈ 0 to +0.01 with no monotone trend; even A=150 (Gini 0.55) sits with the other HK nets, far from random. Clustering (pt) does nothing either. H_SF in its tail form is not supported.
2. **Any HK variant differs from random**, so the cause is something *all* HK variants share and random lacks. Untested candidate: HK is grown in age order (each new node follows only older nodes), so the follow graph is nearly acyclic and followee-of-followee candidate pools funnel into the old core regardless of opinion. This is a hypothesis, not a result.
3. **The rise of extremes is mostly a rewiring effect.** Static HK gap ≈ +0.003 (≈ 0); HK with rewiring ON gives +0.021; random with rewiring ON is −0.063 (more negative than static −0.039). Rewiring amplifies whichever sign the start network sets.
4. At t = 0 hubs of opposite sign are linked at chance (hub-hub cross-side share 0.49-0.51 in *every* network, incl. random, because wiring is opinion-blind), and the share of extremes among hubs is at chance (0.34-0.42). So "opposite-opinion hubs are connected from the start" is true but not specific to HK.
5. Under Chrono the gap is negative everywhere (−0.03 to −0.08), so the sign flip is specific to the For You feed.

Caveat: For You posting ratios are low everywhere (≈ 0.05); HK-OFF gaps are within about 2 s.e. of zero, only HK-ON and random are clearly non-zero. hkA1 under For You is flagged infeasible by `feasible()` in some seeds.

Next (not yet run, needs approval): (a) configuration-model control — HK's exact in/out-degree sequence with randomly matched stubs, which keeps the hubs but removes the age ordering/acyclicity; (b) measure how many followee-of-followee candidates land in the oldest 5 % of nodes per network; (c) rewire ON with the tail dial, since the effect lives in rewiring.

## Result (a): degree-matched control (`network=hkshuf`, `scripts/dial_shuf_run.py`, 90 runs, 0 failed)

Same seed → the same HK graph, then 20 double edge swaps per edge: every agent keeps its exact in- and out-degree (verified against `dial_hkA1_chrono` seed 0),
hubs and tail are untouched, but the age ordering (new nodes follow only older ones) is destroyed. Added metric `sccFrac` = share of agents in the largest
set whose members can all reach each other by following chains of follows (strongly connected component); HK is acyclic except its 16-node seed (0.016).

Extreme − moderate posting gap, For You, 10 seeds (s.e. ≈ 0.001-0.005):

| Start network | sccFrac | rewire OFF | rewire ON |
|---|---|---|---|
| HK A=1 | 0.016 | +0.012 | – |
| HK A=1, degrees kept, rewired wiring | 0.38 | −0.001 | +0.001 |
| HK A=4 | 0.016 | +0.003 | **+0.021** |
| HK A=4, degrees kept, rewired wiring | 0.72 | −0.021 | −0.013 |
| HK A=150 | 0.016 | +0.004 | – |
| HK A=150, degrees kept, rewired wiring | 0.93 | −0.038 | −0.045 |
| random | 1.00 | −0.039 | −0.063 |

Reading. Identical degree sequences give opposite signs, so **the in-degree tail is not what produces the positive gap; the age-ordered (near-acyclic) wiring is.**
The more cyclic the wiring (sccFrac 0.02 → 0.4 → 0.7 → 0.9 → 1), the more negative the gap. This supersedes the hub hypothesis H_SF (tail form) from the first entry.
Rewiring ON does not rescue the shuffled graphs (−0.013, −0.045), so the HK-ON rise (+0.021) also needs the acyclic start.
Caveats: only 4 wiring levels, so the dose-response is across different nets, not a clean dial (sccFrac is also capped by the number of agents with zero in-edges, which is why A=1 is low);
A=1 variants have very low For You posting overall (≈ 0.03) and some seeds are flagged infeasible; the mechanism (candidate funnel into the old core) is still not measured.
Next: a partial-shuffle dial (fraction of swaps 0 / 0.1 / 0.3 / 1) at A=4, and measure the For You candidate pool's share in the oldest 5 % of nodes.

## Decomposing the gap (2026-10-26, from the tables above; no new runs)

The gap (extreme − moderate) is a difference of two moving levels, so it can flip sign by either group moving. Posting ratio by |X| group, For You, 10 seeds
(N = neutral |X|<1/3, M = moderate, E = extreme; ratios E/N and M/N use the neutral group as the anchor):

| Start network | N | M | E | E/N | M/N |
|---|---|---|---|---|---|
| HK A=4, OFF | .049 | .061 | .064 | 1.3 | 1.2 |
| HK A=150, OFF | .047 | .059 | .063 | 1.3 | 1.3 |
| HK A=4 degrees kept, wiring shuffled, OFF | .042 | .062 | .041 | 1.0 | 1.5 |
| random, OFF | .044 | .085 | .045 | 1.0 | 1.9 |
| HK A=4, ON | .049 | .071 | .092 | 1.9 | 1.4 |
| shuffled A=4, ON | .035 | .040 | .027 | 0.8 | 1.1 |
| shuffled A=150, ON | .048 | .070 | .025 | 0.5 | 1.5 |
| random, ON | .048 | .089 | .027 | 0.6 | 1.9 |

Neutral stays ≈ .045 across nets (anchor). Going from acyclic (HK) to cyclic wiring with rewire OFF: extremes fall ≈ .063 → .043 while moderates stay or rise (.06 → .06-.085),
so the negative gap in random/shuffled nets is a *moderate hump* (M/N up to 1.9) with extremes at the neutral level, not extremes being suppressed. With rewire ON extremes fall *below* neutral (E/N 0.5-0.6) in cyclic nets
and rise to 1.9× neutral in HK. The "extremes rise on HK" is therefore: E/N 1.3 (static) → 1.9 (rewired), against a moderate level that barely moves.

## Extremes' share of all posts (For You, last 5,000 steps, 10 seeds; every agent takes ≈ 500 actions in the window, so share of posts ≈ population share × posting ratio)

Population shares: N .32 / M .34 / E .34. Share of POST actions authored by N / M / E:

| Start network | N | M | E | E share ÷ E population share |
|---|---|---|---|---|
| HK A=4, OFF | .27 | .36 | .37 | 1.10 |
| HK A=1 / A=150, OFF | .24 / .26 | .35 / .35 | .41 / .38 | 1.22 / 1.13 |
| HK A=4, ON | .22 | .34 | **.44** | 1.29 |
| shuffled A=4, OFF / ON | .28 / .33 | .43 / .40 | .29 / .27 | 0.85 / 0.80 |
| shuffled A=150, OFF | .26 | .48 | .26 | 0.76 |
| random, OFF / ON | .24 / .28 | .49 / .55 | .26 / .17 | 0.78 / 0.49 |

Extremes author the largest share of posts only on the acyclic (HK) starts, and clearly so only with rewiring ON (.44 vs .34); static HK is a near tie with the moderates (.37 vs .36).
Acyclic wiring is necessary among the tested networks, not shown sufficient, and not shown to be *the* mechanism (the shuffle also changes reciprocity, degree correlations and path structure).

## Decision (2026-10-26): new standing baseline `baseline_hkshuf`

HK is acyclic (new nodes follow only older ones), which real follow graphs are not, and it drives the "extremes lead" result above. User approved a new baseline on the degree-matched
network (`network=hkshuf`, HK m 15 / A 4 degree sequence, wiring randomized; directed configuration model). `baseline_hk` is kept as a labelled "age-ordered growth" condition, not overwritten.
Run: `scripts/standard_run.py hkshuf` (standing config, rewire ON, 3 feeds × 10 seeds, ids `baseline_hkshuf_{chrono,foryou,trend}`), launched with nohup, log `logs/std_hkshuf.out`.
Known gap: follow-back reciprocity is ≈ 1.5 % here vs ≈ 22 % reported for Twitter (Kwak 2010); a follow-back dial is proposed but not approved. The robustness sweep plan (`2026-10-26-robustness-sweep-plan.md`) still names the HK baseline and needs its base network switched before it is approved.
