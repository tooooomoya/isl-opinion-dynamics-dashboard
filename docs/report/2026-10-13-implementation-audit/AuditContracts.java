import admin.AdminOptim;
import agent.Agent;
import agent.Post;
import analysis.Analysis;
import analysis.AssertionCheck;
import dynamics.StepStats;
import experiment.ExperimentConfig;
import experiment.InterventionSetup;
import experiment.SimParams;
import gephi.GephiReader;
import network.*;
import rand.randomGenerator;
import writer.MetricsRow;
import writer.Writer;
import java.io.*;
import java.lang.reflect.Field;
import java.nio.file.*;
import java.util.*;

/** Independent observable contracts; failures document current implementation defects.
 * Some API-only and numerical-boundary failures are intentionally distinguished from the
 * default simulator path in the companion report. Never edits simulation output.
 */
public class AuditContracts {
    private static int passed, failed;
    private static Path scratch;
    private static final PrintStream console = System.out;
    private static void check(String id, boolean ok, String evidence) {
        if (ok) passed++; else failed++;
        console.println((ok ? "PASS " : "FAIL ") + id + " | " + evidence);
    }
    private static SimParams params(String... args) {
        return SimParams.from(ExperimentConfig.fromArgs(args));
    }
    private static Agent[] agents(int n, SimParams p) {
        Agent[] a = new Agent[n];
        for (int i = 0; i < n; i++) a[i] = new Agent(i, p);
        return a;
    }
    private static void feed(AdminOptim ad, Agent[] a, int who, int step, List<Post> ranked) {
        a[who].resetFeed();
        ad.AdminFeedback(who, a, step, ranked, new StepStats());
    }
    private static void quietMake(Network graph, Agent[] a) {
        System.setOut(new PrintStream(OutputStream.nullOutputStream()));
        try { graph.makeNetwork(a); } finally { System.setOut(console); }
    }
    private static Object field(Object o, String name) throws Exception {
        Field f = o.getClass().getDeclaredField(name); f.setAccessible(true); return f.get(o);
    }

    private static void learningAndReactions() {
        SimParams p = params("n=4", "rewire=false", "q_eta=1", "q_gamma=0.9", "q_eps=0");
        Agent a = new Agent(0, p);
        a.chooseAction(0);
        a.getQ()[0][Agent.POST] = 10;
        a.getQ()[0][Agent.LIKE] = 200;
        a.getQ()[0][Agent.RESHARE] = 300;
        a.getQ()[0][Agent.REWIRE] = 400;
        a.observeAndLearn(1);
        check("Q_NEXT_ACTION_MASK", Math.abs(a.getQ()[0][Agent.POST] - 9) < 1e-10,
              "expected 9, actual " + a.getQ()[0][Agent.POST]);
        check("Q_ONLY_PREVIOUS_ENTRY", a.getQ()[0][Agent.LIKE] == 200,
              "other entry=" + a.getQ()[0][Agent.LIKE]);

        AdminOptim ad = new AdminOptim(4, new double[4][4], p);
        Post source = new Post(1, .2, 0);
        a.addPostToFeed(source); a.like(source, 1, ad);
        check("LIKE_SELECTOR_UNIQUE", a.pickFromFeed(Agent.LIKE) == null,
              "liked item removed from reaction candidates");
        boolean choseLike = false;
        for (int i=0; i<100; i++) choseLike |= a.chooseAction(0) == Agent.LIKE;
        check("LIKE_POLICY_UNIQUE", !choseLike, "all feed items already liked");
        a.like(source, 2, ad);
        check("LIKE_API_IDEMPOTENT", source.getLikesReceived() == 1,
              "direct repeated call likes=" + source.getLikesReceived());
        Post share = a.reshare(source, 3, ad, true);
        a.addPostToFeed(Post.reshareOf(source, 2, 3, false));
        check("RESHARE_ROOT_SELECTOR_UNIQUE", a.pickFromFeed(Agent.RESHARE) == null,
              "same root has already been reshared");
        check("RESHARE_LINEAGE", share.getRootAuthorId()==1 && share.getRootPostId()==source.getRootPostId()
              && share.getParentPostId()==source.getPostId() && share.getDepth()==1,
              "root, parent and originator preserved");
        share.like(4);
        check("RESHARE_RECOGNITION_CREDIT", a.recognition(4)>0,
              "likes on reshare enter resharer's recognition");

        for (double eps : new double[]{0, 1}) {
            Agent silent = new Agent(0, params("rewire=false", "q_eps="+eps));
            silent.setChannelMode(Agent.ChannelMode.NONE);
            int act = silent.chooseAction(0);
            check("NO_ACTION_RESPECT_CHANNEL_EPS"+eps, act != Agent.POST && act != Agent.RESHARE,
                  "no permitted action; returned="+act+" (POST=0)");
        }
        Agent pinned = new Agent(0, params("mu=0.1"));
        pinned.setIntrinsicOpinion(0); pinned.setStubbornness(1); pinned.setTarget();
        pinned.addPostToFeed(new Post(1,1,0)); pinned.updateValues();
        check("PINNED_VALUE_FIXED", pinned.getOpinion()==0,
              "pinned intrinsic=0, actual opinion="+pinned.getOpinion());

        Post life = new Post(1,0,0);
        check("LIFE_BOUNDARY", life.isAlive(10,10) && !life.isAlive(11,10), "alive through t=L only");
        life.like(5);
        check("LIFE_REFRESH", life.isAlive(15,10) && !life.isAlive(16,10), "last reaction controls death");
        Agent author = new Agent(1, params("dead_after=10")); Post owned=author.makePost(0); owned.like(5);
        check("RECOGNITION_FORGETS_DEAD", author.recognition(16)==0 && author.getOwnPosts().isEmpty(),
              "likes of dead own posts removed");
    }

