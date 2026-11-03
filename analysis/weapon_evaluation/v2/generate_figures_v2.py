import json,pathlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE=pathlib.Path(__file__).resolve().parent;OUT=HERE/'figures'
OUT.mkdir(parents=True,exist_ok=True)
data=json.loads((HERE/'evaluation.json').read_text(encoding='utf8'));rows=data['weapons'];AX=list(rows[0]['scores'])
CN=['击杀能力','极限射程','涂地涂墙','墨水效率','清杂能力','射击硬直']
FAMILY={'Shooter':'射击枪','Blaster':'爆破枪','Brush':'笔','Charger':'蓄力狙击枪','Maneuver':'机动枪','Roller':'滚筒','Saber':'刮水刀','Shelter':'防空伞','Slosher':'泼桶','Spinner':'旋转枪','Stringer':'猎鱼弓','Bear':'熊武器'}
fp=pathlib.Path('C:/Windows/Fonts/msyh.ttc');font_manager.fontManager.addfont(str(fp))
plt.rcParams.update({'font.family':font_manager.FontProperties(fname=str(fp)).get_name(),'axes.unicode_minus':False,'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'savefig.facecolor':'white'})
COL=['#007C91','#E37339','#6D5C97','#48956C','#AD5673','#426CB0','#8D856A']

def save(fig,name):fig.savefig(OUT/name,dpi=170,bbox_inches='tight');plt.close(fig)
def get(wid):return next(r for r in rows if r['id']==wid)

def heat(rs,name,title,height=None):
    fig,ax=plt.subplots(figsize=(12,height or max(4.7,len(rs)*.38)))
    arr=np.array([[r['scores'][a] for a in AX] for r in rs]);im=ax.imshow(arr,vmin=.5,vmax=5,cmap='YlGnBu',aspect='auto')
    ax.set_xticks(range(6),CN);ax.set_yticks(range(len(rs)),[r['name'] for r in rs]);ax.tick_params(length=0)
    for i in range(len(rs)):
        for j in range(6):ax.text(j,i,f'{arr[i,j]:.1f}',ha='center',va='center',color='white' if arr[i,j]>3.4 else '#152B3C',fontsize=10)
    ax.set_title(title+'\n全部评分高分更优  硬直越短得分越高  默认熟练玩家墙地同效',pad=16)
    fig.colorbar(im,ax=ax,label='模型分数  0.5–5.0',fraction=.025,pad=.025);save(fig,name)

ordered=sorted(rows,key=lambda r:(r['is_bear'],r['family'],r['id']))
heat(ordered[:36],'overview_heatmap_1.png','六维定义修订后的全武器总览  上半',12)
heat(ordered[36:],'overview_heatmap_2.png','六维定义修订后的全武器总览  下半',12)
for f,cn in FAMILY.items():
    rs=[r for r in rows if (r['is_bear'] if f=='Bear' else r['family']==f and not r['is_bear'])]
    heat(rs,f'family_{f}.png',cn+'同类横评')

fig,axes=plt.subplots(1,2,figsize=(15,6))
for ax,(x,y) in zip(axes,[('Killing','Ink Efficiency'),('Inking','Mob Clearing')]):
    for f,cn in FAMILY.items():
        if f=='Bear':continue
        rs=[r for r in rows if r['family']==f and not r['is_bear']]
        ax.scatter([r['scores'][x] for r in rs],[r['scores'][y] for r in rs],s=45,alpha=.75,label=cn)
    for wid in ['Roller_Heavy_Coop','Shooter_Short_Coop','Charger_Long_Coop','Stringer_Explosion_Coop']:
        r=get(wid);ax.annotate(r['name'],(r['scores'][x],r['scores'][y]),xytext=(4,4),textcoords='offset points',fontsize=8)
    ax.set(xlabel=CN[AX.index(x)]+'分数',ylabel=CN[AX.index(y)]+'分数',xlim=(.2,5.4),ylim=(.2,5.4));ax.grid(alpha=.2)
axes[1].legend(bbox_to_anchor=(1.02,1),loc='upper left',fontsize=9)
fig.suptitle('63把常规武器的六维能力组合',fontsize=16);fig.tight_layout();save(fig,'tradeoffs.png')

fig,axes=plt.subplots(1,3,figsize=(16,5.5))
selected=[get(x) for x in ['Stringer_Explosion_Coop','Stringer_Normal_Coop','Stringer_Short_Coop']]
for ax,factor,axis,title in zip(axes[:2],['hit_rate','wall_factor'],['Killing','Inking'],['箭束汇聚率与击杀评分','爆破涂墨可选折扣与评分']):
    chosen=selected if factor=='hit_rate' else [get(wid) for wid in ['Blaster_Middle_Coop','Blaster_LightShort_Coop','Blaster_Bear_Coop']]
    for r in chosen:
        ss=sorted([s for s in data['sensitivity'] if s['id']==r['id'] and s['factor']==factor],key=lambda s:s['value'])
        ax.plot([s['value'] for s in ss],[s['scores'][axis] for s in ss],marker='o',label=r['name'])
    ax.set_title(title);ax.set_xlabel('有效命中比例' if factor=='hit_rate' else '可选涂墨折扣  默认1.0');ax.set_ylim(0,5.3);ax.grid(alpha=.2);ax.legend(fontsize=8)
for wid in ['Shooter_Normal_Coop','Charger_Normal_Coop','Roller_Heavy_Coop','Stringer_Normal_Coop']:
    r=get(wid);axes[2].plot(range(3),[s['score'] for s in r['overall']['scenarios']],marker='o',label=r['name'])
axes[2].set_xticks(range(3),['均衡','战斗偏重','环境偏重']);axes[2].set_title('工作量情景与候选总分');axes[2].set_ylim(0,5.3);axes[2].grid(alpha=.2);axes[2].legend(fontsize=8)
for ax in axes:ax.set_ylabel('固定基准下的模型分数')
fig.suptitle('实验条件对评分的影响',fontsize=16);fig.tight_layout();save(fig,'sensitivity.png')

fig,axes=plt.subplots(1,3,figsize=(16,5.5))
for ax,r in zip(axes,selected):
    inds=[i for i,m in enumerate(r['modes']) if not m.get('aoe_projectiles')]
    ds=[r['modes'][i]['damage'] for i in inds]
    times=[sum(c['alternatives'][i]['frames'] for c in r['benchmarks']['boss']['cases']) for i in inds]
    xx=np.arange(len(inds));ax.bar(xx-.17,ds,.34,color=COL[0]);ax.set_ylabel('全箭命中单次伤害');ax.set_ylim(0,650)
    ax.set_xticks(xx,[r['modes'][i]['name'] for i in inds]);ax.set_title(r['name']);right=ax.twinx();right.plot(xx,times,color=COL[1],marker='o');right.set_ylim(0,1800);right.set_ylabel('五类生命值靶总帧')
    for j,v in enumerate(ds):ax.text(j-.17,v+8,f'{v:g}',ha='center',fontsize=10)
fig.suptitle('三把常规弓  单次最大伤害与五血量基准并非同一个指标',fontsize=16);fig.tight_layout();save(fig,'stringer_modes.png')

rs=sorted(rows,key=lambda r:abs(r['scores']['Killing']-r['previous_scores']['Killing']),reverse=True)[:18]
fig,ax=plt.subplots(figsize=(12,8));yy=np.arange(len(rs))
for y,r in zip(yy,rs):ax.plot([r['previous_scores']['Killing'],r['scores']['Killing']],[y,y],color='#B9C7CC')
ax.scatter([r['previous_scores']['Killing'] for r in rs],yy,color='#999999',label='旧400血基准');ax.scatter([r['scores']['Killing'] for r in rs],yy,color=COL[0],label='新五血量基准')
ax.set_yticks(yy,[r['name'] for r in rs]);ax.invert_yaxis();ax.set_xlim(0,5.3);ax.grid(axis='x',alpha=.2);ax.legend();ax.set_xlabel('击杀能力分数');ax.set_title('击杀定义改变后的分数差异  展示绝对变化较大的18把');save(fig,'killing_changes.png')

rs=sorted(rows,key=lambda r:abs(r['overall']['recommended']-r['overall']['original']),reverse=True)[:16]
fig,ax=plt.subplots(figsize=(12,7.8));yy=np.arange(len(rs))
for y,r in zip(yy,rs):
    low,high=r['overall']['range'];ax.plot([low,high],[y,y],color=COL[0],lw=4,alpha=.5)
ax.scatter([r['overall']['original'] for r in rs],yy,label='原人工总分',color='#999999',s=38)
ax.scatter([r['overall']['recommended'] for r in rs],yy,label='三情景模型均值',color=COL[0],s=38)
ax.set_yticks(yy,[r['name'] for r in rs]);ax.invert_yaxis();ax.set_xlim(0,5.3);ax.grid(axis='x',alpha=.2);ax.legend();ax.set_xlabel('总分  线段表示三情景范围');ax.set_title('工作量情景下的综合评分比较');save(fig,'overall_changes.png')

rs=[get(x) for x in ['Shooter_Normal_Coop','Charger_Long_Coop','Roller_Heavy_Coop','Stringer_Normal_Coop','Charger_Bear_Coop','Saber_Bear_Coop']]
keys=['boss','mob','ground','wall','extra_refill','release','approach'];labels=['五血量战斗','混合杂鱼','涂地','涂墙','额外补墨','射击后潜墨','接敌位移']
fig,ax=plt.subplots(figsize=(13,6));left=np.zeros(len(rs))
for i,(k,lab) in enumerate(zip(keys,labels)):
    vals=np.array([r['overall']['scenarios'][0]['components_frames'][k]/60 for r in rs]);ax.barh(range(len(rs)),vals,left=left,label=lab,color=COL[i]);left+=vals
ax.set_yticks(range(len(rs)),[r['name'] for r in rs]);ax.invert_yaxis();ax.set_xlabel('均衡工作量情景的串行完成时间  秒');ax.set_title('六维的相互作用通过任务时间与共享墨量进入总分');ax.legend(bbox_to_anchor=(1.02,1),loc='upper left',fontsize=9);save(fig,'interaction_components.png')
print('figure files',len(list(OUT.glob('*.png'))))
