#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
import os
from pathlib import Path

# ============ 在这里修改你要检查的文件路径 ============
JSON_FILE_PATH = "/Users/layla.zhang/Downloads/cards.json"  # 改成你的JSON文件路径
# ===================================================

def extract_filekey_from_string(text):
    """
    从字符串中提取filekey
    """
    patterns = [
        # 匹配 file-processing 或 file-processin 格式
        r'file-processin?g?/\d+/(?:cropped-)?images?/([^/\s"\']+\.(?:png|jpg|jpeg|gif|webp|svg))',
        # 匹配更通用的图片路径
        r'/\d+/(?:cropped-)?images?/[^/\s"\']+\.(?:png|jpg|jpeg|gif|webp|svg)',
    ]
    
    all_matches = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            all_matches.extend(matches)
    
    # 如果没有匹配到，尝试更宽松的匹配
    if not all_matches:
        loose_pattern = r'[a-zA-Z0-9\-_/]+/\d+/[a-zA-Z0-9\-_/]+\.(?:png|jpg|jpeg|gif|webp|svg)'
        matches = re.findall(loose_pattern, text, re.IGNORECASE)
        all_matches = matches
    
    return all_matches

def count_unique_filekeys(json_file_path):
    """
    统计JSON文件中不重复的图片filekey数量
    """
    # 检查文件是否存在
    if not Path(json_file_path).exists():
        print(f"❌ 错误: 文件 '{json_file_path}' 不存在")
        return None
    
    print(f"📁 正在读取文件: {json_file_path}")
    
    # 读取JSON文件
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"✅ JSON解析成功")
    except json.JSONDecodeError as e:
        print(f"❌ 错误: JSON解析失败 - {e}")
        return None
    except Exception as e:
        print(f"❌ 错误: 读取文件失败 - {e}")
        return None
    
    # 将JSON转为字符串以便搜索
    json_str = json.dumps(data, ensure_ascii=False)
    
    # 提取所有filekey
    all_filekeys = extract_filekey_from_string(json_str)
    
    # 去重并排序
    unique_filekeys = sorted(set(all_filekeys))
    
    # 统计结果
    total_count = len(all_filekeys)
    unique_count = len(unique_filekeys)
    
    # 显示结果
    print(f"\n{'='*60}")
    print(f"📊 统计结果")
    print(f"{'='*60}")
    print(f"📝 图片出现总次数: {total_count}")
    print(f"🆕 不重复图片数量: {unique_count}")
    print(f"{'='*60}\n")
    
    # 显示示例
    if unique_filekeys:
        print("📋 不重复图片列表:")
        for i, fk in enumerate(unique_filekeys, 1):
            # 只显示文件名
            filename = os.path.basename(fk)
            print(f"  {i:3d}. {filename}")
            # 如果想看完整路径，注释掉上面一行，取消下面注释
            # print(f"  {i:3d}. {fk}")
    else:
        print("⚠️  未找到任何图片文件")
    
    return {
        'total': total_count,
        'unique': unique_count,
        'filekeys': unique_filekeys
    }

if __name__ == "__main__":
    # 执行统计
    result = count_unique_filekeys(JSON_FILE_PATH)
    
    if result is not None:
        print(f"\n✅ 统计完成！共找到 {result['unique']} 个不重复的图片")