    private static void numericalAndFeed() {
        SimParams p=params("n=3", "beta_h=1000", "trend_share=0", "foryou_share=1", "fy_profile=false", "fy_beta=1000", "foryou_hop=0", "feed_capacity=1");
        Agent[] a=agents(3,p); a[0].setOpinion(-1);
        Post near=new Post(1,0,0), far=new Post(2,1,0);
        a[0].addPostToFeed(near); a[0].addPostToFeed(far);
        check("PICK_UNDERFLOW_STABLE", a[0].pickFromFeed(Agent.LIKE)==near,
              "beta=1000, distances=1 and 2; nearer item should dominate");
        AdminOptim ad=new AdminOptim(3,new double[3][3],p);
        ad.addRecentPost(near); ad.addRecentPost(far); ad.rebuildAuthorIndex();
        feed(ad,a,0,1,null);
        check("FY_UNDERFLOW_NONEMPTY", a[0].getFeed().size()==1 && a[0].getFeed().get(0)==near,
              "eligible posts=2, delivered="+a[0].getFeed().size());

        SimParams rp=params("n=4","beta_h=1000"); Agent[] ra=agents(4,rp);
        ra[0].setOpinion(-1);ra[1].setOpinion(1);ra[2].setOpinion(0);ra[3].setOpinion(1);
        AdminOptim rad=new AdminOptim(4,new double[][]{{0,1,0,0},{0,0,0,0},{0,0,0,0},{0,0,0,0}},rp);
        ra[0].addPostToFeed(new Post(2,0,0));ra[0].addPostToFeed(new Post(3,1,0));
        int replacement=ra[0].rewire(rad,ra);
        check("REWIRE_UNDERFLOW_STABLE", replacement==2,"expected new followee=2, actual="+replacement);

        for (boolean fy : new boolean[]{false,true}) {
            SimParams cp=params("n=3","trend_share="+(fy?"0":"1"),"trend_hop=1",
                    "foryou_share="+(fy?"1":"0"),"foryou_hop=1","fy_profile=false","feed_capacity=1","feed_decay_mode=hard");
            Agent[] ca=agents(3,cp);AdminOptim cad=new AdminOptim(3,new double[][]{{0,1,0},{0,0,0},{0,0,0}},cp);
            Post old=new Post(1,0,0), fresh=new Post(2,0,0);
            cad.addRecentPost(old);cad.addRecentPost(fresh);cad.rebuildAuthorIndex();
            List<Post> ranked=cad.rankByVelocity(1);feed(cad,ca,0,1,ranked);
            cad.removeFollowEdge(0,1);cad.addFollowEdge(0,2);feed(cad,ca,0,2,ranked);
            boolean correct=ca[0].getFeed().size()==1 && ca[0].getFeed().get(0).getPostUserId()==2;
            check((fy?"FY":"TREND")+"_REACH_AFTER_EDGE_CHANGE",correct,
                  "now follows 2; shown="+(ca[0].getFeed().isEmpty()?"empty":ca[0].getFeed().get(0).getPostUserId()));
        }

        boolean invariant=true;
        for(int trial=0;trial<100;trial++) {
            randomGenerator.init(1000+trial,1000+trial);
            SimParams fp=params("n=8","feed_capacity=10","trend_share=0.3","foryou_share=0.4","fy_profile=false","foryou_hop=0","trend_hop=0","dead_after=10");
            Agent[] fa=agents(8,fp);double[][] w=new double[8][8]; for(int i=1;i<8;i++)w[0][i]=1;
            AdminOptim fad=new AdminOptim(8,w,fp);
            for(int i=0;i<30;i++) {
                Post post=new Post(i%8,-1+(i%10)/5.0,i%3==0?-20:0);
                fad.addRecentPost(post);fa[0].addToPostCash(post);
                if(i%4==0) {Post copy=Post.reshareOf(post,(i+1)%8,0,false);fad.addRecentPost(copy);fa[0].addToPostCash(copy);}
            }
            fad.sweepDead(1);fad.rebuildAuthorIndex();feed(fad,fa,0,1,fad.rankByVelocity(1));
            Set<Integer> roots=new HashSet<>();
            invariant &= fa[0].getFeed().size()<=10;
            for(Post post:fa[0].getFeed())invariant &= post.getPostUserId()!=0 && post.isAlive(1,10) && roots.add(post.getRootPostId());
            invariant &= fad.getCreatedPostCount()==fad.getAlivePostCount()+fad.getDiedPostCount();
        }
        check("FEED_INVARIANTS_100_SEEDS",invariant,"capacity, own author exclusion, root dedup, live posts, pool conservation");
    }

