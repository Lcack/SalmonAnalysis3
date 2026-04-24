let salmonData = {
    boss: [],
    stage: [],
    weapon: [],
    history: [],
    customScores: {} 
};

// 1. 初始化加载所有数据
async function init() {
    try {
        // 并行加载所有 JSON 文件
        const [boss, stage, weapon, history] = await Promise.all([
            fetch('./data/boss_data.json').then(res => res.json()),
            fetch('./data/stage_data.json').then(res => res.json()),
            fetch('./data/weapon_data.json').then(res => res.json()),
            fetch('./data/coop_schedule.json').then(res => res.json())
        ]);

        salmonData.boss = Object.values(boss.boss);
        salmonData.stage = Object.values(stage.stage);
        salmonData.weapon = Object.values(weapon.weapon);
        salmonData.history = history;

        const savedScores = localStorage.getItem('splatoon_custom_scores');
        if (savedScores) {
            salmonData.customScores = JSON.parse(savedScores);
        }

        console.log("数据加载成功！", salmonData);

        // 数据加载完后，渲染首页
        renderHome();
        
    } catch (error) {
        console.error("加载数据失败，请检查文件名和路径:", error);
        alert("JSON 数据加载失败，请查看控制台。");
    }
}

// 2. 页面切换逻辑
function showPage(pageId) {
    document.querySelectorAll('.page-content').forEach(p => p.style.display = 'none');
    document.getElementById(pageId).style.display = 'block';
    
    // 切换页面时，如果是历史记录页或统计页，可以触发重新渲染
    if (pageId === 'history') renderHistory();
    if (pageId === 'weapon') renderWeapons();
}

// 启动
window.onload = init;