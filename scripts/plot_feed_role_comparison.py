#!/usr/bin/env python3
"""Figures for the five-seed feed comparison; PNG, SVG and PDF exports.

PYENV_VERSION=3.11.9 python scripts/plot_feed_role_comparison.py
Requires matplotlib and numpy. No simulations are run.
"""
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, colors
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "results/feed_role_compare"
OUT = ROOT / "docs/report/figures/feed-position-x-2026-10-14"
REPORT = ROOT / "docs/report/2026-10-14-feed-position-x-comparison.md"
FEEDS = ["foryou", "chrono", "trend"]
NAMES = {"foryou":"For You 100%", "chrono":"Chrono 100%", "trend":"Trend 100%"}
TIERS = ["0", "1-4", "5-19", "20-49", "50+"]
TLABELS = ["0人", "1〜4人", "5〜19人", "20〜49人", "50人以上"]
XGROUPS = ["central", "middle", "edge"]
XLABELS = ["中央帯", "中間帯", "端"]
ACTIONS = ["post", "like", "reshare"]
ANAMES = {"post":"POST｜オリジナル投稿", "like":"LIKE｜いいね", "reshare":"RESHARE｜再共有"}
ANAMES_EN = {"post":"POST: original post", "like":"LIKE", "reshare":"RESHARE"}
TLABELS_EN = ["0", "1–4", "5–19", "20–49", "50+"]
XLABELS_EN = ["Neutral", "Moderate", "Extreme"]
PALETTE = {"post":"#2878B5", "like":"#E69F00", "reshare":"#16836B"}
INK = "#23313F"
FOOT = "η=0.03・k=20・rewire off｜seed 0〜4｜末尾5,000 step｜セル内は個人を等重み、seed間も等重み"
FOOT_EN = "η = 0.03; k = 20; rewire off | Seeds 0–4 | Final 5,000 steps | Equal agent weights within groups; equal seed weights"
FIGURES = []


def load_json(name):
    return json.loads((DATA/name).read_text())


def load_csv(name):
    with (DATA/name).open() as f:
        return list(csv.DictReader(f))


def setup():
    available = {f.name for f in font_manager.fontManager.ttflist}
    family = next((f for f in ["Hiragino Sans", "Noto Sans CJK JP", "Arial Unicode MS"] if f in available), "DejaVu Sans")
    plt.rcParams.update({"font.family":[family,"DejaVu Sans"], "font.size":11,
                         "axes.titlesize":15, "axes.labelsize":11,
                         "text.color":INK, "axes.labelcolor":INK,
                         "xtick.color":INK, "ytick.color":INK,
                         "axes.spines.top":False, "axes.spines.right":False,
                         "axes.spines.left":False, "axes.spines.bottom":False,
                         "figure.facecolor":"white", "axes.facecolor":"white",
                         "svg.fonttype":"path", "pdf.fonttype":42})
    OUT.mkdir(parents=True,exist_ok=True)
    assert load_json("validation.json")["complete"]


def cell(rows, feed, tier, x):
    r = next(r for r in rows if r["feed"]==feed and r["tier"]==tier
             and r["x_group"]==x and r["cutoffs"]=="thirds" and not r["signed"])
    assert r["n_seeds"]==5
    return r


def finish(fig, stem, title, caption, footer=FOOT):
    fig.text(.025,.017,footer,fontsize=9,color="#667481")
    for ext in ["png","svg","pdf"]:
        fig.savefig(OUT/(stem+"."+ext),dpi=180,bbox_inches="tight",pad_inches=.2)
    plt.close(fig)
    FIGURES.append({"stem":stem,"title":title,"caption":caption})


