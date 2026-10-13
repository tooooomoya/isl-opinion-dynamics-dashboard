package experiment;

import admin.AdminOptim;
import agent.Agent;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/**
 * Applies an {@link ExperimentConfig} to the network at t=0 (initial structure; no burn-in,
 * per decision C4) and records the intervened hubs for per-run config logging (lifeline of the
 * randomize-then-regress analysis).
 *
 * Hub-selection scheme (threshold pool, not arbitrary tiers):
 *  1. Extreme background hubs = top nodes by follower count, opinion forced to +-1, Active (BOTH).
 *  2. Neutral hubs = nodes with |opinion| &lt; neutralRadius and followers &ge; threshold,
 *     excluding extremes, picked by size strategy (LARGEST / SMALLEST), opinion set to 0,
 *     channel set per config. Size (actual follower count) is logged for use as a covariate.
 */
public class InterventionSetup {

    public static class HubRecord {
        public final int id;
        public final String role;       // "extreme+", "extreme-", "neutral"
        public final int followers;
        public final Agent.ChannelMode channel;
        public final double assignedOpinion;

        public HubRecord(int id, String role, int followers, Agent.ChannelMode channel, double assignedOpinion) {
            this.id = id;
            this.role = role;
            this.followers = followers;
            this.channel = channel;
            this.assignedOpinion = assignedOpinion;
        }
    }

    // R4 (full pin, decision D3 2026-07-07): intervened hubs are EXOGENOUSLY FIXED — opinion set
    // immediately (no stale pre-intervention broadcast) and stubbornness=1 so updateMyself keeps
    // opinion == intrinsic for the whole run. NB with the coupled relay default (R3 sentinel),
    // mu=1 means a pinned hub's relays are fully flattened to its own opinion; use s_relay to weaken.
    private static void pinHub(Agent hub, double op) {
        hub.setIntrinsicOpinion(op);
        hub.setOpinion(op);
        hub.setStubbornness(1.0);
        hub.setTarget();
    }

    public static List<HubRecord> apply(Agent[] agentSet, AdminOptim admin, ExperimentConfig cfg) {
        List<HubRecord> records = new ArrayList<>();
        Set<Integer> used = new HashSet<>();
        List<Map.Entry<Integer, Integer>> ranking = admin.getFollowerRanking(); // descending by followers

        // 1. Extreme background hubs (top by followers) -> +-1, Active (BOTH).
        List<Double> extremeOpinions = new ArrayList<>();
        switch (cfg.extreme) {
            case NONE -> { /* none */ }
            case SYM -> { extremeOpinions.add(-1.0); extremeOpinions.add(1.0); }
            case ASYM -> extremeOpinions.add(cfg.asymDirection >= 0 ? 1.0 : -1.0);
        }
        int ri = 0;
        for (double op : extremeOpinions) {
            while (ri < ranking.size() && used.contains(ranking.get(ri).getKey())) ri++;
            if (ri >= ranking.size()) break;
            int id = ranking.get(ri++).getKey();
            pinHub(agentSet[id], op);
            agentSet[id].setChannelMode(Agent.ChannelMode.BOTH);
            used.add(id);
            records.add(new HubRecord(id, op > 0 ? "extreme+" : "extreme-",
                    admin.getFollowers(id).size(), Agent.ChannelMode.BOTH, op));
        }

        // 2. Neutral hub pool = top-K hubs by followers, excluding extremes.
        // Following WSSIT, opinion is *overridden* to 0 (not required to be naturally neutral),
        // decoupling opinion role from natural position and keeping a fixed-size pool every run.
        int topK = Math.min(cfg.poolTopK, ranking.size());
        List<Map.Entry<Integer, Integer>> pool = new ArrayList<>();
        for (int idx = 0; idx < topK; idx++) {
            Map.Entry<Integer, Integer> e = ranking.get(idx);
            if (used.contains(e.getKey())) continue;
            pool.add(e);
        }
        // ranking is descending; SMALLEST takes the smallest-eligible hubs first.
        if (cfg.sizeStrategy == ExperimentConfig.SizeStrategy.SMALLEST) {
            Collections.reverse(pool);
        }

        int assigned = 0;
        for (Map.Entry<Integer, Integer> e : pool) {
            if (assigned >= cfg.nNeutral) break;
            int id = e.getKey();
            pinHub(agentSet[id], 0.0);
            agentSet[id].setChannelMode(cfg.channel);
            used.add(id);
            records.add(new HubRecord(id, "neutral", admin.getFollowers(id).size(), cfg.channel, 0.0));
            assigned++;
        }
        if (assigned < cfg.nNeutral) {
            System.out.println("[InterventionSetup] WARNING: requested " + cfg.nNeutral
                    + " neutral hubs but only " + assigned + " available in top-" + topK + " pool.");
        }

        System.out.println("[InterventionSetup] " + cfg.tag() + " -> " + records.size() + " hubs intervened.");
        return records;
    }

    /** One row per intervened hub, run-level fields denormalized for easy cross-run concatenation. */
    public static void writeConfigLog(ExperimentConfig cfg, List<HubRecord> records, String folderPath) {
        StringBuilder sb = new StringBuilder();
        sb.append("seed,net_seed,extreme,n_neutral,size_strategy,channel_cfg,pool_top_k,")
          .append("beta_h,dead_after,q_eta,mu,init_dist,")
          .append("hub_id,role,followers,hub_channel,assigned_opinion\n");
        for (HubRecord r : records) {
            sb.append(cfg.seed).append(',')
              .append(cfg.resolvedNetSeed()).append(',')
              .append(cfg.extreme).append(',')
              .append(cfg.nNeutral).append(',')
              .append(cfg.sizeStrategy).append(',')
              .append(cfg.channel).append(',')
              .append(cfg.poolTopK).append(',')
              .append(cfg.betaH).append(',')
              .append(cfg.deadAfter).append(',')
              .append(cfg.qEta).append(',')
              .append(cfg.mu).append(',')
              .append(cfg.initOpinionDist).append(',')
              .append(r.id).append(',')
              .append(r.role).append(',')
              .append(r.followers).append(',')
              .append(r.channel).append(',')
              .append(String.format("%.4f", r.assignedOpinion)).append('\n');
        }
        try {
            Files.writeString(Path.of(folderPath, "run_config.csv"), sb.toString());
        } catch (IOException e) {
            System.err.println("[InterventionSetup] Failed to write run_config.csv: " + e.getMessage());
        }
    }
}
