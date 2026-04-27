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
// 多语言支持 (i18n)
// ================================
let i18nData = {};           // 语言数据
let currentLang = 'cn';      // 当前语言

// 加载语言文件
async function loadLanguageData() {
    try {
        const response = await fetch('./data/language.json');
        if (response.ok) {
            i18nData = await response.json();
            // 从 localStorage 读取用户设置的语言
            const savedLang = localStorage.getItem('salmon_language');
            if (savedLang && i18nData[savedLang]) {
                currentLang = savedLang;
            }
            // 更新语言选择器
            const langSelector = document.getElementById('lang-selector');
            if (langSelector) {
                langSelector.value = currentLang;
            }
            console.log('✅ 语言数据已加载:', currentLang);
        }
    } catch (error) {
        console.error('❌ 加载语言数据失败:', error);
    }
}

// 翻译函数
function t(key) {
    if (!i18nData[currentLang]) return key;

    const keys = key.split('.');
    let value = i18nData[currentLang];

    for (const k of keys) {
        if (value && typeof value === 'object' && k in value) {
            value = value[k];
        } else {
            // 如果找不到翻译，返回中文或key本身
            if (i18nData['cn'] && key !== '') {
                let cnValue = i18nData['cn'];
                for (const k2 of keys) {
                    if (cnValue && typeof cnValue === 'object' && k2 in cnValue) {
                        cnValue = cnValue[k2];
                    } else {
                        return key;
                    }
                }
                return cnValue || key;
            }
            return key;
        }
    }

    return value || key;
}

// 切换语言
function changeLanguage(lang) {
    if (!i18nData[lang]) {
        console.warn('不支持的语言:', lang);
        return;
    }

    currentLang = lang;
    localStorage.setItem('salmon_language', lang);

    // 重新渲染所有页面
    const currentPage = document.querySelector('.page-content:not([style*="none"])')?.id;

    // 更新静态文本
    updateStaticText();

    // 重新渲染当前页面内容
    switch(currentPage) {
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

    console.log('🌐 语言已切换:', lang);
}

// 更新静态文本（导航栏等）
function updateStaticText() {
    // 更新所有带有 data-i18n 属性的元素
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (key) {
            const translated = t(key);
            if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                el.placeholder = translated;
            } else {
                el.textContent = translated;
            }
        }
    });

    // 更新 placeholder
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        if (key) {
            el.placeholder = t(key);
        }
    });

    // 更新加载提示
    const loadingText = document.querySelector('.loading-content p');
    if (loadingText && !loadingText.getAttribute('data-i18n')) {
        loadingText.textContent = t('common.loading');
    }
}

// ================================
// 初始化
// ================================
document.addEventListener('DOMContentLoaded', init);

