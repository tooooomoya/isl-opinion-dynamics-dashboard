package network;

import constants.Const;
import experiment.ExperimentConfig;

/**
 * R24 (docs/report/2026-07-07-model-revision-requirements.md): resolve the initial network from
 * config instead of editing/recompiling a comment block in OpinionDynamics.setNetwork().
 *
 * DC-SBM exposes its parameters as CLI keys (sbm_k, sbm_pin, sbm_pout, sbm_gamma, sbm_deg) — it
 * was the neutral-hub study's own network (research-direction.md), not the general default.
 * hk (the ExperimentConfig default) also exposes its params as CLI keys (hk_m/hk_a/hk_pt) — it is
 * now this paper's calibration-baseline network (2026-07-16, docs/report/calibration-sweep-results.md),
 * superseding the 2026-07-10 journal.tex-matching rationale. Other generators keep their
 * documented hardcoded parameters; wire up CLI keys for them only if a study starts varying them.
 */
public final class NetworkFactory {

    private NetworkFactory() {}

    public static Network create(ExperimentConfig cfg, int n) {
        switch (cfg.networkType) {
            case "dcsbm":
                // Study default. Current calibration lived in setNetwork(): targetDeg=50 (not the
                // class docstring's 10) lands rank50/rank100 in the mid-tier band. See
                // docs/report/2026-06-26-implementation.md.
                return new DCSBMNetwork(n, cfg.sbmK, cfg.sbmPin, cfg.sbmPout, cfg.sbmGamma, cfg.sbmDeg);
            case "ba":
                return new BarabasiAlbertNetwork(n, 3);
            case "hk":
                // params on CLI (hk_m/hk_a/hk_pt); defaults calibrated 2026-07-16 against
                // Kwak et al. 2010 (m=15/A=4/pt=0.05) — see class docstring.
                return new HolmeKimNetwork(n, cfg.hkM, cfg.hkA, cfg.hkPt);
            case "hkshuf":
                // degree-matched control: HK graph, then double edge swaps (same in/out degrees, random wiring)
                return new HolmeKimShuffledNetwork(n, cfg.hkM, cfg.hkA, cfg.hkPt);
            case "ws":
                // K = 2 * wsOut: the generator adds edges to the next K/2 agents, so wsOut is the out-degree
                return new WattsStrogatzNetwork(n, 2 * cfg.wsOut, cfg.wsBeta);
            case "dms":
                return new DMSNetwork(n, 3, 2);
            case "cnn":
                return new ConnectingNearestNeighborNetwork(n, 0.3);
            case "lfr":
                return new LFRNetwork(n, 10, 50, 0.2, 2.5, 1.5, 10, 50);
            case "homophily":
                return new HomophilyNetwork(n, cfg.homOut, cfg.homGamma);
            case "dba":
                return new DirectedBANetwork(n, cfg.baOut, cfg.baAttract);
            case "random":
                return new RandomNetwork(n, cfg.randomP);
            case "read":
                return new ReadNetwork(n, cfg.readPath);
            default:
                throw new IllegalArgumentException("Unknown network type: '" + cfg.networkType
                        + "' (expected dcsbm|ba|hk|hkshuf|ws|dba|dms|cnn|lfr|random|homophily|read)");
        }
    }
}