def overview(rows):
    title = "1 | Action choice by follower group"
    populations = [cell(rows,"foryou",t,"ALL")["n_agents"] for t in TIERS]
    population_total = cell(rows,"foryou","ALL","ALL")["n_agents"]
    assert population_total == 1000 and np.isclose(sum(populations),population_total)
    shares = np.array(populations)/population_total*100
    for feed in FEEDS:
        assert all(np.isclose(cell(rows,feed,t,"ALL")["n_agents"],n) for t,n in zip(TIERS,populations))
    group_labels = [f"{label} followers\n{share:.1f}% of population" for label,share in zip(TLABELS_EN,shares)]
    fig,axes = plt.subplots(1,3,figsize=(15.5,6.5),sharey=True)
    fig.subplots_adjust(left=.17,right=.98,top=.73,bottom=.17,wspace=.12)
    fig.suptitle(title,x=.025,y=.99,ha="left",fontsize=20)
    fig.text(.025,.935,"Each bar shows the group's action mix (100%). Blue = POST; orange = LIKE; green = RESHARE.",fontsize=11)
    fig.text(.025,.895,"Population shares count agents, not actions: five-seed means, N = 1,000 per seed; identical across feed modes.",fontsize=10,color="#667481")
    for ax,feed in zip(axes,FEEDS):
        left = np.zeros(5)
        for action in ACTIONS:
            values = np.array([cell(rows,feed,t,"ALL")["share_"+action]*100 for t in TIERS])
            ax.barh(range(5),values,left=left,height=.65,color=PALETTE[action],edgecolor="white",linewidth=1)
            for y,(v,l) in enumerate(zip(values,left)):
                if v>=7:
                    ax.text(l+v/2,y,f"{v:.0f}%",ha="center",va="center",fontsize=11,
                            color=INK if action=="like" else "white")
            left += values
        assert np.allclose(left,100,atol=1e-8)
        ax.set_title(NAMES[feed],pad=15)
        ax.set_xlim(0,100); ax.set_xticks([0,25,50,75,100]); ax.set_xlabel("Action share (%)")
        ax.set_yticks(range(5),group_labels); ax.tick_params(axis="y",length=0)
        ax.set_axisbelow(True); ax.grid(axis="x",alpha=.15)
    axes[0].invert_yaxis(); axes[0].set_ylabel("Follower count (in-degree)",labelpad=12)
    fig.legend(handles=[Patch(facecolor=PALETTE[a],label=ANAMES_EN[a]) for a in ACTIONS],
               loc="upper center",bbox_to_anchor=(.58,.85),ncol=3,frameon=False)
    finish(fig,"01_roles_by_followers",title,
           "Five-seed mean action shares, pooling X groups. Row labels also give each follower group's share of the whole population (agent counts, not action counts).",FOOT_EN)


def heatmaps(rows):
    title = "2 | Action shares by X group and follower count"
    fig,axes = plt.subplots(3,3,figsize=(14,12))
    fig.subplots_adjust(left=.10,right=.89,top=.88,bottom=.10,wspace=.24,hspace=.30)
    fig.suptitle(title,x=.025,y=.99,ha="left",fontsize=20)
    fig.text(.025,.947,"Cells show action shares (%). Darker colors indicate higher shares. All panels use the same 0–100% scale.",fontsize=11)
    fig.text(.025,.916,"Neutral: |X| < 1/3       Moderate: 1/3 ≤ |X| < 2/3       Extreme: |X| ≥ 2/3",fontsize=10,color="#667481")
    for i,action in enumerate(ACTIONS):
        cmap = colors.LinearSegmentedColormap.from_list(action,["#F6F8FA",PALETTE[action]])
        for j,feed in enumerate(FEEDS):
            ax = axes[i,j]
            vals = np.array([[cell(rows,feed,t,x)["share_"+action]*100 for x in XGROUPS] for t in TIERS])
            im = ax.imshow(vals,vmin=0,vmax=100,cmap=cmap,aspect="auto")
            for y in range(5):
                for x in range(3):
                    ax.text(x,y,f"{vals[y,x]:.1f}",ha="center",va="center",fontsize=12,
                            color="white" if vals[y,x]>65 and action!="like" else INK)
            ax.set_xticks(range(3),XLABELS_EN); ax.set_yticks(range(5),TLABELS_EN if j==0 else [""]*5)
            ax.tick_params(length=0)
            if i==0: ax.set_title(NAMES[feed],pad=12)
            if j==0: ax.set_ylabel(ANAMES_EN[action]+"\nFollower count",labelpad=12,color=PALETTE[action])
        box=axes[i,2].get_position(); cax=fig.add_axes([.92,box.y0,.014,box.height])
        cb=fig.colorbar(im,cax=cax,ticks=[0,25,50,75,100]); cb.set_label("Action share (%)")
    finish(fig,"02_position_x_action_heatmaps",title,
           "Rows are follower-count groups; columns are Neutral, Moderate, and Extreme X groups. POST, LIKE, and RESHARE have separate panels with fixed 0–100% scales.",FOOT_EN)


