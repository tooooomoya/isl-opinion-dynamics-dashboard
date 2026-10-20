package agent;

/**
 * A post. Originals and reshares are the same kind of object ("a reshare is a post whose content
 * is borrowed"): a reshare carries the source's X unchanged, but its author is the resharer, so
 * every like it later receives is credited to the resharer, not to the source author. Lineage
 * (root/parent/relayer/depth) is kept for cascade logging and dedup.
 *
 * A post is alive while {@code step - lastReactionStep <= L}; lastReactionStep is the step of its
 * last like or reshare (creation step if none). Dead posts leave every pool.
 */
public class Post {
    private final int postUserId;     // author (the resharer, for a reshare)
    private final double postOpinion;  // X carried by the post (the source's X, for a reshare)
    private final int postedStep;      // creation step (for a reshare: the step it was reshared)
    private int receivedReposts;       // reshares of THIS post (feeds the For-You velocity ranking)
    private int lastRepostStep;        // step of the latest reshare (lifespan diagnostics)
    private int likesReceived;         // likes of THIS post (recognition for its author)
    private int lastReactionStep;      // step of the latest like or reshare; creation step if none
    private double copyLikes;          // likes received by reshares of THIS original (shared with its author via reshare_alpha)
    private int likesByOriginator;    // likes of THIS copy that came from the original's own author (all credited to the resharer)
    private final Post root;           // root original (this post itself for an original)
    private int likesInHorizon;        // likes received within the credit horizon after creation (delayed-credit reward)
    private final int postId;
    private static int postIdCounter = 0;

    private final int rootPostId;
    private final int rootAuthorId;    // originator: author of the root post (a reshare's own author is the resharer)
    private final int parentPostId;
    private final int relayerId;
    private final int depth;
    private final boolean viaAlgo;     // the source was delivered via the algorithmic For-You stream

    /** Original post. */
    public Post(int postUserId, double postOpinion, int postedStep) {
        this.postUserId = postUserId;
        this.postOpinion = postOpinion;
        this.postedStep = postedStep;
        this.receivedReposts = 0;
        this.lastRepostStep = postedStep;
        this.likesReceived = 0;
        this.lastReactionStep = postedStep;
        this.postId = postIdCounter++;
        this.rootPostId = this.postId;
        this.root = this;
        this.rootAuthorId = postUserId;
        this.parentPostId = -1;
        this.relayerId = -1;
        this.depth = 0;
        this.viaAlgo = false;
    }

    private Post(Post parent, int resharerId, int step, boolean viaAlgo) {
        this.postUserId = resharerId;
        this.postOpinion = parent.postOpinion;
        this.postedStep = step;
        this.receivedReposts = 0;
        this.lastRepostStep = step;
        this.likesReceived = 0;
        this.lastReactionStep = step;
        this.postId = postIdCounter++;
        this.rootPostId = parent.rootPostId;
        this.root = parent.root;
        this.rootAuthorId = parent.rootAuthorId;
        this.parentPostId = parent.postId;
        this.relayerId = resharerId;
        this.depth = parent.depth + 1;
        this.viaAlgo = viaAlgo;
    }

    /** A reshare of {@code parent} by {@code resharerId} at {@code step}: same X, new author. */
    public static Post reshareOf(Post parent, int resharerId, int step, boolean viaAlgo) {
        return new Post(parent, resharerId, step, viaAlgo);
    }

    public int getPostUserId() { return postUserId; }
    public double getPostOpinion() { return postOpinion; }
    public int getPostedStep() { return postedStep; }
    public int getReceivedReposts() { return receivedReposts; }
    public int getLikesReceived() { return likesReceived; }
    public int getLikesInHorizon() { return likesInHorizon; }
    /** Likes of this copy given by the original's own author (0 for an original). */
    public int getLikesByOriginator() { return likesByOriginator; }
    /** Likes received by reshares of this original (0 for a reshare). */
    public double getCopyLikes() { return copyLikes; }
    public int getLastReactionStep() { return lastReactionStep; }
    public int getPostId() { return postId; }
    public int getLastRepostStep() { return lastRepostStep; }
    public int getRootPostId() { return rootPostId; }
    public int getRootAuthorId() { return rootAuthorId; }
    public int getParentPostId() { return parentPostId; }
    public int getRelayerId() { return relayerId; }
    public int getDepth() { return depth; }
    public boolean isRelay() { return relayerId >= 0; }
    public boolean isViaAlgo() { return viaAlgo; }
    /** Kept for the cascade log's column layout; there is no bounded-confidence gate any more. */
    public boolean isOutOfBcRelay() { return false; }

    /** alive iff the last like/reshare (or creation) was at most {@code deadAfter} steps ago. */
    public boolean isAlive(int step, int deadAfter) {
        return step - lastReactionStep <= deadAfter;
    }

    /** A like at {@code step}: credits the author, refreshes the post's life. */
    public void like(int step) { like(step, Integer.MAX_VALUE); }

    /** As {@link #like(int)}, also counting the like toward the creation-window total if within {@code creditHorizon} steps. */
    public void like(int step, int creditHorizon) { like(step, creditHorizon, -1); }

    /** As above; a like by the original's own author goes entirely to the resharer and never to the author's share (no self-credit). */
    public void like(int step, int creditHorizon, int likerId) {
        likesReceived++;
        if (root != this) {
            if (likerId == root.postUserId) likesByOriginator++; else root.copyLikes++;
        }
        if (step - postedStep <= creditHorizon) likesInHorizon++;
        lastReactionStep = step;
    }

    /** This post was reshared at {@code step}: refreshes its life, feeds the velocity ranking. */
    public void receiveRepost(int step) {
        receivedReposts++;
        lastRepostStep = step;
        lastReactionStep = step;
    }

    /** Fresh copy of the original (used by the analysis post cache; carries no engagement). */
    public Post copyPost() {
        return new Post(this.postUserId, this.postOpinion, this.postedStep);
    }
}
