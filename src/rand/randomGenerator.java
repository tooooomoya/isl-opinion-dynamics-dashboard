package rand;

import java.util.Random;

/**
 * Named RNG streams (R15, docs/report/2026-07-07-model-revision-requirements.md).
 *
 * network()      — network generation only; seeded by net_seed (default = seed), so the
 *                  initial graph can be held fixed while dynamics noise varies.
 * intervention() — hub selection / experiment setup (currently deterministic, stream reserved).
 * dynamics()     — everything else: agent behavior, shuffles, feeds, initial opinions.
 *
 * Streams are derived deterministically: network from netSeed, dynamics from seed,
 * intervention from seed offset by a fixed odd constant (golden-ratio increment) so the
 * two never coincide for any int seed.
 */
public final class randomGenerator {

    private static Random networkRand;
    private static Random interventionRand;
    private static Random dynamicsRand;

    private randomGenerator() {}

    /** Call once from main before constructing the simulator. */
    public static void init(int seed, int netSeed) {
        networkRand = new Random(netSeed);
        interventionRand = new Random((long) seed + 0x9E3779B9L);
        dynamicsRand = new Random(seed);
    }

    public static Random network() {
        return checked(networkRand);
    }

    public static Random intervention() {
        return checked(interventionRand);
    }

    public static Random dynamics() {
        return checked(dynamicsRand);
    }

    private static Random checked(Random r) {
        if (r == null) {
            throw new IllegalStateException("randomGenerator not initialized — call init(seed, netSeed) first");
        }
        return r;
    }
}
