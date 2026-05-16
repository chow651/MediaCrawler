# -*- coding: utf-8 -*-
"""
财经网红评论情绪分析脚本
"""

import json
from collections import Counter

# 读取评论数据
comments = []
with open('data/douyin/jsonl/search_comments_2026-05-09.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        try:
            comment = json.loads(line.strip())
            comments.append(comment)
        except:
            continue

print(f"总评论数: {len(comments)}")

# 关键词分类
stock_keywords = ['股票', 'A股', '大盘', '涨', '跌', '牛市', '熊市', '涨停', '跌停', '抄底', '割肉', '套牢', '解套', '板块', '热点', '龙头', '妖股']
emotion_positive = ['涨', '牛', '赚', '发财', '暴富', '翻倍', '起飞', '冲', '加仓', '满仓', '抄底']
emotion_negative = ['跌', '亏', '套', '割', '赔', '爆仓', '清仓', '跑', '撤', '坑']
hot_sectors = ['AI', '人工智能', '芯片', '半导体', '新能源', '锂电', '光伏', '白酒', '医药', '地产', '券商', '银行', '中字头', '国企', '央企', '军工', '汽车', '机器人']

# 分析评论
stock_comments = []
emotion_counts = Counter()
sector_counts = Counter()

for c in comments:
    content = c.get('content', '')

    # 检查是否包含股票相关关键词
    if any(kw in content for kw in stock_keywords):
        stock_comments.append(content)

    # 统计情绪
    for kw in emotion_positive:
        if kw in content:
            emotion_counts['positive'] += 1
            break
    for kw in emotion_negative:
        if kw in content:
            emotion_counts['negative'] += 1
            break

    # 统计板块
    for sector in hot_sectors:
        if sector in content:
            sector_counts[sector] += 1

print(f"\n=== 股票相关评论数: {len(stock_comments)} ===")
for i, c in enumerate(stock_comments[:30]):
    print(f"{i+1}. {c[:150]}")

print(f"\n=== 情绪统计 ===")
print(f"积极情绪: {emotion_counts.get('positive', 0)}")
print(f"消极情绪: {emotion_counts.get('negative', 0)}")

print(f"\n=== 板块热度统计 ===")
for sector, count in sector_counts.most_common(20):
    print(f"{sector}: {count}")

# 计算狂热风险
total_emotion = emotion_counts.get('positive', 0) + emotion_counts.get('negative', 0)
if total_emotion > 0:
    positive_ratio = emotion_counts.get('positive', 0) / total_emotion
    print(f"\n=== 狂热风险评估 ===")
    print(f"积极情绪占比: {positive_ratio:.2%}")
    if positive_ratio > 0.7:
        print("⚠️ 警告：积极情绪占比过高，存在狂热风险！")
    elif positive_ratio > 0.6:
        print("⚡ 注意：积极情绪偏高，需关注风险")
    else:
        print("✅ 正常：情绪处于合理区间")
