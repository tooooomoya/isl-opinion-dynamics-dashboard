package dynamics;

import constants.Const;
import java.util.Arrays;

/**
 * R1/R6: per-step behavioral-event accumulators. Reset at the start of each step, incremented
 * during the agent loop, read into the metrics row at step end.
 *
 * Most fields are population-scoped (exclude pinned intervention hubs — see OpinionDynamics'
 * {@code population} flag), so hub behavior (exogenously fixed, not organic) doesn't bias
 * population-level behavioral metrics. Fields marked "all agents" are the exception.
 */
public class StepStats {
    public int activeCount;             // population agents processed this step
    public int outGroupExposureCount;   // population: feed posts read with opposite-sign opinion
    public int repostCount;             // population: reposts performed (Agent.getLastReposts())
    public int crossRepostCount;        // population: of the above, opposite-sign reposts
    public int outGroupSanctionCount;   // population: evictions/unfollows targeting an opposite-sign agent
    public int blockCount;              // population: new blocks (Agent.getLastBlocks())
    public int unfollowCount;           // population: successful unfollow() calls
    public int followCount;             // population: successful follow() calls (2026-08-06 addition --
                                         // "follow" existed as an all-agents-including-hubs count
                                         // (followActionNum) but had no population-only counterpart,
                                         // unlike unfollowCount above; added for the network-dynamism
                                         // analysis, docs/report 2026-08-06)
    public int evictionCount;           // population: capacity-eviction events

    public int originalPostCount;       // all agents (including pinned hubs)
    public int allRepostCount;          // all agents (including pinned hubs)

    // Feed-composition-by-camp: population agents only, camp = reader's opinionClass (5-bin,
    // Const.NUM_OF_BINS_OF_OPINION) at feed-build time. Counted in AdminOptim.AdminFeedback()
    // before chrono/forYou are merged (channel provenance is otherwise lost once merged into
    // Agent.feed). Sums are divided by feedClassAgentCount[cls] in buildMetricsRow to get the
    // per-agent average count, mirroring the feedPostOpinionMean_i / cRateMean_i convention.
    public double[] feedForYouCountSum = new double[Const.NUM_OF_BINS_OF_OPINION];   // delivered via algorithmic For-You slot
    public double[] feedChronoCountSum = new double[Const.NUM_OF_BINS_OF_OPINION];   // delivered via chronological-from-follows
    public double[] feedRepostCountSum = new double[Const.NUM_OF_BINS_OF_OPINION];   // post is a relay (Post.isRelay())
    public double[] feedOriginalCountSum = new double[Const.NUM_OF_BINS_OF_OPINION]; // post is an original (not relayed)
    public int[] feedClassAgentCount = new int[Const.NUM_OF_BINS_OF_OPINION];        // population agents processed, per class (denominator)
    // 2026-08-06: feed-composition-by-AUTHOR-tier (Agent.hubTier), same reader-camp indexing as
    // above -- added for the feed-composition mechanism investigation (docs/report/2026-08-02-
    // delayed-moderate-conduit-pilot.md HANDOFF: why does avgComfortRate flip sign between control
    // and N_silent as p_u/vocal_comfort_radius vary?). feedNeutCountSum = authored by the pinned
    // Neutral hub tier specifically (hubTier==2); feedHubCountSum = authored by ANY pinned hub tier
    // (hubTier>=0), the crowding-out counterpart -- lets "M's own content isn't comfortable to an
    // extreme reader but displaces feed slots" be distinguished from "M's absence changes who else
    // fills those slots."
    public double[] feedNeutCountSum = new double[Const.NUM_OF_BINS_OF_OPINION];
    public double[] feedHubCountSum = new double[Const.NUM_OF_BINS_OF_OPINION];
    // 2026-08-06: full author-opinion-class feed composition, [readerClass][authorClass] --
    // ALL authors (hub + organic), using the author's LIVE opinionClass (unlike hubTier, which is
    // frozen at pin time -- here we genuinely want "what class is this author in right now," since
    // e.g. an organic (non-hub) agent that happens to be neutral right now is exactly what we need
    // to tell apart from the pinned Neutral hub's own posts within author-class 2). Answers "ratio
    // of each opinion class's posts in a given camp's feed, control vs N_silent" directly.
    public double[][] feedAuthorClassCountSum =
            new double[Const.NUM_OF_BINS_OF_OPINION][Const.NUM_OF_BINS_OF_OPINION];
    // 2026-08-06: subset of feedAuthorClassCountSum's [readerClass][authorClass] cells that also
    // satisfy the READER's own vocal-comfort-radius check (Agent.updateMyself()'s withinComfort,
    // same threshold that drives comfortPostRate/postProb) -- added to test whether moderate
    // content displacing the silenced Neutral hub actually falls inside readers' comfort windows,
    // or just adds volume outside it. Tallied in Agent.updateMyself() (the only place a reader's own
    // vcr/opinion and each feed post are both in scope at once), using the SAME
    // agentSet[post.getPostUserId()].getOpinionClass() lookup as AdminFeedback's
    // feedAuthorClassCountSum tally, in the same agent's turn (feed build then feed read happen
    // back-to-back with no other agent's turn in between), so the two arrays are on an IDENTICAL
    // author-classification basis -- feedClassComfortCountSum[r][a] / feedAuthorClassCountSum[r][a]
    // (both population-averaged the same way) is a valid "fraction of author-class-a content that
    // counts as comfortable to reader-class-r" ratio.
    public double[][] feedClassComfortCountSum =
            new double[Const.NUM_OF_BINS_OF_OPINION][Const.NUM_OF_BINS_OF_OPINION];

    public void reset() {
        activeCount = 0;
        outGroupExposureCount = 0;
        repostCount = 0;
        crossRepostCount = 0;
        outGroupSanctionCount = 0;
        blockCount = 0;
        unfollowCount = 0;
        followCount = 0;
        evictionCount = 0;
        originalPostCount = 0;
        allRepostCount = 0;
        Arrays.fill(feedForYouCountSum, 0.0);
        Arrays.fill(feedChronoCountSum, 0.0);
        Arrays.fill(feedRepostCountSum, 0.0);
        Arrays.fill(feedOriginalCountSum, 0.0);
        Arrays.fill(feedClassAgentCount, 0);
        Arrays.fill(feedNeutCountSum, 0.0);
        Arrays.fill(feedHubCountSum, 0.0);
        for (double[] row : feedAuthorClassCountSum) Arrays.fill(row, 0.0);
        for (double[] row : feedClassComfortCountSum) Arrays.fill(row, 0.0);
    }
}
