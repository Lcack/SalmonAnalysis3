/**
 * SalmonAnalysis3 - 主应用逻辑
 * Splatoon3 打工分析工具
 */

// ================================
// 全局数据存储
// ================================
const AppData = {
    weapons: {},        // 武器数据 (id -> weapon object)
    stages: {},         // 场地数据 (id -> stage object)
    bosses: {},         // Boss数据 (id -> boss object)
    schedules: [],      // 所有打工场次
    bigRuns: [],        // Big Run 历史
    eggstraWorks: [],   // Eggstra Work 历史
    customScores: null, // 用户自定义评分
    
    // 运行时缓存
    currentSchedule: null,   // 当前进行中的场次
    futureSchedules: [],     // 未来4场
    
    // 武器名称到ID的映射（用于匹配）
    weaponNameMap: new Map()
};

// ================================
// 初始化
// ================================
document.addEventListener('DOMContentLoaded', init);

async function init() {
    console.log('🐟 SalmonAnalysis3 初始化中...');
    
    try {
        // 并行加载所有数据
        await loadAllData();
        
        // 加载用户自定义评分
        loadCustomScores();
        
        // 计算当前和未来场次
        calculateSchedules();
        
        // 初始化筛选器选项
        initFilters();
        
        // 隐藏加载动画
        hideLoading();
        
        // 渲染首页
        renderHome();
        
        console.log('✅ 初始化完成！');
        console.log('数据概览:', {
            武器数: Object.keys(AppData.weapons).length,
            场地数: Object.keys(AppData.stages).length,
            Boss数: Object.keys(AppData.bosses).length,
            总场次数: AppData.schedules.length,
            BigRun数: AppData.bigRuns.length,
            EggstraWork数: AppData.eggstraWorks.length
        });
        
    } catch (error) {
        console.error('❌ 初始化失败:', error);
        showError('数据加载失败，请检查控制台获取详情');
    }
}

// ================================
// 数据加载
// ================================
async function loadAllData() {
    const [weaponsRes, stagesRes, bossesRes, schedulesRes, bigRunRes, eggstraRes] = await Promise.all([
        fetch('./data/weapon_data.json'),
        fetch('./data/stage_data.json'),
        fetch('./data/boss_data.json'),
        fetch('./data/coop_schedule.json'),
        fetch('./data/history_bigrun.json'),
        fetch('./data/history_EggstraWork.json')
    ]);
    
    // 检查响应状态
    const responses = [weaponsRes, stagesRes, bossesRes, schedulesRes, bigRunRes, eggstraRes];
    const names = ['weapon_data.json', 'stage_data.json', 'boss_data.json', 'coop_schedule.json', 'history_bigrun.json', 'history_EggstraWork.json'];
    
    responses.forEach((res, i) => {
        if (!res.ok) throw new Error(`加载 ${names[i]} 失败: ${res.status}`);
    });
    
    // 解析JSON
    const [weaponsJson, stagesJson, bossesJson, schedulesJson, bigRunJson, eggstraJson] = await Promise.all([
        weaponsRes.json(),
        stagesRes.json(),
        bossesRes.json(),
        schedulesRes.json(),
        bigRunRes.json(),
        eggstraRes.json()
    ]);
    
    // 存储数据
    AppData.weapons = weaponsJson.weapon || {};
    AppData.stages = stagesJson.stage || {};
    AppData.bosses = bossesJson.boss || {};
    AppData.schedules = schedulesJson.schedule || [];
    AppData.bigRuns = bigRunJson.bigrun || [];
    AppData.eggstraWorks = eggstraJson.eggstrawork || [];
    
    // 构建武器名称映射
    buildWeaponNameMap();
}

function buildWeaponNameMap() {
    // 建立武器中文名到武器对象的映射
    Object.values(AppData.weapons).forEach(weapon => {
        if (weapon.name_zh) {
            AppData.weaponNameMap.set(weapon.name_zh, weapon);
        }
        if (weapon.name_en) {
            AppData.weaponNameMap.set(weapon.name_en, weapon);
        }
        if (weapon.name_jp) {
            AppData.weaponNameMap.set(weapon.name_jp, weapon);
        }
    });
}