    private static void graphAndMetrics() throws Exception {
        randomGenerator.init(50,50);SimParams p=params("n=8");Agent[] a=agents(8,p);
        Network small=new WattsStrogatzNetwork(8,30,.1);quietMake(small,a);
        boolean noSelf=true;for(int i=0;i<8;i++)noSelf &= small.getEdge(i,i)==0;
        check("WS_SMALL_NO_SELF",noSelf,"n=8, default ws_out=15");
        boolean reciprocal=true;
        AdminOptim ad=new AdminOptim(8,new double[8][8],p);
        for(int k=0;k<5000;k++) {
            int i=randomGenerator.dynamics().nextInt(8),j=randomGenerator.dynamics().nextInt(8);
            if(i==j)continue;
            if(randomGenerator.dynamics().nextBoolean())ad.addFollowEdge(i,j);else ad.removeFollowEdge(i,j);
            for(int u=0;u<8;u++) {
                reciprocal &= ad.getFollowerList()[u]==ad.getFollowers(u).size();
                for(int v=0;v<8;v++)reciprocal &= ad.follows(u,v)==ad.getFollowers(v).contains(u);
            }
        }
        check("GRAPH_REVERSE_INDEX_5000_OPERATIONS",reciprocal,"forward/reverse edges and follower counts agree");
        boolean fixed=true;String hkExample="none";
        for(int seed=0;seed<1000 && fixed;seed++) {
            randomGenerator.init(seed,seed);Network hk=new HolmeKimNetwork(60,15,1,.05);quietMake(hk,agents(60,params("n=60")));
            for(int i=0;i<60;i++){int deg=0;for(int j=0;j<60;j++)if(hk.getEdge(i,j)>0)deg++;if(deg!=15){fixed=false;hkExample="seed="+seed+", node="+i+", degree="+deg;break;}}
        }
        check("HK_FIXED_OUT_DEGREE",fixed,"valid hk_m=15,hk_a=1,hk_pt=.05; "+hkExample);

        Agent[] pop=agents(2,params("n=2"));pop[0].setOpinion(0);pop[1].setOpinion(0);pop[1].setTarget();
        pop[0].addPostToFeed(new Post(1,-1,0));pop[1].addPostToFeed(new Post(0,1,0));
        Analysis metrics=new Analysis(2);metrics.setFeedMap(pop[0]);metrics.setFeedMap(pop[1]);metrics.computeFeedMetrics(pop);
        check("FEED_METRIC_POPULATION_FILTER",metrics.getFeedMeanArray()[2]==-1,
              "population reader mean=-1, reported="+metrics.getFeedMeanArray()[2]);
        pop[0].setTarget();
        check("EMPTY_POPULATION_FINITE",Double.isFinite(metrics.computeVarianceOpinion(pop)) && Double.isFinite(metrics.computeMeanOpinion(pop)),
              "all targeted: variance="+metrics.computeVarianceOpinion(pop)+", mean="+metrics.computeMeanOpinion(pop));

        Agent[] one=agents(1,params("n=1"));Network empty=new RandomNetwork(1,0);quietMake(empty,one);
        AdminOptim iad=new AdminOptim(1,new double[1][1],params("n=1"));
        AssertionCheck ac=new AssertionCheck(one,empty,1,1);ac.snapshotOutDegrees(iad);one[0].setOpinion(2);ac.assertionChecker(one,iad,1,1);
        ByteArrayOutputStream capture=new ByteArrayOutputStream();System.setOut(new PrintStream(capture));ac.reportASError();System.setOut(console);
        check("ASSERT_FINAL_STEP_INCLUDED",!capture.toString().contains("reported : 0"),capture.toString().trim());
        AssertionCheck nan=new AssertionCheck(one,empty,1,2);nan.snapshotOutDegrees(iad);one[0].setOpinion(Double.NaN);nan.assertionChecker(one,iad,1,1);
        int[] errors=(int[])field(nan,"numOfError");check("ASSERT_REJECTS_NAN",errors[1]>0,"NaN opinion error count="+errors[1]);
    }

