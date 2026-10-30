# Initial opinion distributions: design review (2026-10-28)

This review corrects the interpretation of the completed empirical-initialization calibration and the subsequent recommendation that uniform initialization is universally the correct ABM calibration design. No new simulations or changes to completed scores are made here.

## Verified implementation and data

- The completed run uses `init_dist=empirical` and `mu=0`. Opinion composition remains fixed; activity, learning, and network structure can change. It cannot demonstrate the emergence of an opinion distribution.
- The later v2 objective pools mirror bins by their populations. Left/right symmetric rules do not make an asymmetric population or its interaction opportunities symmetric. The v2 score is a pooled descriptive fit conditional on the empirical composition, not evidence of symmetry in the full initialized system.
- Per-person activity is the target. Empirical population counts therefore do not algebraically impose the activity profile. Composition can nevertheless change exposure, recognition, and learning through interactions. Attribution requires matched interventions on composition and mechanisms.
- Buntain & Snegovaya distinguish seven-category survey self-placement from daily news-sharing-imputed ideology. The bins used here are survey labels, not labels inferred solely from posting. Survey self-placement is neither an innate continuous opinion nor proof that seven equal-width latent intervals are appropriate.
- The released 762-account panel is selected for observed news sharing and matching. Its bin frequencies do not identify the ideology distribution among all platform users or silent users. Its conditional activity profile is also conditional on this selection. Uniform initialization alone does not correct this observation problem.

## Methodological interpretation

There is no universal CSS rule requiring uniform initial opinions. Empirical calibration can constrain initial conditions from relevant data; generative explanation tests whether specified local processes can produce a macro-pattern under stated starting conditions. Neither approach removes assumptions about initialization. Windrum et al. explicitly discuss empirical initialization and initial-condition dependence; Epstein's generative account requires producing the pattern, not uniformly distributed agents.

Folding is an estimand choice, not a mathematical operation permissible only for symmetric systems. It deliberately discards sign information. With unequal composition, person-weighted pooling includes composition-specific weights. For an extremity hypothesis, define the weights explicitly: either person-weighted rates for a specified population or an equal-side standardized rate `(a_left + a_right)/2`. Show the seven-bin residuals and asymmetry separately. The latter standardization is a proposed new statistic, not the statistic used in the completed v2 run.

## Recommended prospective design for this project

1. Treat the primary claim as emergence of *activity conditional on opinion*, with fixed opinions. Use uniform opinions as a controlled reference condition consistent with the user's intended question. Check a symmetric center-heavy distribution as a prespecified robustness condition; neither distribution is asserted to represent the actual platform population. Do not change individual action propensities by opinion at initialization to encode the target profile.
2. Keep activity by opinion, detected repost-network segregation, and held-out degree/activity distributions distinct. Specify the seven-bin and extremity comparisons and their weights before fitting. Check left/right differences even if only extremity enters the primary objective.
3. Change initialization at fixed candidate parameters and paired seeds to diagnose composition sensitivity. A surviving valley supports robustness to that intervention; it does not alone establish the proposed causal mechanism. A disappearing valley does not prove uniform-initialized calibration cannot work.
4. Run a separate uniform-initialized calibration if that is the primary claim. Keep all old runs as empirical-composition conditional results. Do not silently mix their likelihoods/objectives or treat old parameter rankings as rankings under the new initialization.
5. Before comparing long-run outcomes, check time-window drift and horizon dependence. A fixed step count is not evidence of equilibrium. Include mechanism controls with similar aggregate activity, so the explanation is more specific than the mere production of a U-shape.
6. If estimating population composition, use a low-dimensional family with external information or an explicit prior and report sensitivity/identifiability. This selected panel's activity summaries alone do not identify both latent population composition and behavioral parameters.

The existing random-forest/EI Bayesian optimization is a simulator optimization procedure, not a Bayesian posterior estimate of the ABM parameters. Estimating latent initial conditions probabilistically would require a declared inference/observation model, not just adding more BO dimensions.

## Sources checked

- Buntain & Snegovaya (2025), original article, cached full text `results/empirical_source_audit/buntain.xml`: https://doi.org/10.1093/pnasnexus/pgaf333 . See the existing source audit for public notebooks, selection, and unresolved tweet-type filters.
- Windrum, Fagiolo & Moneta (2007), especially sections 4–5: https://www.jasss.org/10/2/8.html .
- Epstein (1999), *Agent-based computational models and generative social science*: https://cdanfort.w3.uvm.edu/csc-reading-group/epstein-complexity-1999.pdf .
- Thiele, Kurth & Grimm (2014), calibration and sensitivity methods: https://jasss.soc.surrey.ac.uk/17/3/11.html .

These sources support the methodological distinctions; the prospective experiment choices above are this project's design recommendations, not a claimed field-wide prescription.