function loadCustomScores() {
    try {
        const saved = localStorage.getItem('salmon_custom_scores');
        if (saved) {
            AppData.customScores = JSON.parse(saved);
            console.log('✅ 已加载用户自定义评分');
            
            // 应用自定义评分到武器数据
            applyCustomScores();
        }
    } catch (e) {
        console.warn('加载自定义评分失败:', e);
    }
}

function applyCustomScores() {
    if (!AppData.customScores) return;
    
    Object.entries(AppData.customScores).forEach(([weaponId, rating]) => {
        if (AppData.weapons[weaponId]) {
            AppData.weapons[weaponId].rating = rating;
        }
    });
}

// ================================
// 时间计算逻辑
// ================================
function calculateSchedules() {
    const now = new Date();
    
    // 将 schedule 的时间字符串转换为 Date 对象
    const parsedSchedules = AppData.schedules.map(s => {
        return {
            ...s,
            startTime: parseTimeString(s.Start_time),
            endTime: parseTimeString(s.End_time),
            isBigRun: s.Is_Big_Run === 'true'
        };
    });
    
    // 找到当前进行中的场次
    AppData.currentSchedule = parsedSchedules.find(s => 
        s.startTime <= now && s.endTime > now
    );
    
    // 找到未来4场
    AppData.futureSchedules = parsedSchedules
        .filter(s => s.startTime > now)
        .slice(0, 4);
    
    // 保存解析后的数据
    AppData.schedules = parsedSchedules;
}