    private static void configAndIO() throws Exception {
        String[] invalid={"q_gamma=1.1","q_eta=-0.1","q_eps=2","q_tau=NaN","access_prob=2","rho_l=2","recog_mix=2","l_ref=0","feed_capacity=0","dead_after=-1","i_edge_lo=0.9","trend_share=NaN","init_dist=empirical","vel_mode=typo","feed_decay_mode=typo"};
        int accepted=0;for(String token:invalid){try{params(token);accepted++;}catch(IllegalArgumentException expected){}}
        check("CONFIG_REJECT_INVALID",accepted==0,"invalid configs accepted="+accepted+"/"+invalid.length);
        boolean unknownRejected=false;try{params("bc_dec=0.99");}catch(IllegalArgumentException ex){unknownRejected=true;}
        check("CONFIG_REJECT_REMOVED_KEY",unknownRejected,"removed knob bc_dec silently accepted="+!unknownRejected);
        String[][] pairs={{"interaction_window=100","interaction_window=200"},{"q_tau=0.1001","q_tau=0.1002"},{"read_path=a.gexf","read_path=b.gexf"},{"pin_opinion_ids=0:0.1","pin_opinion_ids=0:0.9"}};
        int collisions=0;for(String[] pair:pairs)if(ExperimentConfig.fromArgs(new String[]{pair[0]}).resultFolder().equals(ExperimentConfig.fromArgs(new String[]{pair[1]}).resultFolder()))collisions++;
        check("CONFIG_ID_DISTINCT",collisions==0,"distinct output path collisions="+collisions+"/"+pairs.length);
        Path cfgdir=Files.createDirectories(scratch.resolve("config"));
        InterventionSetup.writeConfigLog(new ExperimentConfig(),List.of(),cfgdir.toString());
        long lines=Files.lines(cfgdir.resolve("run_config.csv")).count();
        check("CONFIG_SAVED_WITHOUT_HUBS",lines>1,"run_config.csv lines="+lines);

        String xml="<gexf xmlns=\"http://gexf.net/1.3\"><graph defaultedgetype=\"directed\"><attributes class=\"node\"><attribute id=\"opinion\" title=\"opinion\" type=\"double\"/><attribute id=\"intrinsicopinion\" title=\"intrinsicOpinion\" type=\"double\"/><attribute id=\"accessprob\" title=\"accessProb\" type=\"double\"/></attributes><nodes><node id=\"0\"><attvalues><attvalue for=\"opinion\" value=\"0.5\"/><attvalue for=\"intrinsicopinion\" value=\"0.1\"/><attvalue for=\"accessprob\" value=\"0.8\"/></attvalues></node><node id=\"1\"/></nodes><edges><edge source=\"0\" target=\"1\"/></edges></graph></gexf>";
        Path gexf=scratch.resolve("export-format.gexf");Files.writeString(gexf,xml);Agent[] a=agents(2,params("n=2"));GephiReader.readGraphNodes(a,gexf.toString());
        check("GEXF_ACCESS_ROUNDTRIP",a[0].getAccessProb()==.8,"exported accessprob=.8, read="+a[0].getAccessProb());
        check("GEXF_CURRENT_AND_INTRINSIC",a[0].getOpinion()==.5 && a[0].getIntrinsicOpinion()==.1,
              "current .5 / intrinsic .1, read="+a[0].getOpinion()+" / "+a[0].getIntrinsicOpinion());
        Path old=scratch.resolve("format12.gexf");Files.writeString(old,xml.replace("http://gexf.net/1.3","http://www.gexf.net/1.2draft"));
        check("GEXF_NAMESPACE12",GephiReader.readGraphEdges(2,old.toString())[0][1]==1,"1.2draft valid edge 0->1");
        boolean missingRejected=false;try{GephiReader.readGraphEdges(2,scratch.resolve("missing.gexf").toString());}catch(Exception ex){missingRejected=true;}
        check("GEXF_MISSING_FAILS",missingRejected,"missing input returns an empty graph instead of failing="+!missingRejected);

        Path notdir=scratch.resolve("not-directory");Files.writeString(notdir,"x");Writer broken=new Writer(notdir.toString());MetricsRow row=new MetricsRow();row.put("value",.5);broken.setMetrics(row);broken.write();
        boolean writeRejected=false;try{broken.flush();}catch(Exception ex){writeRejected=true;}
        check("OUTPUT_FAILURE_PROPAGATES",writeRejected,"flush returned; remaining metrics buffer="+((StringBuilder)field(broken,"metricsBuf")).length());
        Path localedir=Files.createDirectories(scratch.resolve("locale"));for(String sub:List.of("metrics","posts","opinion"))Files.createDirectories(localedir.resolve(sub));
        Locale saved=Locale.getDefault();
        try{Locale.setDefault(Locale.GERMANY);Writer writer=new Writer(localedir.toString());writer.setMetrics(row);writer.write();writer.flush();List<String> rows=Files.readAllLines(localedir.resolve("metrics/results.csv"));
            check("CSV_LOCALE_INDEPENDENT",rows.get(0).split(",").length==rows.get(1).split(",").length,"header="+rows.get(0)+", row="+rows.get(1));
        }finally{Locale.setDefault(saved);}
    }

    public static void main(String[] args) throws Exception {
        scratch=Path.of(args[0]);Files.createDirectories(scratch);randomGenerator.init(0,0);
        learningAndReactions();numericalAndFeed();graphAndMetrics();configAndIO();
        console.println("CONTRACT_TOTAL passed="+passed+" failed="+failed);
        if(failed>0)System.exit(1);
    }
}