def stacked_by_x(rows):
    title = "1b | Action choice by feed, X group, and follower count"
    fig,axes = plt.subplots(3,3,figsize=(16,12),sharex=True,sharey="row")
    fig.subplots_adjust(left=.22,right=.985,top=.81,bottom=.095,wspace=.10,hspace=.22)
    fig.suptitle(title,x=.025,y=.99,ha="left",fontsize=20)
    fig.text(.025,.947,"Each bar shows the action mix within an X × follower group (100%). Bars are contiguous within each panel.",fontsize=11)
    fig.text(.025,.916,"Population labels show each X × follower group's share of all agents; five-seed means, N = 1,000 per seed.",fontsize=10,color="#667481")
    fig.legend(handles=[Patch(facecolor=PALETTE[a],label=ANAMES_EN[a]) for a in ACTIONS],
               loc="upper center",bbox_to_anchor=(.59,.887),ncol=3,frameon=False)
    thresholds=["|X| < 1/3", "1/3 ≤ |X| < 2/3", "|X| ≥ 2/3"]
    total=cell(rows,"foryou","ALL","ALL")["n_agents"]
    for i,(x,xlabel,threshold) in enumerate(zip(XGROUPS,XLABELS_EN,thresholds)):
        x_count=cell(rows,"foryou","ALL",x)["n_agents"]
        counts=[cell(rows,"foryou",t,x)["n_agents"] for t in TIERS]
        assert np.isclose(sum(counts),x_count)
        labels=[f"{label} followers\n{100*n/total:.1f}% of population" for label,n in zip(TLABELS_EN,counts)]
        for j,feed in enumerate(FEEDS):
            ax=axes[i,j]; left=np.zeros(5)
            assert all(np.isclose(cell(rows,feed,t,x)["n_agents"],n) for t,n in zip(TIERS,counts))
            for action in ACTIONS:
                values=np.array([cell(rows,feed,t,x)["share_"+action]*100 for t in TIERS])
                ax.barh(range(5),values,left=left,height=1.0,color=PALETTE[action],edgecolor="white",linewidth=.6)
                for y,(v,l) in enumerate(zip(values,left)):
                    if v>=7:
                        ax.text(l+v/2,y,f"{v:.0f}%",ha="center",va="center",fontsize=10,
                                color=INK if action=="like" else "white")
                left+=values
            assert np.allclose(left,100,atol=1e-8)
            ax.set_xlim(0,100); ax.set_ylim(4.5,-.5)
            ax.set_xticks([0,25,50,75,100]); ax.set_yticks(range(5),labels)
            ax.tick_params(axis="y",length=0,labelsize=9)
            ax.tick_params(axis="x",length=0,labelbottom=True,labelsize=9)
            if i==0: ax.set_title(NAMES[feed],pad=14)
            if i==2: ax.set_xlabel("Action share (%)")
        box=axes[i,0].get_position(); center=(box.y0+box.y1)/2
        fig.text(.025,center+.035,xlabel,fontsize=18,ha="left",va="center")
        fig.text(.025,center+.005,threshold,fontsize=10,ha="left",va="center",color="#667481")
        fig.text(.025,center-.025,f"{100*x_count/total:.1f}% of\nall agents",fontsize=10,ha="left",va="center",color="#667481")
    finish(fig,"05_stacked_roles_by_x",title,
           "Columns are feed modes; rows are Neutral, Moderate, and Extreme. Within each panel, contiguous bars show the five follower groups. Blue = POST, orange = LIKE, green = RESHARE. Population labels are joint X × follower-group shares of the whole population, not percentages within the X group.",FOOT_EN)