function parseTimeString(timeStr) {
    // 格式: "2022/09/08 23:00"
    if (!timeStr) return null;
    return new Date(timeStr.replace(/\//g, '-'));
}

function formatDateTime(date) {
    if (!date) return '-';
    const d = new Date(date);
    return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function formatDuration(hours) {
    if (!hours) return '-';
    const h = parseInt(hours);
    return h >= 24 ? `${Math.floor(h/24)}天${h%24}小时` : `${h}小时`;
}

// ================================
// 页面切换
// ================================
function showPage(pageId) {
    // 隐藏所有页面
    document.querySelectorAll('.page-content').forEach(page => {
        page.style.display = 'none';
    });
    
    // 显示目标页面
    const targetPage = document.getElementById(pageId);
    if (targetPage) {
        targetPage.style.display = 'block';
    }
    
    // 更新导航状态
    document.querySelectorAll('.nav-links li').forEach(li => {
        li.classList.remove('active');
        if (li.dataset.page === pageId) {
            li.classList.add('active');
        }
    });
    
    // 触发页面渲染
    switch(pageId) {
        case 'home':
            renderHome();
            break;
        case 'history':
            renderHistory();
            break;
        case 'stats':
            renderStats();
            break;
        case 'weapons':
            renderWeapons();
            break;
    }
    
    // 滚动到顶部
    window.scrollTo(0, 0);
}

// ================================
// 首页渲染
// ================================
let currentScheduleTimer = null;
let futureScheduleTimer = null;

function renderHome() {
    renderCurrentSchedule();
    renderFutureSchedules();
}

function startCurrentScheduleTimer(endTime) {
    // 清除之前的定时器
    if (currentScheduleTimer) {
        clearInterval(currentScheduleTimer);
    }

    function updateTimer() {
        const now = new Date();
        const diff = endTime - now;

        if (diff <= 0) {
            document.getElementById('countdown-timer').textContent = '已结束';
            clearInterval(currentScheduleTimer);
            return;
        }

        const hours = Math.floor(diff / (1000 * 60 * 60));
        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((diff % (1000 * 60)) / 1000);

        document.getElementById('countdown-timer').textContent =
            `还剩${hours}小时${minutes}分${seconds}秒`;
    }

    updateTimer();
    currentScheduleTimer = setInterval(updateTimer, 1000);
}

function startFutureScheduleTimer(schedules) {
    // 清除之前的定时器
    if (futureScheduleTimer) {
        clearInterval(futureScheduleTimer);
    }

    function updateTimers() {
        const now = new Date();
        schedules.forEach((s, index) => {
            const timerEl = document.getElementById(`future-timer-${index}`);
            if (!timerEl) return;

            const diff = s.startTime - now;

            if (diff <= 0) {
                timerEl.textContent = '已开始';
                return;
            }

            const days = Math.floor(diff / (1000 * 60 * 60 * 24));
            const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

            if (days > 0) {
                timerEl.textContent = `${days}天${hours}小时${minutes}分钟后`;
            } else {
                timerEl.textContent = `${hours}小时${minutes}分钟后`;
            }
        });
    }

    updateTimers();
    futureScheduleTimer = setInterval(updateTimers, 60000); // 每分钟更新一次
}

// 页面切换时清理定时器
function showPage(pageId) {
    // 清理首页定时器
    if (pageId !== 'home') {
        if (currentScheduleTimer) {
            clearInterval(currentScheduleTimer);
            currentScheduleTimer = null;
        }
        if (futureScheduleTimer) {
            clearInterval(futureScheduleTimer);
            futureScheduleTimer = null;
        }
    }

    // 隐藏所有页面
    document.querySelectorAll('.page-content').forEach(page => {
        page.style.display = 'none';
    });

    // 显示目标页面
    const targetPage = document.getElementById(pageId);
    if (targetPage) {
        targetPage.style.display = 'block';
    }

    // 更新导航状态
    document.querySelectorAll('.nav-links li').forEach(li => {
        li.classList.remove('active');
        if (li.dataset.page === pageId) {
            li.classList.add('active');
        }
    });

    // 触发页面渲染
    switch(pageId) {
        case 'home':
            renderHome();
            break;
        case 'history':
            renderHistory();
            break;
        case 'stats':
            renderStats();
            break;
        case 'weapons':
            renderWeapons();
            break;
    }

    // 滚动到顶部
    window.scrollTo(0, 0);
}

function getStageByName(stageName) {
    return Object.values(AppData.stages).find(s =>
        s.name_zh === stageName || s.name_en === stageName || s.id === stageName
    );
}

function generateRadarChart(weapons) {
    const size = 80;
    const center = size / 2;
    const maxRadius = size * 0.4;
    const ratings = weapons.map(w => w?.rating?.overall || 0);

    // 四个角的坐标 (左上, 右上, 右下, 左下)
    const corners = [
        { x: center - maxRadius, y: center - maxRadius }, // 左上
        { x: center + maxRadius, y: center - maxRadius }, // 右上
        { x: center + maxRadius, y: center + maxRadius }, // 右下
        { x: center - maxRadius, y: center + maxRadius }  // 左下
    ];

    // 生成网格线 (5层)
    let gridLines = '';
    for (let i = 1; i <= 5; i++) {
        const r = (maxRadius * i) / 5;
        const points = corners.map(c => {
            const dx = c.x - center;
            const dy = c.y - center;
            return `${center + dx * i / 5},${center + dy * i / 5}`;
        }).join(' ');
        gridLines += `<polygon points="${points}" fill="none" stroke="#ddd" stroke-width="0.5"/>`;
    }

    // 生成对角线
    const diagonals = `
        <line x1="${center - maxRadius}" y1="${center - maxRadius}" x2="${center + maxRadius}" y2="${center + maxRadius}" stroke="#ddd" stroke-width="0.5"/>
        <line x1="${center + maxRadius}" y1="${center - maxRadius}" x2="${center - maxRadius}" y2="${center + maxRadius}" stroke="#ddd" stroke-width="0.5"/>
    `;

    // 生成数据多边形
    let dataPoints = '';
    if (ratings.length > 0) {
        const polygonPoints = ratings.slice(0, 4).map((rating, i) => {
            const normalizedRating = Math.min(Math.max(rating / 5, 0), 1);
            const corner = corners[i];
            const dx = corner.x - center;
            const dy = corner.y - center;
            return `${center + dx * normalizedRating},${center + dy * normalizedRating}`;
        }).join(' ');
        dataPoints = `<polygon points="${polygonPoints}" fill="rgba(139, 92, 246, 0.5)" stroke="#8B5CF6" stroke-width="1.5"/>`;
    }

    return `
        <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" class="radar-chart">
            <rect width="100%" height="100%" fill="white"/>
            ${gridLines}
            ${diagonals}
            ${dataPoints}
        </svg>
    `;
}

function renderCurrentSchedule() {
    const container = document.getElementById('current-schedule');
    if (!container) return;

    if (!AppData.currentSchedule) {
        container.innerHTML = '<div class="schedule-card"><p>当前没有进行中的打工场次</p></div>';
        return;
    }

    const s = AppData.currentSchedule;
    const weapons = getWeaponsForSchedule(s);
    const rating = calculateScheduleRating(weapons);

    // 格式化评分显示
    const ratingDisplay = rating === null ? '?' : (rating.toFixed(1) + '/10');
    const ratingClass = getRatingClass(rating === null ? 5 : rating / 2); // ?使用最高配色

    // 获取boss图片
    const bossImage = getBossImage(s.King_Salmonid);

    // 获取场地Banner图片
    const stage = getStageByName(s.Stage);
    const bannerImage = stage?.imageBanner || null;

    // 计算持续时间（小时）
    const durationHours = s.Duration ? parseInt(s.Duration) : 0;

    container.innerHTML = `
        <div class="schedule-card current" ${bannerImage ? `style="background-image: url('${bannerImage}'); background-size: cover; background-position: center;"` : ''}>
            <div class="current-schedule-overlay">
                <div class="schedule-header">
                    <span class="schedule-stage">${s.Stage || '未知场地'}</span>
                    ${bossImage ? `<img src="${bossImage}" alt="${s.King_Salmonid}" class="schedule-boss-img" title="${s.King_Salmonid}">` : '<span class="schedule-boss">?</span>'}
                </div>
                <div class="schedule-time">
                    ${formatDateTime(s.startTime)} - ${formatDateTime(s.endTime)}
                </div>
                <div id="countdown-timer" class="countdown-timer">计算中...</div>
                <div class="schedule-rating ${ratingClass}">
                    综合评分: ${ratingDisplay}
                </div>
                <div class="weapons-row">
                    ${weapons.map(w => renderWeaponIcon(w)).join('')}
                </div>
                <div class="current-duration">${durationHours}小时</div>
            </div>
        </div>
    `;

    // 启动倒计时
    if (s.endTime) {
        startCurrentScheduleTimer(s.endTime);
    }
}

function renderFutureSchedules() {
    const container = document.getElementById('future-schedules');
    if (!container) return;

    if (AppData.futureSchedules.length === 0) {
        container.innerHTML = '<p>暂无未来的打工场次数据</p>';
        return;
    }

    container.innerHTML = AppData.futureSchedules.map((s, index) => {
        const weapons = getWeaponsForSchedule(s);
        const rating = calculateScheduleRating(weapons);

        // 格式化评分显示
        const ratingDisplay = rating === null ? '?' : (rating.toFixed(1) + '/10');
        const ratingClass = getRatingClass(rating === null ? 5 : rating / 2); // ?使用最高配色

        // 获取boss图片
        const bossImage = getBossImage(s.King_Salmonid);

        // 获取场地图片(imageL)
        const stage = getStageByName(s.Stage);
        const stageImage = stage?.imageL || null;

        return `
            <div class="schedule-card future-card" ${stageImage ? `style="background-image: url('${stageImage}'); background-size: cover; background-position: center;"` : ''}>
                <div class="future-schedule-overlay">
                    <div class="schedule-header">
                        <span class="schedule-stage">${s.Stage || '未知场地'}</span>
                        ${bossImage ? `<img src="${bossImage}" alt="${s.King_Salmonid}" class="schedule-boss-img" title="${s.King_Salmonid}">` : '<span class="schedule-boss">?</span>'}
                    </div>
                    <div class="schedule-time">
                        ${formatDateTime(s.startTime)} - ${formatDateTime(s.endTime)}
                    </div>
                    <div id="future-timer-${index}" class="future-timer">计算中...</div>
                    <div class="schedule-rating ${ratingClass}">
                        评分: ${ratingDisplay}
                    </div>
                    <div class="weapons-row">
                        ${weapons.map(w => renderWeaponIcon(w)).join('')}
                    </div>
                </div>
            </div>
        `;
    }).join('');

    // 启动未来场次倒计时
    startFutureScheduleTimer(AppData.futureSchedules);
}

// ================================
// 历史记录页渲染
// ================================
let currentHistoryFilter = {
    stage: '',
    boss: '',
    weapon: '',
    minRating: ''
};

// 分页状态
let historyPagination = {
    page: 1,
    pageSize: 50,
    total: 0
};

function initFilters() {
    // 填充场地筛选器
    const stageSelect = document.getElementById('filter-stage');
    if (stageSelect) {
        const stages = [...new Set(AppData.schedules.map(s => s.Stage).filter(Boolean))];
        stages.forEach(stage => {
            stageSelect.innerHTML += `<option value="${stage}">${stage}</option>`;
        });
    }
    
    // 填充Boss筛选器
    const bossSelect = document.getElementById('filter-boss');
    if (bossSelect) {
        const bosses = [...new Set(AppData.schedules.map(s => s.King_Salmonid).filter(Boolean))];
        bosses.forEach(boss => {
            bossSelect.innerHTML += `<option value="${boss}">${boss}</option>`;
        });
    }
    
    // 填充武器类型筛选器
    const typeSelect = document.getElementById('weapon-type-filter');
    if (typeSelect) {
        const types = [...new Set(Object.values(AppData.weapons).map(w => w.type).filter(Boolean))];
        types.forEach(type => {
            typeSelect.innerHTML += `<option value="${type}">${type}</option>`;
        });
    }
}

function renderHistory() {
    const tbody = document.getElementById('history-tbody');
    const paginationContainer = document.getElementById('history-pagination');
    if (!tbody) return;

    // 筛选数据
    let filtered = AppData.schedules.filter(s => {
        if (currentHistoryFilter.stage && s.Stage !== currentHistoryFilter.stage) return false;
        if (currentHistoryFilter.boss && s.King_Salmonid !== currentHistoryFilter.boss) return false;

        const weapons = getWeaponsForSchedule(s);
        if (currentHistoryFilter.weapon) {
            const hasWeapon = weapons.some(w =>
                w && (w.name_zh?.includes(currentHistoryFilter.weapon) ||
                      w.name_en?.includes(currentHistoryFilter.weapon))
            );
            if (!hasWeapon) return false;
        }

        const rating = calculateScheduleRating(weapons);
        if (currentHistoryFilter.minRating && (rating === null || rating < parseFloat(currentHistoryFilter.minRating))) {
            return false;
        }

        return true;
    });

    // 按时间倒序
    filtered.sort((a, b) => b.startTime - a.startTime);

    // 更新分页信息
    historyPagination.total = filtered.length;
    const totalPages = Math.ceil(historyPagination.total / historyPagination.pageSize);

    // 确保当前页在有效范围内
    if (historyPagination.page > totalPages) historyPagination.page = totalPages || 1;
    if (historyPagination.page < 1) historyPagination.page = 1;

    // 分页截取数据
    const startIndex = (historyPagination.page - 1) * historyPagination.pageSize;
    const displayData = filtered.slice(startIndex, startIndex + historyPagination.pageSize);

    tbody.innerHTML = displayData.map(s => {
        const weapons = getWeaponsForSchedule(s);
        const rating = calculateScheduleRating(weapons);

        // 格式化评分显示
        const ratingDisplay = rating === null ? '?' : (rating.toFixed(1) + '/10');
        const ratingClass = getRatingClass(rating === null ? 5 : rating / 2); // ?使用最高配色

        // 生成雷达图
        const radarSvg = generateRadarChart(weapons);

        return `
            <tr>
                <td>#${s.no || '-'}</td>
                <td>${formatDateTime(s.startTime)}<br>${formatDateTime(s.endTime)}</td>
                <td>${s.Stage || '-'}</td>
                <td class="center-cell">${s.King_Salmonid || '-'}</td>
                <td>
                    <div class="weapons-row history-weapons">
                        ${weapons.map(w => renderWeaponIcon(w)).join('')}
                    </div>
                </td>
                <td class="center-cell radar-cell">${radarSvg}</td>
                <td class="center-cell ${ratingClass}">${ratingDisplay}</td>
            </tr>
        `;
    }).join('');

    // 渲染分页控件
    if (paginationContainer) {
        renderPagination(paginationContainer, totalPages);
    }
}

function applyFilters() {
    currentHistoryFilter.stage = document.getElementById('filter-stage')?.value || '';
    currentHistoryFilter.boss = document.getElementById('filter-boss')?.value || '';
    currentHistoryFilter.weapon = document.getElementById('filter-weapon')?.value || '';
    currentHistoryFilter.minRating = document.getElementById('filter-rating')?.value || '';

    // 重置到第一页
    historyPagination.page = 1;
    renderHistory();
}

function changePageSize(size) {
    historyPagination.pageSize = parseInt(size);
    historyPagination.page = 1;
    renderHistory();
}

function goToPage(page) {
    historyPagination.page = page;
    renderHistory();
}

function renderPagination(container, totalPages) {
    const currentPage = historyPagination.page;
    const pageSize = historyPagination.pageSize;
    const total = historyPagination.total;

    let paginationHTML = `
        <div class="pagination-controls">
            <div class="page-size-selector">
                <label>每页显示：</label>
                <select onchange="changePageSize(this.value)">
                    <option value="20" ${pageSize === 20 ? 'selected' : ''}>20条</option>
                    <option value="50" ${pageSize === 50 ? 'selected' : ''}>50条</option>
                    <option value="100" ${pageSize === 100 ? 'selected' : ''}>100条</option>
                </select>
            </div>
            <div class="page-info">第 ${currentPage}/${totalPages} 页 (共 ${total} 条)</div>
            <div class="page-buttons">
                <button onclick="goToPage(${currentPage - 1})" ${currentPage <= 1 ? 'disabled' : ''}>上一页</button>
    `;

    // 显示页码按钮（最多显示5个）
    const maxButtons = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxButtons / 2));
    let endPage = Math.min(totalPages, startPage + maxButtons - 1);
    if (endPage - startPage < maxButtons - 1) {
        startPage = Math.max(1, endPage - maxButtons + 1);
    }

    for (let i = startPage; i <= endPage; i++) {
        paginationHTML += `<button onclick="goToPage(${i})" class="${i === currentPage ? 'active' : ''}">${i}</button>`;
    }

    paginationHTML += `
                <button onclick="goToPage(${currentPage + 1})" ${currentPage >= totalPages ? 'disabled' : ''}>下一页</button>
            </div>
        </div>
    `;

    container.innerHTML = paginationHTML;
}

function resetFilters() {
    document.getElementById('filter-stage').value = '';
    document.getElementById('filter-boss').value = '';
    document.getElementById('filter-weapon').value = '';
    document.getElementById('filter-rating').value = '';
    
    currentHistoryFilter = { stage: '', boss: '', weapon: '', minRating: '' };
    renderHistory();
}

// ================================
// 统计页渲染
// ================================
function renderStats() {
    renderWeaponFrequency();
    renderBigRunTable();
    renderEggstraTable();
}

function renderWeaponFrequency() {
    const container = document.getElementById('weapon-frequency');
    if (!container) return;
    
    // 统计武器出场次数
    const weaponCount = {};
    AppData.schedules.forEach(s => {
        (s.Weapon || []).forEach(weaponName => {
            weaponCount[weaponName] = (weaponCount[weaponName] || 0) + 1;
        });
    });
    
    // 排序取前20
    const sorted = Object.entries(weaponCount)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 20);
    
    const maxCount = sorted[0]?.[1] || 1;
    
    container.innerHTML = sorted.map(([name, count]) => {
        const weapon = AppData.weaponNameMap.get(name);
        const percentage = (count / maxCount * 100).toFixed(0);
        
        return `
            <div class="stat-card">
                <div class="stat-header">
                    <span>${weapon?.name_zh || name}</span>
                    <span>${count} 次</span>
                </div>
                <div class="stat-bar">
                    <div class="stat-bar-fill" style="width: ${percentage}%"></div>
                </div>
            </div>
        `;
    }).join('');
}

