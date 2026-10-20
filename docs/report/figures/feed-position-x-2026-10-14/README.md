# Feed比較の図

η=0.03・k=20・rewire off｜seed 0〜4｜末尾5,000 step｜セル内は個人を等重み、seed間も等重み
 
## 1 | Action choice by follower group

![1 | Action choice by follower group](01_roles_by_followers.png)

Five-seed mean action shares, pooling X groups. Row labels also give each follower group's share of the whole population (agent counts, not action counts).

[SVG](01_roles_by_followers.svg) · [PDF](01_roles_by_followers.pdf)

## 1b | Action choice by feed, X group, and follower count

![1b | Action choice by feed, X group, and follower count](05_stacked_roles_by_x.png)

Columns are feed modes; rows are Neutral, Moderate, and Extreme. Within each panel, contiguous bars show the five follower groups. Blue = POST, orange = LIKE, green = RESHARE. Population labels are joint X × follower-group shares of the whole population, not percentages within the X group.

[SVG](05_stacked_roles_by_x.svg) · [PDF](05_stacked_roles_by_x.pdf)

## 2 | Action shares by X group and follower count

![2 | Action shares by X group and follower count](02_position_x_action_heatmaps.png)

Rows are follower-count groups; columns are Neutral, Moderate, and Extreme X groups. POST, LIKE, and RESHARE have separate panels with fixed 0–100% scales.

[SVG](02_position_x_action_heatmaps.svg) · [PDF](02_position_x_action_heatmaps.pdf)

## 3｜XによるPOSTの違いは、seedごとに再現するか

![3｜XによるPOSTの違いは、seedごとに再現するか](03_x_effect_seed_variation.png)

seedの線は同じseed内のX帯間の比較。誤差帯や信頼区間ではなく、５本の実測runとその平均を示す。

[SVG](03_x_effect_seed_variation.svg) · [PDF](03_x_effect_seed_variation.pdf)

## 4｜For Youから切り替えると、POSTは何ポイント変わるか

![4｜For Youから切り替えると、POSTは何ポイント変わるか](04_paired_post_differences.png)

同じseed・同じ階層・同じX帯でのPOST選択率の差。色の尺度は両パネル共通の−60〜+60pp。小注記は差が正だったseed数。

[SVG](04_paired_post_differences.svg) · [PDF](04_paired_post_differences.pdf)

## 再生成

`PYENV_VERSION=3.11.9 python scripts/plot_feed_role_comparison.py`
