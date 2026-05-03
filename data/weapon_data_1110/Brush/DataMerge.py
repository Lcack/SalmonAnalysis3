import json
import os
import copy

def deep_merge(base, override):
    for key, value in override.items():
        if isinstance(value, dict) and key in base and isinstance(base[key], dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base

def process_weapon_files():
    # --- 修改点：获取脚本所在的绝对路径 ---
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"当前扫描目录: {script_dir}")
    
    # 获取该目录下的所有 json 文件
    all_files = [f for f in os.listdir(script_dir) if f.endswith('.json')]
    
    # 筛选出所有含有 _Coop 的文件
    coop_files = [f for f in all_files if '_Coop.game__GameParameterTable.json' in f]

    if not coop_files:
        print("未在脚本目录下找到任何包含 '_Coop' 的 JSON 文件。")
        return

    for coop_file in coop_files:
        base_file = coop_file.replace('_Coop', '')
        
        # 构造完整路径进行读取
        coop_path = os.path.join(script_dir, coop_file)
        base_path = os.path.join(script_dir, base_file)
        
        target_name = ""
        result_data = None

        if base_file in all_files:
            print(f"正在合并: {base_file} + {coop_file}")
            try:
                with open(base_path, 'r', encoding='utf-8') as f:
                    base_data = json.load(f)
                with open(coop_path, 'r', encoding='utf-8') as f:
                    coop_data = json.load(f)

                merged_data = deep_merge(copy.deepcopy(base_data), coop_data)
                if '$parent' in merged_data:
                    del merged_data['$parent']

                result_data = merged_data
                target_name = f"Merge_{coop_file}"
            except Exception as e:
                print(f"处理文件 {coop_file} 时出错: {e}")

        elif "Bear" in coop_file:
            print(f"检测到 Bear 武器 (独立文件): {coop_file}")
            try:
                with open(coop_path, 'r', encoding='utf-8') as f:
                    result_data = json.load(f)
                target_name = f"Bear_{coop_file}"
            except Exception as e:
                print(f"读取 Bear 武器文件 {coop_file} 时出错: {e}")
        else:
            print(f"警告：找不到 {coop_file} 对应的原始文件 {base_file}，且非 Bear 系列。")

        # 写入新文件（同样写入到脚本所在目录）
        if target_name and result_data:
            target_path = os.path.join(script_dir, target_name)
            with open(target_path, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, indent=2, ensure_ascii=False)
            print(f"成功生成: {target_name}")

if __name__ == "__main__":
    process_weapon_files()