function renderBigRunTable() {
    const tbody = document.getElementById('bigrun-tbody');
    if (!tbody) return;
    
    tbody.innerHTML = AppData.bigRuns.map(run => `
        <tr>
            <td>${run.no || '-'}</td>
            <td>${run.Stage || '-'}</td>
            <td>${run.Start_time || '-'}</td>
            <td class="rating-high">${run.Gold ?? '-'}</td>
            <td class="rating-mid">${run.Silver ?? '-'}</td>
            <td class="rating-low">${run.Bronze ?? '-'}</td>
        </tr>
    `).join('');
}

function renderEggstraTable() {
    const tbody = document.getElementById('eggstra-tbody');
    if (!tbody) return;
    
    tbody.innerHTML = AppData.eggstraWorks.map(run => `
        <tr>
            <td>${run.no || '-'}</td>
            <td>${run.Stage || '-'}</td>
            <td>${run.Start_time || '-'}</td>
            <td class="rating-high">${run.Gold ?? '-'}</td>
            <td class="rating-mid">${run.Silver ?? '-'}</td>
            <td class="rating-low">${run.Bronze ?? '-'}</td>
        </tr>
    `).join('');
}

// ================================
// 武器页渲染
// ================================
let currentWeaponFilter = '';
let currentWeaponSort = 'rating-desc';

