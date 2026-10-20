# 2026-10-14 Like influence with static network (scripts/like_static.py, 15 runs)
Rewire OFF, w_fit=w_rec=1 (S1), For You 100 % (hop 1), HK, L=200; ref (ρ_L .05, ρ_R .10, β_F 3) vs ρ_L=ρ_R ∈ {0.3,0.5} × β_F ∈ {10,25}; 3 seeds.
Result: like−post reward −0.002…−0.004 in all cells (ref −0.004); like share 0.32; identity fit 0.66–0.67 (= random-feed expectation 1−E|Δx|=0.667), assortativity ≈ −0.01, spread ≈ 0.01, captured gain ≤0.02.
Conclusion: with a static, non-homophilous network, even strong X̂ updates/sharp For You do not raise identity fit: the candidate pool (followees + 1 hop) contains too few close agents for the ranking to select from. Liking does not pay.
