"""Chinese static figures from the saved, auditable evaluation artifact."""
import json, pathlib, math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE=pathlib.Path(__file__).resolve().parent
data=json.loads((HERE/'evaluation.json').read_text(encoding='utf8'))
rows=data['weapons'];AX=data['weapons'][0]['scores'].keys()
AX=list(AX); CN=['大鲑鱼击杀','攻击范围','涂墨能力','墨水效率','清杂能力','动作灵活']
FAMILY={'Shooter':'射击枪','Blaster':'爆破枪','Brush':'笔','Charger':'蓄力狙击枪','Maneuver':'机动枪','Roller':'滚筒','Saber':'刮水刀','Shelter':'防空伞','Slosher':'泼桶','Spinner':'旋转枪','Stringer':'猎鱼弓','Bear':'熊武器'}
fontpath=pathlib.Path('C:/Windows/Fonts/msyh.ttc')
font_manager.fontManager.addfont(str(fontpath))
plt.rcParams.update({'font.family':font_manager.FontProperties(fname=str(fontpath)).get_name(),'axes.unicode_minus':False,'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'savefig.facecolor':'white'})
OUT=HERE/'figures';OUT.mkdir(exist_ok=True)
palette=['#007C91','#E37339','#6D5C97','#48956C','#AD5673','#426CB0']

def save(fig,name):
    fig.savefig(OUT/name,dpi=170,bbox_inches='tight');plt.close(fig)

def heat(rs,name,title,height=None):
    fig,ax=plt.subplots(figsize=(12,height or max(5,len(rs)*.29)))
    arr=np.array([[r['scores'][a] for a in AX] for r in rs])
    im=ax.imshow(arr,vmin=.5,vmax=5,cmap='YlGnBu',aspect='auto')
    ax.set_xticks(range(6),CN);ax.set_yticks(range(len(rs)),[r['name'] for r in rs]);ax.tick_params(length=0)
    for i in range(len(rs)):
        for j in range(6):ax.text(j,i,f'{arr[i,j]:.1f}',ha='center',va='center',color='white' if arr[i,j]>3.4 else '#152B3C',fontsize=9)
    ax.set_title(title+'\n模型分数越高越强  每轴允许采用不同动作',pad=16)
    fig.colorbar(im,ax=ax,label='模型分数  0.5–5.0',fraction=.025,pad=.025)
    save(fig,name)

ordered=sorted(rows,key=lambda r:(r['is_bear'],r['family'],r['id']))
heat(ordered,'overview_heatmap.png','71把武器六维总览')
heat(ordered[:36],'overview_heatmap_1.png','全武器六维总览  上半',12)
heat(ordered[36:],'overview_heatmap_2.png','全武器六维总览  下半',12)

for f,cn in FAMILY.items():
    rs=[r for r in rows if (r['is_bear'] if f=='Bear' else r['family']==f and not r['is_bear'])]
    heat(rs,f'family_{f}.png',cn+'同类横评',max(4.7,len(rs)*.38))

fig,axes=plt.subplots(1,2,figsize=(15,6))
for ax,(x,y) in zip(axes,[('Killing','Ink Efficiency'),('Inking','Mob Clearing')]):
    for f in FAMILY:
        if f=='Bear':continue
        rs=[r for r in rows if r['family']==f and not r['is_bear']]
        ax.scatter([r['scores'][x] for r in rs],[r['scores'][y] for r in rs],s=45,alpha=.7,label=FAMILY[f])
    for wid in ['Roller_Heavy_Coop','Shooter_Short_Coop','Charger_Long_Coop','Stringer_Explosion_Coop','Slosher_Diffusion_Coop']:
        r=next(r for r in rows if r['id']==wid);ax.annotate(r['name'],(r['scores'][x],r['scores'][y]),xytext=(4,4),textcoords='offset points',fontsize=8)
    ax.set(xlabel=CN[AX.index(x)]+'模型分数',ylabel=CN[AX.index(y)]+'模型分数',xlim=(.2,5.4),ylim=(.2,5.4));ax.grid(alpha=.2)
axes[1].legend(bbox_to_anchor=(1.02,1),loc='upper left',fontsize=9)
fig.suptitle('跨类别比较  单一维度优势不会自动转化为其他维度优势',fontsize=16)
fig.tight_layout();save(fig,'tradeoffs.png')

fig,axes=plt.subplots(1,3,figsize=(16,5.5))
for ax,factor,axis,title in zip(axes,['hit_rate','density','paint_overlap'],['Killing','Mob Clearing','Inking'],['箭束汇聚率对击杀评分','敌群密度对清杂评分','涂墨重叠系数对评分']):
    selected=[r for r in rows if (r['family']=='Stringer' and not r['is_bear'])] if factor=='hit_rate' else [next(r for r in rows if r['id']==wid) for wid in (['Shooter_Normal_Coop','Blaster_Middle_Coop','Brush_Normal_Coop','Charger_Normal_Coop'] if factor=='density' else ['Shooter_Normal_Coop','Roller_Normal_Coop','Stringer_Normal_Coop','Slosher_Washtub_Coop'])]
    for r in selected:
        vals=sorted([s for s in data['sensitivity'] if s['id']==r['id'] and s['factor']==factor],key=lambda s:s['value'])
        ax.plot([s['value'] for s in vals],[s['scores'][axis] for s in vals],marker='o',label=r['name'])
    ax.set_title(title);ax.set_xlabel({'hit_rate':'箭束有效命中比例','density':'每平方游戏单位的目标密度','paint_overlap':'有效涂墨比例'}[factor]);ax.set_ylabel('固定标尺下的模型分数');ax.set_ylim(0,5.4);ax.grid(alpha=.2);ax.legend(fontsize=8)
fig.suptitle('单因素敏感性分析  曲线范围不是统计置信区间',fontsize=16)
fig.tight_layout();save(fig,'sensitivity.png')

rs=[r for r in rows if r['family']=='Stringer' and not r['is_bear']]
fig,axes=plt.subplots(1,3,figsize=(16,5.2))
for ax,r in zip(axes,rs):
    pairs=[(m,mm) for m,mm in zip(r['modes'],r['mode_metrics']) if not m.get('aoe_projectiles')]
    x=np.arange(len(pairs));d=[m['damage'] for m,mm in pairs];t=[mm['cohock_cold_s'] for m,mm in pairs]
    ax.bar(x-.17,d,.34,color=palette[0],label='全箭命中伤害');ax.set_ylabel('单次伤害  游戏点数');ax.set_xticks(x,[m['name'] for m,mm in pairs]);ax.set_title(r['name']);ax2=ax.twinx();ax2.plot(x,t,color=palette[1],marker='o',label='400血目标击杀时间');ax2.set_ylabel('模型击杀时间  秒');ax.set_ylim(0,650)
    ax2.set_ylim(0,1.6)
    for i,v in enumerate(d):ax.text(i-.17,v+9,f'{v:g}',ha='center',fontsize=10)
    if ax==axes[0]:ax.legend(loc='upper left',fontsize=8);ax2.legend(loc='upper center',fontsize=8)
fig.suptitle('三把常规弓的动作比较  点射 一段蓄力 满蓄力',fontsize=16)
fig.tight_layout();save(fig,'stringer_modes.png')

fig,ax=plt.subplots(figsize=(15,4.2));ax.set_axis_off()
steps=[('原始参数','普通文件加Coop覆盖\n保留熊武器独立参数'),('动作适配','区分蓄力 翻滚 滚动\n解析上限与伤害分组'),('场景计算','400血击杀与整箱墨\n涂墨 群攻 动作代理'),('标尺与复核','63把常规武器定标\n敏感性分析与来源追踪'),('产品写回','71把六维数字评分\n报告 CSV 可复算脚本')]
for i,(title,desc) in enumerate(steps):
    x=.015+i*.2;ax.add_patch(plt.Rectangle((x,.25),.17,.52,facecolor='#EEF5F8',edgecolor='#9AB3C0',linewidth=1))
    ax.text(x+.085,.64,title,ha='center',va='center',fontsize=14,weight='bold');ax.text(x+.085,.45,desc,ha='center',va='center',fontsize=10)
    if i<4:ax.annotate('',xy=(x+.195,.51),xytext=(x+.174,.51),arrowprops=dict(arrowstyle='->',color='#496C7E',lw=1.5))
ax.set_title('从参数到六维评分的可复算流程',fontsize=17,pad=12);save(fig,'flow_model.png')
print('figures',len(list(OUT.glob('*.png'))))