function renderWeapons() {
    const container = document.getElementById('weapon-grid');
    if (!container) return;
    
    let weapons = Object.values(AppData.weapons);
    
    // 筛选
    if (currentWeaponFilter) {
        weapons = weapons.filter(w => w.type === currentWeaponFilter);
    }
    
    // 排序
    weapons.sort((a, b) => {
        switch(currentWeaponSort) {
            case 'rating-desc':
                // null 值排到最后
                if (a.rating?.overall === null && b.rating?.overall === null) return 0;
                if (a.rating?.overall === null) return 1;
                if (b.rating?.overall === null) return -1;
                return (b.rating?.overall || 0) - (a.rating?.overall || 0);
            case 'rating-asc':
                // null 值排到最后
                if (a.rating?.overall === null && b.rating?.overall === null) return 0;
                if (a.rating?.overall === null) return 1;
                if (b.rating?.overall === null) return -1;
                return (a.rating?.overall || 0) - (b.rating?.overall || 0);
            case 'name':
                return (a.name_zh || '').localeCompare(b.name_zh || '');
            case 'type':
                return (a.type || '').localeCompare(b.type || '');
            default:
                return 0;
        }
    });
    
    container.innerHTML = weapons.map(w => {
        const rating = w.rating?.overall;
        const tier = w.rating?.tier;
        const dimensions = w.rating?.dimensions || {};
        
        // 处理 null 值显示
        const ratingDisplay = rating === null ? '?' : (rating || 0).toFixed(1);
        const tierDisplay = tier === null ? '?' : (tier || '?');
        
        return `
            <div class="weapon-card">
                <div class="weapon-image">
                    ${w.image ? `<img src="${w.image}" alt="${w.name_zh}" onerror="this.style.display='none'">` : '?'}
                </div>
                <div class="weapon-name">${w.name_zh || w.name_en || '未知'}</div>
                <div class="weapon-type">${w.type || '?'}</div>
                <div class="weapon-rating tier-${tierDisplay.replace('+', '-plus').replace('X', 'X')}">${ratingDisplay}</div>
                <span class="tier-badge tier-${tierDisplay.replace('+', '-plus').replace('X', 'X')}">${tierDisplay}</span>
                
                <div class="dimension-bars">
                    ${Object.entries(dimensions).slice(0, 4).map(([key, val]) => `
                        <div class="dimension-row">
                            <span class="dimension-label">${key}</span>
                            <div class="dimension-bar">
                                <div class="dimension-fill" style="width: ${(val === null ? 0 : (val || 0)) * 20}%"></div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }).join('');
}