async function init() {
    console.log('🐟 SalmonAnalysis3 初始化中...');

    try {
        // 并行加载所有数据（包括语言数据）
        await Promise.all([
            loadAllData(),
            loadLanguageData()
        ]);

        // 更新静态文本
        updateStaticText();

        // 加载用户自定义评分（来自上传的JSON文件）
        loadCustomScores();

        // 加载用户对武器评分的修改
        loadUserWeaponEdits();

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
// 时区处理
// ================================
// JSON 数据使用的基准时区（东八区）
const DATA_TIMEZONE = 'Asia/Shanghai';
const DATA_TIMEZONE_OFFSET = -8 * 60; // 东八区相对于 UTC 的分钟数（负值表示东时区）

// 获取用户本地时区与数据时区的时差（分钟）
function getTimezoneOffsetMinutes() {
    const now = new Date();
    // 用户本地时区偏移（分钟）
    const userOffset = now.getTimezoneOffset(); // 注意：正值表示西时区
    // 数据时区偏移（东八区 = -480 分钟）
    const dataOffset = DATA_TIMEZONE_OFFSET;
    // 返回需要调整的分钟数
    return userOffset - dataOffset;
}

// 将数据时间（东八区）转换为用户本地时间
function convertToLocalTime(date) {
    if (!date) return null;
    const offsetMinutes = getTimezoneOffsetMinutes();
    return new Date(date.getTime() - offsetMinutes * 60 * 1000);
}

// ================================
// 时间计算逻辑
// ================================
function calculateSchedules() {
    const now = new Date();

    // 将 schedule 的时间字符串转换为 Date 对象（并进行时区转换）
    const parsedSchedules = AppData.schedules.map(s => {
        // 先按东八区解析
        const startTimeCST = parseTimeString(s.Start_time);
        const endTimeCST = parseTimeString(s.End_time);

        // 转换为用户本地时间
        return {
            ...s,
            startTime: convertToLocalTime(startTimeCST),
            endTime: convertToLocalTime(endTimeCST),
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

function formatDateTime(date, showWeekday = false) {
    if (!date) return '-';
    const d = new Date(date);
    const weekdays = ['日', '一', '二', '三', '四', '五', '六'];
    const weekday = showWeekday ? `(${weekdays[d.getDay()]})` : '';
    return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}${weekday} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

// 历史记录专用的时间格式化（不显示周几，用于历史记录表格）
function formatDateTimeHistory(date) {
    if (!date) return '-';
    const d = new Date(date);
    return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
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
            const timerEl = document.getElementById('countdown-timer');
            if (timerEl) timerEl.textContent = t('home.ended');
            clearInterval(currentScheduleTimer);
            return;
        }

        const hours = Math.floor(diff / (1000 * 60 * 60));
        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((diff % (1000 * 60)) / 1000);

        const timerEl = document.getElementById('countdown-timer');
        if (timerEl) {
            timerEl.textContent = `${t('home.timeRemaining')}${hours}${t('home.hours')}${minutes}${t('home.minutes')}${seconds}${t('home.seconds')}`;
        }
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
                timerEl.textContent = t('home.started');
                return;
            }

            const days = Math.floor(diff / (1000 * 60 * 60 * 24));
            const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

            if (days > 0) {
                timerEl.textContent = `${days}${t('home.days')}${hours}${t('home.hours')}${minutes}${t('home.minutes')}${t('home.after')}`;
            } else {
                timerEl.textContent = `${hours}${t('home.hours')}${minutes}${t('home.minutes')}${t('home.after')}`;
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
        container.innerHTML = `<div class="schedule-card"><p>${t('home.noCurrent')}</p></div>`;
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

    container.innerHTML = `
        <div class="schedule-card current" ${bannerImage ? `style="background-image: url('${bannerImage}'); background-size: cover; background-position: center;"` : ''}>
            <div class="current-schedule-overlay">
                <div class="schedule-header">
                    <span class="schedule-stage">${s.Stage || t('home.unknownStage')}</span>
                    ${bossImage ? `<img src="${bossImage}" alt="${s.King_Salmonid}" class="schedule-boss-img" title="${s.King_Salmonid}">` : '<span class="schedule-boss">?</span>'}
                </div>
                <div class="schedule-time">
                    <span class="time-start">${formatDateTime(s.startTime, true)}</span> - <span class="time-end">${formatDateTime(s.endTime)}</span>
                </div>
                <div id="countdown-timer" class="countdown-timer">${t('home.calculating')}</div>
                <div class="weapons-row">
                    ${weapons.map(w => renderWeaponIcon(w)).join('')}
                </div>
                <div class="schedule-rating-bottom ${ratingClass}">
                    ${t('home.rating')}:${ratingDisplay}
                </div>
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
        container.innerHTML = `<p>${t('home.noFuture')}</p>`;
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
                        <span class="time-start">${formatDateTime(s.startTime, true)}</span> - <span class="time-end">${formatDateTime(s.endTime)}</span>
                    </div>
                    <div id="future-timer-${index}" class="future-timer">计算中...</div>
                    <div class="weapons-row">
                        ${weapons.map(w => renderWeaponIcon(w)).join('')}
                    </div>
                    <div class="schedule-rating-bottom ${ratingClass}">
                        评分:${ratingDisplay}
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
    weapons: [], // 多武器筛选数组
    minRating: '',
    maxRating: ''
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
        stageSelect.innerHTML = `<option value="">${t('weapons.filter.all')}</option>`;
        stages.forEach(stage => {
            stageSelect.innerHTML += `<option value="${stage}">${stage}</option>`;
        });
    }

    // 填充Boss筛选器
    const bossSelect = document.getElementById('filter-boss');
    if (bossSelect) {
        const bosses = [...new Set(AppData.schedules.map(s => s.King_Salmonid).filter(Boolean))];
        bossSelect.innerHTML = `<option value="">${t('weapons.filter.all')}</option>`;
        bosses.forEach(boss => {
            bossSelect.innerHTML += `<option value="${boss}">${boss}</option>`;
        });
    }

    // 填充武器类型筛选器
    const typeSelect = document.getElementById('weapon-type-filter');
    if (typeSelect) {
        const types = [...new Set(Object.values(AppData.weapons).map(w => w.type).filter(Boolean))];
        typeSelect.innerHTML = `<option value="">${t('weapons.filter.all')}</option>`;
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
        if (currentHistoryFilter.weapons && currentHistoryFilter.weapons.length > 0) {
            // 多武器筛选：场次必须包含所有指定的武器（AND逻辑）
            const hasAllWeapons = currentHistoryFilter.weapons.every(filterWeapon => {
                return weapons.some(w =>
                    w && (w.name_zh?.includes(filterWeapon) ||
                          w.name_en?.includes(filterWeapon))
                );
            });
            if (!hasAllWeapons) return false;
        }

        const rating = calculateScheduleRating(weapons);
        const minRating = parseFloat(currentHistoryFilter.minRating);
        const maxRating = parseFloat(currentHistoryFilter.maxRating);

        if (!isNaN(minRating) && (rating === null || rating < minRating)) {
            return false;
        }
        if (!isNaN(maxRating) && (rating === null || rating > maxRating)) {
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
                <td>${formatDateTimeHistory(s.startTime)}<br>${formatDateTimeHistory(s.endTime)}</td>
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
    currentHistoryFilter.weapons = getWeaponFilterValues();
    currentHistoryFilter.minRating = document.getElementById('filter-rating-min')?.value || '';
    currentHistoryFilter.maxRating = document.getElementById('filter-rating-max')?.value || '';

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
    document.getElementById('filter-rating-min').value = '';
    document.getElementById('filter-rating-max').value = '';

    // 重置武器筛选为单个空输入框
    const container = document.getElementById('weapon-filter-container');
    container.innerHTML = '<input type="text" class="filter-weapon-input" placeholder="输入武器名称" data-index="0" oninput="onWeaponInputChange(this)">';

    currentHistoryFilter = { stage: '', boss: '', weapons: [], minRating: '', maxRating: '' };
    renderHistory();
}

// 武器筛选输入框变化处理
function onWeaponInputChange(input) {
    const container = document.getElementById('weapon-filter-container');
    const inputs = container.querySelectorAll('.filter-weapon-input');
    const currentIndex = parseInt(input.dataset.index);

    // 如果当前输入框有值且不是最后一个，且总数少于4个，添加新输入框
    if (input.value.trim() !== '' && currentIndex === inputs.length - 1 && inputs.length < 4) {
        const newInput = document.createElement('input');
        newInput.type = 'text';
        newInput.className = 'filter-weapon-input';
        newInput.placeholder = '输入武器名称';
        newInput.dataset.index = currentIndex + 1;
        newInput.oninput = function() { onWeaponInputChange(this); };
        container.appendChild(newInput);
    }

    // 如果当前输入框被清空且不是唯一一个，且后面没有值，移除后面的空输入框
    if (input.value.trim() === '') {
        // 移除当前之后的所有空输入框
        for (let i = inputs.length - 1; i > currentIndex; i--) {
            if (inputs[i].value.trim() === '') {
                inputs[i].remove();
            }
        }
    }
}

// 获取所有武器筛选值
function getWeaponFilterValues() {
    const container = document.getElementById('weapon-filter-container');
    if (!container) return [];
    const inputs = container.querySelectorAll('.filter-weapon-input');
    return Array.from(inputs)
        .map(input => input.value.trim())
        .filter(value => value !== '');
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
            <td>${run.no || t('common.empty')}</td>
            <td>${run.Stage || t('common.empty')}</td>
            <td>${run.Start_time || t('common.empty')}</td>
            <td class="rating-high">${run.Gold ?? t('common.empty')}</td>
            <td class="rating-mid">${run.Silver ?? t('common.empty')}</td>
            <td class="rating-low">${run.Bronze ?? t('common.empty')}</td>
        </tr>
    `).join('');
}

function renderEggstraTable() {
    const tbody = document.getElementById('eggstra-tbody');
    if (!tbody) return;

    tbody.innerHTML = AppData.eggstraWorks.map(run => `
        <tr>
            <td>${run.no || t('common.empty')}</td>
            <td>${run.Stage || t('common.empty')}</td>
            <td>${run.Start_time || t('common.empty')}</td>
            <td class="rating-high">${run.Gold ?? t('common.empty')}</td>
            <td class="rating-mid">${run.Silver ?? t('common.empty')}</td>
            <td class="rating-low">${run.Bronze ?? t('common.empty')}</td>
        </tr>
    `).join('');
}

// ================================
// 武器详情弹窗
// ================================
let currentEditingWeapon = null;  // 当前正在编辑的武器
let editModeData = null;          // 编辑中的数据副本

function openWeaponModal(weaponDataEncoded) {
    const modal = document.getElementById('weapon-modal');
    const modalBody = document.getElementById('weapon-modal-body');
    const modalFooter = document.getElementById('weapon-modal-footer');

    // 解码武器数据
    const w = JSON.parse(decodeURIComponent(weaponDataEncoded));
    currentEditingWeapon = w;

    // 隐藏底部按钮（重置为查看模式）
    modalFooter.style.display = 'none';

    // 渲染查看模式
    renderViewMode(w);

    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden'; // 防止背景滚动
}

function renderViewMode(w) {
    const modalBody = document.getElementById('weapon-modal-body');

    // 获取用户的修改（如果有）
    const userEdit = getUserWeaponEdit(w.id);
    const rating = userEdit?.overall ?? w.rating?.overall;
    const tier = userEdit?.tier ?? w.rating?.tier;
    const dimensions = userEdit?.dimensions ?? w.rating?.dimensions ?? {};

    // 处理 null 值显示
    const ratingDisplay = rating === null ? '?' : (rating || 0).toFixed(1);
    const tierDisplay = tier === null ? '?' : (tier || '?');
    const isQuestionMarkWeapon = rating === null;

    // 获取所有6个维度
    const allDimensions = Object.entries(dimensions);

    const ratingClass = getRatingClass(rating === null ? 5 : rating);
    const tierClass = 'tier-' + tierDisplay.replace('+', '-plus').replace('X', 'X');

    // 铅笔图标（SVG）
    const editIcon = `
        <button class="edit-icon-btn" onclick="enterEditMode()" title="编辑武器评分">
            <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/>
            </svg>
        </button>
    `;

    modalBody.innerHTML = `
        <div class="modal-weapon-header">
            <div class="modal-weapon-image">
                ${w.image ? `<img src="${w.image}" alt="${w.name_zh}" onerror="this.style.display='none'">` : '?'}
            </div>
            <div class="modal-weapon-name">${w.name_zh || w.name_en || '未知'}${editIcon}</div>
            <div class="modal-weapon-type">${w.type || '?'}</div>
            <div class="modal-weapon-rating ${ratingClass} ${tierClass}">${ratingDisplay}</div>
            <span class="modal-weapon-tier ${tierClass}">${tierDisplay}</span>
        </div>

        <div class="modal-dimensions">
            ${isQuestionMarkWeapon ? `
                ${allDimensions.map(([key, val]) => `
                    <div class="modal-dimension-row">
                        <span class="modal-dimension-label">${key}</span>
                        <span class="modal-dimension-question">?</span>
                    </div>
                `).join('')}
            ` : `
                ${allDimensions.map(([key, val]) => `
                    <div class="modal-dimension-row">
                        <span class="modal-dimension-label">${key}</span>
                        <div class="modal-dimension-bar-container">
                            <div class="modal-dimension-bar">
                                <div class="modal-dimension-fill" style="width: ${(val === null ? 0 : (val || 0)) * 20}%"></div>
                            </div>
                            <span class="modal-dimension-value">${val === null ? '?' : (val || 0).toFixed(1)}</span>
                        </div>
                    </div>
                `).join('')}
            `}
        </div>
    `;
}

function enterEditMode() {
    const modalBody = document.getElementById('weapon-modal-body');
    const modalFooter = document.getElementById('weapon-modal-footer');

    if (!currentEditingWeapon) return;

    // 获取当前值（优先使用用户已修改的值）
    const userEdit = getUserWeaponEdit(currentEditingWeapon.id);
    const currentRating = userEdit?.overall ?? currentEditingWeapon.rating?.overall ?? 0;
    const currentTier = userEdit?.tier ?? currentEditingWeapon.rating?.tier ?? 'B';
    const currentDimensions = userEdit?.dimensions ?? currentEditingWeapon.rating?.dimensions ?? {};

    // 创建编辑数据副本
    editModeData = {
        overall: currentRating,
        tier: currentTier,
        dimensions: { ...currentDimensions }
    };

    // 渲染编辑模式
    renderEditMode();

    // 显示底部按钮
    modalFooter.style.display = 'flex';
}

function renderEditMode() {
    const modalBody = document.getElementById('weapon-modal-body');
    const w = currentEditingWeapon;
    const dimensions = editModeData.dimensions;

    const allDimensions = Object.entries(dimensions);

    modalBody.innerHTML = `
        <div class="modal-weapon-header">
            <div class="modal-weapon-image">
                ${w.image ? `<img src="${w.image}" alt="${w.name_zh}" onerror="this.style.display='none'">` : '?'}
            </div>
            <div class="modal-weapon-name">${w.name_zh || w.name_en || '未知'}</div>
            <div class="modal-weapon-type">${w.type || '?'}</div>
            <div style="margin-bottom: 0.5rem;">
                <input type="number" id="edit-rating" class="modal-input rating-input" 
                       value="${editModeData.overall}" min="0" max="10" step="0.1" 
                       onchange="updateEditData('overall', this.value)">
            </div>
            <input type="text" id="edit-tier" class="modal-input tier-input" 
                   value="${editModeData.tier}" maxlength="2" placeholder="S+/X"
                   onchange="updateEditData('tier', this.value)">
        </div>

        <div class="modal-dimensions">
            ${allDimensions.map(([key, val]) => `
                <div class="modal-dimension-row">
                    <span class="modal-dimension-label">${key}</span>
                    <div class="modal-dimension-bar-container">
                        <div class="modal-dimension-bar">
                            <div class="modal-dimension-fill" style="width: ${(val === null ? 0 : (val || 0)) * 20}%"></div>
                        </div>
                        <input type="number" class="modal-dimension-input" 
                               value="${val === null ? '' : (val || 0)}" 
                               min="0" max="5" step="0.1"
                               onchange="updateEditDimension('${key}', this.value)">
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

function updateEditData(field, value) {
    if (!editModeData) return;
    if (field === 'overall') {
        editModeData.overall = parseFloat(value) || 0;
    } else if (field === 'tier') {
        editModeData.tier = value.toUpperCase();
    }
}

function updateEditDimension(key, value) {
    if (!editModeData || !editModeData.dimensions) return;
    editModeData.dimensions[key] = parseFloat(value) || 0;
}

function saveWeaponEdit() {
    if (!currentEditingWeapon || !editModeData) return;

    // 保存到用户修改存储
    saveUserWeaponEdit(currentEditingWeapon.id, editModeData);

    // 更新武器数据（前端显示用）
    if (AppData.weapons[currentEditingWeapon.id]) {
        AppData.weapons[currentEditingWeapon.id].rating = {
            overall: editModeData.overall,
            tier: editModeData.tier,
            dimensions: { ...editModeData.dimensions }
        };
    }

    // 隐藏底部按钮
    document.getElementById('weapon-modal-footer').style.display = 'none';

    // 重新渲染查看模式
    renderViewMode(currentEditingWeapon);

    // 刷新武器列表显示
    renderWeapons();

    // 提示保存成功
    showToast('武器评分已保存');
}

function cancelWeaponEdit() {
    // 隐藏底部按钮
    document.getElementById('weapon-modal-footer').style.display = 'none';

    // 重新渲染查看模式（放弃修改）
    if (currentEditingWeapon) {
        renderViewMode(currentEditingWeapon);
    }
}

// 获取用户对武器的修改
function getUserWeaponEdit(weaponId) {
    try {
        const saved = localStorage.getItem('salmon_weapon_edits');
        if (saved) {
            const edits = JSON.parse(saved);
            return edits[weaponId] || null;
        }
    } catch (e) {
        console.warn('读取用户武器修改失败:', e);
    }
    return null;
}

// 保存用户对武器的修改
function saveUserWeaponEdit(weaponId, data) {
    try {
        let edits = {};
        const saved = localStorage.getItem('salmon_weapon_edits');
        if (saved) {
            edits = JSON.parse(saved);
        }
        edits[weaponId] = data;
        localStorage.setItem('salmon_weapon_edits', JSON.stringify(edits));
    } catch (e) {
        console.error('保存用户武器修改失败:', e);
    }
}

// 加载用户武器修改（初始化时调用）
function loadUserWeaponEdits() {
    try {
        const saved = localStorage.getItem('salmon_weapon_edits');
        if (saved) {
            const edits = JSON.parse(saved);
            // 应用到武器数据
            Object.entries(edits).forEach(([weaponId, data]) => {
                if (AppData.weapons[weaponId]) {
                    AppData.weapons[weaponId].rating = {
                        overall: data.overall,
                        tier: data.tier,
                        dimensions: { ...data.dimensions }
                    };
                }
            });
            console.log('✅ 已加载用户武器修改');
        }
    } catch (e) {
        console.warn('加载用户武器修改失败:', e);
    }
}

// 下载用户修改后的武器评分
function downloadUserWeaponScores() {
    // 获取当前武器数据（包含用户修改）
    const scores = {};
    Object.entries(AppData.weapons).forEach(([id, w]) => {
        scores[id] = w.rating || { overall: 3, tier: 'B', dimensions: {} };
    });

    const blob = new Blob([JSON.stringify(scores, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = 'my_weapon_scores.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    console.log('📥 用户武器评分已下载');
}

// 重置所有用户修改
function resetAllUserWeaponEdits() {
    localStorage.removeItem('salmon_weapon_edits');
    location.reload();
}

// 简单的 Toast 提示
function showToast(message) {
    // 创建 toast 元素
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        bottom: 100px;
        left: 50%;
        transform: translateX(-50%);
        background: var(--splat-yellow);
        color: var(--splat-black);
        padding: 0.8rem 1.5rem;
        border-radius: 8px;
        font-weight: bold;
        z-index: 2000;
        animation: fadeInUp 0.3s ease;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);

    // 2秒后移除
    setTimeout(() => {
        toast.style.animation = 'fadeOut 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 2000);
}

function closeWeaponModal(event) {
    // 如果点击的是关闭按钮或遮罩层，则关闭弹窗
    if (!event || event.target.id === 'weapon-modal' || event.target.classList.contains('modal-close')) {
        const modal = document.getElementById('weapon-modal');
        modal.style.display = 'none';
        document.body.style.overflow = ''; // 恢复背景滚动
        // 重置编辑状态
        currentEditingWeapon = null;
        editModeData = null;
        document.getElementById('weapon-modal-footer').style.display = 'none';
    }
}

// 键盘 ESC 关闭弹窗
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeWeaponModal();
    }
});

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

        // 处理 null 值显示 (绿问号和金问号武器)
        const ratingDisplay = rating === null ? '?' : (rating || 0).toFixed(1);
        const tierDisplay = tier === null ? '?' : (tier || '?');
        const isQuestionMarkWeapon = rating === null;

        // 检查是否有用户修改
        const hasUserEdit = getUserWeaponEdit(w.id) !== null;

        // 获取所有6个维度
        const allDimensions = Object.entries(dimensions);

        // 将武器数据编码为 JSON 字符串，用于点击事件
        const weaponData = encodeURIComponent(JSON.stringify(w));

        return `
            <div class="weapon-card${hasUserEdit ? ' user-modified' : ''}" onclick="openWeaponModal('${weaponData}')">
                <div class="weapon-image">
                    ${w.image ? `<img src="${w.image}" alt="${w.name_zh}" onerror="this.style.display='none'">` : '?'}
                </div>
                <div class="weapon-name">${w.name_zh || w.name_en || '未知'}</div>
                <div class="weapon-type">${w.type || '?'}</div>
                <div class="weapon-rating tier-${tierDisplay.replace('+', '-plus').replace('X', 'X')}">${ratingDisplay}</div>
                <span class="tier-badge tier-${tierDisplay.replace('+', '-plus').replace('X', 'X')}">${tierDisplay}</span>

                <div class="dimension-bars">
                    ${isQuestionMarkWeapon ? `
                        ${allDimensions.map(([key, val]) => `
                            <div class="dimension-row">
                                <span class="dimension-label">${key}</span>
                                <span class="dimension-question">?</span>
                            </div>
                        `).join('')}
                    ` : `
                        ${allDimensions.map(([key, val]) => `
                            <div class="dimension-row">
                                <span class="dimension-label">${key}</span>
                                <div class="dimension-bar">
                                    <div class="dimension-fill" style="width: ${(val === null ? 0 : (val || 0)) * 20}%"></div>
                                </div>
                            </div>
                        `).join('')}
                    `}
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