def seed_lines(raw):
    title = "3｜XによるPOSTの違いは、seedごとに再現するか"
    fig,axes=plt.subplots(2,3,figsize=(14,8.4),sharex=True,sharey=True)
    fig.subplots_adjust(left=.08,right=.98,top=.80,bottom=.15,wspace=.17,hspace=.29)
    fig.suptitle(title,x=.025,y=.99,ha="left",fontsize=20)
    fig.text(.025,.93,"灰色の線＝各seed、青い太線＝５seed平均。灰色が逆方向に動く箇所は、平均だけで断定しない。",fontsize=11)
    for i,tier in enumerate(["5-19","50+"]):
        for j,feed in enumerate(FEEDS):
            ax=axes[i,j]; data=[]
            for seed in range(5):
                vals=[]
                for x in XGROUPS:
                    r=next(r for r in raw if r["feed"]==feed and int(r["seed"])==seed and r["tier"]==tier
                           and r["x_group"]==x and r["cutoffs"]=="thirds" and r["signed"]=="False")
                    vals.append(float(r["share_post"])*100)
                data.append(vals)
                ax.plot(range(3),vals,color="#B6BDC5",alpha=.9,lw=1.4,marker="o",markersize=4)
            means=np.mean(data,axis=0)
            ax.plot(range(3),means,color=PALETTE["post"],lw=3,marker="o",markersize=7,zorder=5)
            for x,y in enumerate(means):
                ax.annotate(f"{y:.1f}%",(x,y),xytext=(0,9),textcoords="offset points",ha="center",
                            color=PALETTE["post"],fontsize=10,zorder=6,
                            bbox=dict(facecolor="white",alpha=.8,edgecolor="none",pad=1))
            ax.set_ylim(0,100); ax.set_xlim(-.18,2.18); ax.set_xticks(range(3),XLABELS)
            ax.set_yticks([0,25,50,75,100]); ax.grid(axis="y",alpha=.15); ax.tick_params(length=0)
            ax.set_title(NAMES[feed]+"｜"+("5〜19人層" if i==0 else "50人以上層"),fontsize=13)
            if j==0: ax.set_ylabel("POST選択率 (%)")
    fig.legend(handles=[Line2D([0],[0],color="#B6BDC5",lw=1.5,marker="o",label="各seed（５本）"),
                        Line2D([0],[0],color=PALETTE["post"],lw=3,marker="o",label="５seed平均")],
               loc="upper center",bbox_to_anchor=(.5,.885),ncol=2,frameon=False)
    finish(fig,"03_x_effect_seed_variation",title,
           "seedの線は同じseed内のX帯間の比較。誤差帯や信頼区間ではなく、５本の実測runとその平均を示す。")


