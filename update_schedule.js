const fs = require('fs');
const path = require('path');

const DATA_DIR = path.join(__dirname, 'data');
const SCHEDULE_FILE = path.join(DATA_DIR, 'coop_schedule.json');
const STAGE_FILE = path.join(DATA_DIR, 'stage_data.json');
const BOSS_FILE = path.join(DATA_DIR, 'boss_data.json');
const WEAPON_FILE = path.join(DATA_DIR, 'weapon_data.json');

function buildDict(filePath, rootKey) {
    if (!fs.existsSync(filePath)) return {};
    try {
        const rawData = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
        const dict = {};
        const items = rawData[rootKey];
        for (const key in items) {
            if (items[key].name_en && items[key].name_zh) {
                dict[items[key].name_en] = items[key].name_zh;
            }
        }
        return dict;
    } catch (e) { return {}; }
}

function formatToUTC8(isoString) {
    const date = new Date(isoString);
    const utc8 = new Date(date.getTime() + 8 * 60 * 60 * 1000);
    const yyyy = utc8.getUTCFullYear();
    const MM = String(utc8.getUTCMonth() + 1).padStart(2, '0');
    const dd = String(utc8.getUTCDate()).padStart(2, '0');
    const HH = String(utc8.getUTCHours()).padStart(2, '0');
    const mm = String(utc8.getUTCMinutes()).padStart(2, '0');
    return `${yyyy}/${MM}/${dd} ${HH}:${mm}`;
}

function getDuration(startIso, endIso) {
    const d1 = new Date(startIso);
    const d2 = new Date(endIso);
    return String(Math.round((d2 - d1) / (1000 * 60 * 60)));
}

async function updateSchedules() {
    try {
        console.log('正在加载本地字典数据...');
        const stageDict = buildDict(STAGE_FILE, 'stage');
        const bossDict = buildDict(BOSS_FILE, 'boss');
        const weaponDict = buildDict(WEAPON_FILE, 'weapon');

        let localData = { schedule: [] };
        let lastStartTimeMs = 0;
        let lastNo = 0;

        if (fs.existsSync(SCHEDULE_FILE)) {
            const content = fs.readFileSync(SCHEDULE_FILE, 'utf-8');
            if (content.trim()) {
                localData = JSON.parse(content);
                if (localData.schedule && localData.schedule.length > 0) {
                    const latestRecord = localData.schedule.reduce((prev, current) => {
                        return (new Date(current.Start_time).getTime() > new Date(prev.Start_time).getTime()) ? current : prev;
                    });
                    lastStartTimeMs = new Date(latestRecord.Start_time).getTime();
                    const lastItem = localData.schedule[localData.schedule.length - 1];
                    lastNo = parseInt(lastItem.no) || 0;
                    console.log(`读取到本地共 ${localData.schedule.length} 条数据。最新序号 ${lastNo}，开始时间 ${latestRecord.Start_time}。`);
                }
            }
        }

        console.log('正在请求 splatoon3.ink 数据...');
        const response = await fetch('https://splatoon3.ink/data/schedules.json');
        const jsonResponse = await response.json();
        const coopGroupingSchedule = jsonResponse.data.coopGroupingSchedule;

        const fetchedSchedules = [];

        // --- 核心解析逻辑 ---
        const parseNode = (node, isBigRun) => {
            // 1. 检查 node 是否存在以及是否有时间
            if (!node || !node.startTime || !node.endTime) return null;

            // 2. 检查 setting 及其内部数据（关键防御）
            const setting = node.coopStage ? node : node.setting; // 兼容不同API层级
            
            // 如果连场景信息都没有，说明是无效节点，跳过
            if (!setting && !node.setting) return null;
            
            const finalSetting = node.setting || node;

            const stageNameEn = finalSetting.coopStage?.name || "Unknown";
            const bossNameEn = finalSetting.boss?.name || node.__splatoon3ink_king_salmonid_guess || "Unknown";
            
            // 3. 安全提取武器
            let weaponsZh = ["未知", "未知", "未知", "未知"];
            if (finalSetting.weapons && Array.isArray(finalSetting.weapons)) {
                weaponsZh = finalSetting.weapons.map(w => {
                    // 这里的 w 可能没有 name，继续防御
                    const wName = w.name || "Random";
                    return weaponDict[wName] || wName;
                });
            }

            return {
                no: "", 
                Start_time: formatToUTC8(node.startTime),
                End_time: formatToUTC8(node.endTime),
                Duration: getDuration(node.startTime, node.endTime),
                Is_Big_Run: isBigRun,
                Stage: stageDict[stageNameEn] || stageNameEn,
                King_Salmonid: bossDict[bossNameEn] || bossNameEn,
                Weapon: weaponsZh
            };
        };

        // 处理 Regular
        if (coopGroupingSchedule.regularSchedules?.nodes) {
            coopGroupingSchedule.regularSchedules.nodes.forEach(node => {
                const item = parseNode(node, "false");
                if (item) fetchedSchedules.push(item);
            });
        }

        // 处理 Big Run
        if (coopGroupingSchedule.bigRunSchedules?.nodes) {
            coopGroupingSchedule.bigRunSchedules.nodes.forEach(node => {
                const item = parseNode(node, "true");
                if (item) fetchedSchedules.push(item);
            });
        }

        // 过滤重叠
        const newItems = fetchedSchedules.filter(item => {
            return new Date(item.Start_time).getTime() > lastStartTimeMs;
        });

        if (newItems.length === 0) {
            console.log('没有发现比本地更新的场次。');
            return;
        }

        newItems.sort((a, b) => new Date(a.Start_time) - new Date(b.Start_time));
        newItems.forEach(item => {
            lastNo++;
            item.no = String(lastNo);
            localData.schedule.push(item);
        });

        fs.writeFileSync(SCHEDULE_FILE, JSON.stringify(localData, null, 4), 'utf-8');
        console.log(`成功！新增了 ${newItems.length} 条场次。目前总计: ${localData.schedule.length}`);

    } catch (error) {
        console.error('更新过程中发生严重错误:');
        console.error(error);
    }
}

updateSchedules();