function filterWeapons() {
    currentWeaponFilter = document.getElementById('weapon-type-filter')?.value || '';
    renderWeapons();
}

function sortWeapons() {
    currentWeaponSort = document.getElementById('weapon-sort')?.value || 'rating-desc';
    renderWeapons();
}

// ================================
// 武器评分自定义功能
// ================================
function downloadWeaponScores() {
    const scores = {};
    Object.entries(AppData.weapons).forEach(([id, w]) => {
        scores[id] = w.rating || { overall: 3, tier: 'B', dimensions: {} };
    });
    
    const blob = new Blob([JSON.stringify(scores, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = 'weapon_scores.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    console.log('📥 武器评分配置已下载');
}

function uploadWeaponScores(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = (e) => {
        try {
            const customScores = JSON.parse(e.target.result);
            
            // 验证数据格式
            if (typeof customScores !== 'object') {
                throw new Error('无效的评分数据格式');
            }
            
            // 保存到 localStorage
            localStorage.setItem('salmon_custom_scores', JSON.stringify(customScores));
            AppData.customScores = customScores;
            
            // 应用新评分
            applyCustomScores();
            
            alert('✅ 自定义评分已应用！所有场次的评分将重新计算。');
            
            // 重新渲染当前页面
            const currentPage = document.querySelector('.page-content:not([style*="none"])')?.id;
            if (currentPage) {
                switch(currentPage) {
                    case 'home': renderHome(); break;
                    case 'history': renderHistory(); break;
                    case 'weapons': renderWeapons(); break;
                }
            }
            
        } catch (err) {
            alert('❌ 文件解析失败: ' + err.message);
        }
    };
    reader.readAsText(file);
    
    // 清空input以便可以重复选择同一文件
    event.target.value = '';
}

// ================================
// 工具函数
// ================================
function getWeaponsForSchedule(schedule) {
    if (!schedule.Weapon || !Array.isArray(schedule.Weapon)) {
        return [];
    }

    return schedule.Weapon.map(weaponName => {
        return AppData.weaponNameMap.get(weaponName) || null;
    }).filter(Boolean);
}

function getBossImage(bossName) {
    if (!bossName) return null;
    // 在 boss 数据中查找
    const boss = Object.values(AppData.bosses).find(b =>
        b.name_zh === bossName || b.name_en === bossName || b.id === bossName
    );
    return boss?.image_path || null;
}

function calculateScheduleRating(weapons) {
    if (!weapons || weapons.length === 0) return null;

    // 检查是否有问号武器（overall 为 null 的武器）
    const hasQuestionMarkWeapon = weapons.some(w => w?.rating?.overall === null);
    if (hasQuestionMarkWeapon) {
        return null; // 有问号武器时返回 null，显示 "?"
    }

    // 过滤掉无效值，只计算有评分的武器
    const ratings = weapons
        .map(w => w?.rating?.overall)
        .filter(r => r !== null && r !== undefined && typeof r === 'number');

    if (ratings.length === 0) return null;

    // 计算总分（4把武器加起来除以2，总分10分制）
    const sum = ratings.reduce((a, b) => a + b, 0);
    const score = (sum / ratings.length) * 2;
    return score; // 返回 0-10 的分数
}

function getRatingClass(rating) {
    if (rating >= 4) return 'rating-high';
    if (rating >= 3) return 'rating-mid';
    return 'rating-low';
}

function getTierClass(tier) {
    if (!tier) return '';
    return 'tier-' + tier.replace('+', '-plus').replace('X', 'X');
}

function renderWeaponIcon(weapon) {
    if (!weapon) return '<div class="weapon-icon">?</div>';

    const name = weapon.name_zh || weapon.name_en || '?';
    const rating = weapon.rating?.overall;
    const ratingDisplay = rating === null ? '?' : (rating || 0).toFixed(1);
    const ratingClass = rating === null ? '' : getRatingClass(rating || 0);

    return `
        <div class="weapon-icon ${ratingClass}" title="${name} (${ratingDisplay})">
            ${weapon.image ? `<img src="${weapon.image}" alt="${name}" loading="lazy">` : name.slice(0, 2)}
        </div>
    `;
}

function hideLoading() {
    const loading = document.getElementById('loading');
    if (loading) {
        loading.classList.add('hidden');
    }
}

function showError(message) {
    const loading = document.getElementById('loading');
    if (loading) {
        loading.innerHTML = `<div class="loading-content"><p style="color: #ff6b35;">❌ ${message}</p></div>`;
    }
}

// ================================
// 调试接口（控制台可用）
// ================================
window.SalmonApp = {
    data: AppData,
    reload: init,
    clearCustomScores: () => {
        localStorage.removeItem('salmon_custom_scores');
        location.reload();
    }
};