def differences(raw):
    title="4｜For Youから切り替えると、POSTは何ポイント変わるか"
    fig,axes=plt.subplots(1,2,figsize=(12.5,6.8),sharey=True)
    fig.subplots_adjust(left=.10,right=.88,top=.79,bottom=.15,wspace=.20)
    fig.suptitle(title,x=.025,y=.99,ha="left",fontsize=19)
    fig.text(.025,.93,"赤＝POSTが増える、青＝減る。数字は同じseed同士の差を平均した値（percentage points）。",fontsize=10)
    fig.text(.025,.889,"小さい注記は、POSTが増えたseed数 / ５。候補範囲や保持方法も含むFeed方式全体の比較。",fontsize=10,color="#667481")
    for ax,feed in zip(axes,["chrono","trend"]):
        vals=np.zeros((5,3)); counts=np.zeros((5,3),dtype=int)
        for y,tier in enumerate(TIERS):
            for x,group in enumerate(XGROUPS):
                rows=[r for r in raw if r["feed"]==feed and r["tier"]==tier and r["x_group"]==group
                      and r["cutoffs"]=="thirds" and r["signed"]=="False"]
                assert len(rows)==5
                ds=np.array([float(r["share_post"])*100 for r in rows]); vals[y,x]=ds.mean(); counts[y,x]=(ds>0).sum()
        im=ax.imshow(vals,vmin=-60,vmax=60,cmap="RdBu_r",aspect="auto")
        for y in range(5):
            for x in range(3):
                color="white" if abs(vals[y,x])>37 else INK
                ax.text(x,y-.11,f"{vals[y,x]:+.1f} pp",ha="center",va="center",fontsize=12,color=color)
                ax.text(x,y+.20,f"増加 {counts[y,x]}/5 seed",ha="center",va="center",fontsize=8,color=color)
        ax.set_xticks(range(3),XLABELS); ax.set_yticks(range(5),TLABELS); ax.tick_params(length=0)
        ax.set_title(NAMES[feed].replace(" 100%","")+" − For You",pad=12)
    axes[0].set_ylabel("フォロワー数",labelpad=12)
    cax=fig.add_axes([.92,.15,.018,.64]); cb=fig.colorbar(im,cax=cax,ticks=[-60,-30,0,30,60])
    cb.set_label("POST選択率の変化 (pp)")
    finish(fig,"04_paired_post_differences",title,
           "同じseed・同じ階層・同じX帯でのPOST選択率の差。色の尺度は両パネル共通の−60〜+60pp。小注記は差が正だったseed数。")


def gallery():
    start,end="<!-- feed-role-figures:start -->","<!-- feed-role-figures:end -->"
    lines=[start,"## 図で確認する","",
           "青＝POST、橙＝LIKE、緑＝RESHARE。平均とseed別の変動を分けて確認する。","",
           "中央帯：|X|<1/3、中間帯：1/3≤|X|<2/3、端：|X|≥2/3。"," "]
    local=["# Feed比較の図","",FOOT," "]
    for f in FIGURES:
        stem,title,caption=f["stem"],f["title"],f["caption"]
        rel=f"figures/{OUT.name}/{stem}"
        lines += [f"### {title}","",f"![{title}]({rel}.png)","",caption,"",
                  f"[SVG]({rel}.svg) · [PDF]({rel}.pdf)",""]
        local += [f"## {title}","",f"![{title}]({stem}.png)","",caption,"",
                  f"[SVG]({stem}.svg) · [PDF]({stem}.pdf)",""]
    lines += [end,""]
    text=REPORT.read_text()
    if start in text:
        before,rest=text.split(start,1); _,after=rest.split(end,1)
        text=before+"\n".join(lines)+after.lstrip("\n")
    else:
        marker="## 結果の解釈"
        assert marker in text
        text=text.replace(marker,"\n".join(lines)+"\n"+marker,1)
    REPORT.write_text(text)
    local += ["## 再生成","","`PYENV_VERSION=3.11.9 python scripts/plot_feed_role_comparison.py`",""]
    (OUT/"README.md").write_text("\n".join(local))
    manifest={"figures":FIGURES,"sources":{p.name:hashlib.sha256(p.read_bytes()).hexdigest()
              for p in [DATA/"cells_aggregate.json",DATA/"cells.csv",DATA/"paired_cells.csv"]},
              "matplotlib":matplotlib.__version__,"seeds":list(range(5)),"tail_steps":[15001,20000]}
    (OUT/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2))


def main():
    setup()
    rows=load_json("cells_aggregate.json")
    overview(rows); stacked_by_x(rows); heatmaps(rows); seed_lines(load_csv("cells.csv")); differences(load_csv("paired_cells.csv"))
    gallery()
    print(f"Saved {len(FIGURES)} figures in PNG / SVG / PDF:",OUT)


if __name__=="__main__":
    main()
