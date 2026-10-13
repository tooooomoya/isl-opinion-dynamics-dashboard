import agent.*; import admin.*; import experiment.*; import rand.randomGenerator; import dynamics.StepStats; import java.util.*;
public class ReviewProbe {
 static SimParams p(String... a){return SimParams.from(ExperimentConfig.fromArgs(a));}
 public static void main(String[] args){
 randomGenerator.init(123,123);
 Agent a=new Agent(0,p("rewire=false","q_eta=1","q_gamma=0.9","q_eps=0")); a.setOpinion(0); a.addPostToFeed(new Post(1,0,0)); int st=a.observeAndLearn(0); a.getQ()[st][Agent.REWIRE]=100; int act=a.chooseAction(st); a.observeAndLearn(1); System.out.println("UNAVAILABLE_BOOTSTRAP action="+act+" updatedQ="+a.getQ()[st][act]+" expectedAvailableOnly=1.0");
 Agent empty=new Agent(0,p("rewire=false","q_eta=1","q_eps=0")); int e=empty.observeAndLearn(0); empty.getQ()[e][Agent.LIKE]=100; empty.chooseAction(e); empty.observeAndLearn(1); System.out.println("EMPTY_FEED_BOOTSTRAP Qpost="+empty.getQ()[e][Agent.POST]+" expectedAvailableOnly=0.0");
 Post src=new Post(1,0,0); AdminOptim admin=new AdminOptim(2,new double[2][2],p("n=2")); a.like(src,1,admin); a.like(src,2,admin); System.out.println("REPEAT_LIKE sameAgentSamePost count="+src.getLikesReceived()+" lastReactionStep="+src.getLastReactionStep());
 Agent sil=new Agent(0,p("rewire=false","q_eps=1")); sil.setChannelMode(Agent.ChannelMode.NONE); try{sil.chooseAction(0);System.out.println("NO_AVAILABLE unexpectedlySucceeded");}catch(Exception ex){System.out.println("NO_AVAILABLE "+ex);}
 Agent sil2=new Agent(0,p("rewire=false","q_eps=0")); sil2.setChannelMode(Agent.ChannelMode.NONE); System.out.println("NO_AVAILABLE_EPS0 returned="+sil2.chooseAction(0)+" (POST=0 but posting disabled)");
 ExperimentConfig t1=ExperimentConfig.fromArgs(new String[]{"foryou_share=0.7","interaction_window=100"}); ExperimentConfig t2=ExperimentConfig.fromArgs(new String[]{"foryou_share=0.7","interaction_window=200"});System.out.println("TAG_COLLISION interactionWindow100vs200="+t1.resultFolder().equals(t2.resultFolder()));
 ExperimentConfig z1=ExperimentConfig.fromArgs(new String[]{"q_tau=0.1001"});ExperimentConfig z2=ExperimentConfig.fromArgs(new String[]{"q_tau=0.1002"});System.out.println("TAG_COLLISION qTau1001vs1002="+z1.resultFolder().equals(z2.resultFolder()));
 SimParams tiny=p("trend_share=0","foryou_share=0.7","fy_profile=false","feed_capacity=1"); Agent[] aa={new Agent(0,tiny),new Agent(1,tiny)}; AdminOptim ad=new AdminOptim(2,new double[][]{{0,1},{0,0}},tiny); ad.addRecentPost(new Post(1,0,0)); ad.rebuildAuthorIndex(); ad.AdminFeedback(0,aa,1,null,new StepStats()); System.out.println("FLOORED_FEED S=1 fyShare=.7 feedSize="+aa[0].getFeed().size()+" (fySlots=floor(.7)=0)");
 }
}