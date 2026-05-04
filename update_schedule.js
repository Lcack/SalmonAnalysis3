const fs = require('fs');
const path = require('path');

const DATA_DIR = path.join(__dirname, 'data');
const SCHEDULE_FILE = path.join(DATA_DIR, 'coop_schedule.json');
const STAGE_FILE = path.join(DATA_DIR, 'stage_data.json');
const BOSS_FILE = path.join(DATA_DIR, 'boss_data.json');
const WEAPON_FILE = path.join(DATA_DIR, 'weapon_data.json');
const BIGRUN_FILE = path.join(DATA_DIR, 'history_bigrun.json');
const EGGSTRA_FILE = path.join(DATA_DIR, 'history_EggstraWork.json');

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

function getLatestFromFile(filePath, arrayKey) {
    if (!fs.existsSync(filePath)) return { lastStartTimeMs: 0, lastNo: 0 };
    try {
        const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
        const items = data[arrayKey];
        if (!items || items.length === 0) return { lastStartTimeMs: 0, lastNo: 0 };
        const latest = items.reduce((prev, curr) => {
            return (new Date(curr.Start_time).getTime() > new Date(prev.Start_time).getTime()) ? curr : prev;
        });
        return {
            lastStartTimeMs: new Date(latest.Start_time).getTime(),
            lastNo: parseInt(latest.no) || 0
        };
    } catch (e) {
        return { lastStartTimeMs: 0, lastNo: 0 };
    }
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

        let totalNewRegular = 0;
        let totalNewBigRun = 0;
        let totalNewEggstra = 0;

        // ========== 1. 处理 Regular（常规场次）==========
        if (coopGroupingSchedule.regularSchedules?.nodes) {
            coopGroupingSchedule.regularSchedules.nodes.forEach(node => {
                const item = parseNode(node, "false");
                if (item) fetchedSchedules.push(item);
            });
        }

        const newRegularItems = fetchedSchedules.filter(item => {
            return new Date(item.Start_time).getTime() > lastStartTimeMs;
        });

        if (newRegularItems.length > 0) {
            newRegularItems.sort((a, b) => new Date(a.Start_time) - new Date(b.Start_time));
            newRegularItems.forEach(item => {
                lastNo++;
                item.no = String(lastNo);
                localData.schedule.push(item);
            });
            totalNewRegular = newRegularItems.length;
            console.log(`常规场次：新增 ${totalNewRegular} 条。`);
        } else {
            console.log('常规场次：没有发现比本地更新的场次。');
        }

        // ========== 2. 处理 Big Run ==========
        const bigRunInfo = getLatestFromFile(BIGRUN_FILE, 'bigrun');
        let lastBigRunNo = bigRunInfo.lastNo;
        const newBigRunItems = [];

        if (coopGroupingSchedule.bigRunSchedules?.nodes && coopGroupingSchedule.bigRunSchedules.nodes.length > 0) {
            coopGroupingSchedule.bigRunSchedules.nodes.forEach(node => {
                const item = parseNode(node, "true");
                if (item && new Date(item.Start_time).getTime() > bigRunInfo.lastStartTimeMs) {
                    newBigRunItems.push(item);
                }
            });

            if (newBigRunItems.length > 0) {
                newBigRunItems.sort((a, b) => new Date(a.Start_time) - new Date(b.Start_time));

                // 读取现有 bigrun 数据
                let bigRunData = { bigrun: [] };
                if (fs.existsSync(BIGRUN_FILE)) {
                    const content = fs.readFileSync(BIGRUN_FILE, 'utf-8');
                    if (content.trim()) bigRunData = JSON.parse(content);
                }

                newBigRunItems.forEach(item => {
                    // 写入 coop_schedule.json
                    lastNo++;
                    item.no = String(lastNo);
                    item.Duration = "48";
                    localData.schedule.push(item);

                    // 写入 history_bigrun.json
                    lastBigRunNo++;
                    bigRunData.bigrun.push({
                        no: String(lastBigRunNo),
                        Start_time: item.Start_time,
                        End_time: item.End_time,
                        Duration: "48",
                        Is_Big_Run: "true",
                        Stage: item.Stage,
                        King_Salmonid: item.King_Salmonid,
                        Weapon: item.Weapon,
                        Gold: 135,
                        Silver: 110,
                        Bronze: 85
                    });
                });

                fs.writeFileSync(BIGRUN_FILE, JSON.stringify(bigRunData, null, 4), 'utf-8');
                totalNewBigRun = newBigRunItems.length;
                console.log(`Big Run：新增 ${totalNewBigRun} 条（已同步更新 coop_schedule 和 history_bigrun）。`);
            } else {
                console.log('Big Run：没有发现比本地更新的场次。');
            }
        } else {
            console.log('Big Run：API 中无数据，跳过。');
        }

        // ========== 3. 处理 Team Contest（团队竞赛 / Eggstra Work）==========
        const eggstraInfo = getLatestFromFile(EGGSTRA_FILE, 'eggstrawork');
        let lastEggstraNo = eggstraInfo.lastNo;
        const newEggstraItems = [];

        if (coopGroupingSchedule.teamContestSchedules?.nodes && coopGroupingSchedule.teamContestSchedules.nodes.length > 0) {
            coopGroupingSchedule.teamContestSchedules.nodes.forEach(node => {
                if (!node || !node.startTime || !node.endTime) return;
                const startMs = new Date(node.startTime).getTime();
                if (startMs <= eggstraInfo.lastStartTimeMs) return;

                const finalSetting = node.setting || node;
                const stageNameEn = finalSetting.coopStage?.name || "Unknown";

                let weaponsZh = ["未知", "未知", "未知", "未知"];
                if (finalSetting.weapons && Array.isArray(finalSetting.weapons)) {
                    weaponsZh = finalSetting.weapons.map(w => {
                        const wName = w.name || "Random";
                        return weaponDict[wName] || wName;
                    });
                }

                newEggstraItems.push({
                    Start_time: formatToUTC8(node.startTime),
                    End_time: formatToUTC8(node.endTime),
                    Stage: stageDict[stageNameEn] || stageNameEn,
                    Weapon: weaponsZh
                });
            });

            if (newEggstraItems.length > 0) {
                newEggstraItems.sort((a, b) => new Date(a.Start_time) - new Date(b.Start_time));

                let eggstraData = { eggstrawork: [] };
                if (fs.existsSync(EGGSTRA_FILE)) {
                    const content = fs.readFileSync(EGGSTRA_FILE, 'utf-8');
                    if (content.trim()) eggstraData = JSON.parse(content);
                }

                newEggstraItems.forEach(item => {
                    lastEggstraNo++;
                    eggstraData.eggstrawork.push({
                        no: String(lastEggstraNo),
                        Start_time: item.Start_time,
                        End_time: item.End_time,
                        Duration: "48",
                        Stage: item.Stage,
                        Weapon: item.Weapon,
                        Gold: "",
                        Silver: "",
                        Bronze: ""
                    });
                });

                fs.writeFileSync(EGGSTRA_FILE, JSON.stringify(eggstraData, null, 4), 'utf-8');
                totalNewEggstra = newEggstraItems.length;
                console.log(`Team Contest：新增 ${totalNewEggstra} 条（已更新 history_EggstraWork）。`);
            } else {
                console.log('Team Contest：没有发现比本地更新的场次。');
            }
        } else {
            console.log('Team Contest：API 中无数据，跳过。');
        }

        // ========== 写入 coop_schedule.json ==========
        if (totalNewRegular > 0 || totalNewBigRun > 0) {
            fs.writeFileSync(SCHEDULE_FILE, JSON.stringify(localData, null, 4), 'utf-8');
        }

        // ========== 汇总 ==========
        const totalNew = totalNewRegular + totalNewBigRun + totalNewEggstra;
        if (totalNew === 0) {
            console.log('汇总：所有类型均无新场次，未进行任何更新。');
        } else {
            console.log(`汇总：成功更新！常规 +${totalNewRegular}，Big Run +${totalNewBigRun}，Team Contest +${totalNewEggstra}。coop_schedule 总计: ${localData.schedule.length}`);
        }

    } catch (error) {
        console.error('更新过程中发生严重错误:');
        console.error(error);
    }
}

updateSchedules();