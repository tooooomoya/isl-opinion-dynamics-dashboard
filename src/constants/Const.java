package constants;

/**
 * True physical/structural constants only, with a hard invariant (2026-07-09 consolidation):
 * every field here has NO corresponding {@link ExperimentConfig} field / CLI key. The moment a
 * value becomes runtime-tunable, it must move to {@code ExperimentConfig} entirely (field default
 * + CLI case + {@code tag()} comparison) and be deleted from here — never both. Before this pass,
 * several fields (e.g. {@code REPOST_PROB}) were dead copies of a value that had already migrated
 * to {@code ExperimentConfig}, and others (e.g. {@code FEED_CAPACITY}) were live only as the
 * initializer for an {@code ExperimentConfig} field, spreading one parameter's definition across
 * two files for no reason. See {@code ExperimentConfig}'s {@code DEFAULTS} sentinel for how
 * defaults + their {@code tag()} comparison are now kept in one place.
 */
public class Const {
    // ---- Velocity-primary "For You" recommender (research-direction.md §3 item 6) ----
    // alpha (For-You share) and h (hop reach) are per-run knobs -> ExperimentConfig/SimParams.
    public static final int VELOCITY_WINDOW = 100;         // W: posts older than W steps leave the For-You candidate pool
    public static final int REACH_REFRESH_INTERVAL = 100;  // recompute cached h-hop reachable sets every R steps

    // network parameter
    public static final double CONNECTION_PROB_OF_RANDOM_NW = 0.01;

    // agent parameter
    // 2026-07-14: BOUNDED_CONFIDENCE/MINIMUM_BC migrated to ExperimentConfig.bcCeiling/bcFloor
    // (sweepable clamp bounds on the dynamic bc ratchet). VOCAL_COMFORT_RADIUS stays here, fixed,
    // as the R5/D4 perceptual comfort radius for the vocal-minority mechanism (Agent.java
    // withinComfort check) — it must NOT track the swept bc floor, or an intolerant extremist's
    // vocality would silence itself as soon as bc collapses, defeating the mechanism's purpose.
    public static final double VOCAL_COMFORT_RADIUS = 0.2;
    public static final double POST_COST = 0.0;
    public static final double OPINION_PREVALENCE = 0.5;
    public static final double INITIAL_OPINION_STD = 0.6;
    // NB the per-run conduit dials (P_r^out, s_relay), tolerance decline/recovery rates, the
    // follow-capacity cap, P_u, the init-opinion clip flag, and the assert cadence are all on
    // SimParams now. See docs/report/2026-07-07-*.
    public static final double INITIAL_STUBBORNNESS = 0.7;

    // Per-step platform-access probability (distinct from ExperimentConfig.pU / CLI `p_u`, the
    // tie-dissolution phase-diagram knob — same "P_u" initials, unrelated meaning) moved to
    // ExperimentConfig.accessProb / CLI `access_prob` (2026-07-10) so the timescale knob is
    // actually sweepable, per this file's own migrate-or-delete invariant.

    // result data parameter (RESULT_LIST removed in R21; columns come from MetricsRow insertion
    // order in OpinionDynamics.buildMetricsRow()).
    public static final int NUM_OF_BINS_OF_POSTS = 5; // % of bins of opinions in posts for analysis
    public static final int NUM_OF_BINS_OF_OPINION = NUM_OF_BINS_OF_POSTS;
    public static final int NUM_OF_BINS_OF_OPINION_FOR_WRITER = NUM_OF_BINS_OF_OPINION;

    // ---- Empirical 7-bin calibration/init target (2026-07-21) ----
    // Buntain & Snegovaya 2025 (PNAS Nexus, "Post-January 6 deplatforming..."), OSF data
    // 10.17605/OSF.IO/KQFM6, tw_handle_to_libcon.csv joined against
    // twitter.2020to2021.matched.counts.parquet (n=765 surveyed Twitter/X accounts,
    // self-reported ideological lean on a [-3,+3]/7-point scale). NOT exposed via
    // ExperimentConfig/CLI -- this is fixed survey data, not a runtime-tunable parameter (see this
    // file's class-level invariant). Deliberately kept asymmetric (not symmetrized) -- both the
    // empirical initial-opinion distribution and posting-activity-by-ideology are genuinely
    // liberal-skewed in this sample; fitting to that shape directly, per opinion-space bin, avoids
    // an arbitrary symmetrization choice. 7 equal-width bins span [-1,1] (width 2/7 each), in
    // ascending self-reported-lean order (very liberal -> very conservative).
    public static final int NUM_OF_BINS_EMPIRICAL_7 = 7;
    // Respondent counts by bin (population/self-reported-ideology distribution). Sum = 765.
    public static final int[] EMPIRICAL_OPINION_BIN_COUNTS = {160, 131, 85, 208, 46, 71, 64};
    // Mean total posts per respondent by bin, full 2020-2022 observation window (posting-activity
    // target). NOT monotonic in extremity -- the "somewhat" bins post less than moderates; only
    // the most-extreme bin shows the well-known hyper-partisan elevation (~2x moderates).
    public static final double[] EMPIRICAL_POST_BIN_WEIGHTS =
            {4328.725, 2682.863, 1503.682, 2135.798, 691.065, 1156.761, 3742.547};

    // 2026-08-25 (docs/report/2026-08-25-...): analysis-only alternate "extreme" threshold probe
    // -- does the neutral-hub effect on the extreme camp's posting/comfort rate get bigger if
    // "extreme" is narrowed from |opinion|>=0.6 (the NUM_OF_BINS_OF_OPINION=5 bin4/bin0 boundary
    // that drives feed/comfort dynamics) to |opinion|>=0.8, motivated by a visual break around
    // there in network-layout figures. Deliberately NOT touching Agent.opinionClass or any of the
    // dynamics it drives (feed composition, comfort gating) -- this is a parallel, dynamics-free
    // reclassification of the SAME simulated posts/comfort values, purely for outcome measurement,
    // so results stay comparable to the existing 0.6-boundary runs. Neutral/moderate boundary
    // left at 0.2 per the existing convention.
    // 2026-08-25: camp terminology renamed (moderate/near-extreme/extreme -> neutral/moderate/
    // extreme; see docs/report/2026-08-25-camp-terminology-rename.md) -- bin 1 (0.2<=|op|<0.8,
    // formerly "near-extreme") is now "moderate"; bin 2 (|op|<0.2, formerly "moderate") is now
    // "neutral".
    public static int band08Of(double opinion) {
        double a = Math.abs(opinion);
        if (a >= 0.8) return 0; // extreme
        if (a >= 0.2) return 1; // moderate
        return 2; // neutral
    }
}
