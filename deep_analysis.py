# -*- coding: utf-8 -*-
"""
深度分析财经网红评论
"""

import json
from collections import Counter
import re

# 读取评论数据
comments = []
with open('data/douyin/jsonl/search_comments_2026-05-09.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        try:
            comment = json.loads(line.strip())
            comments.append(comment)
        except:
            continue

print(f"=" * 60)
print(f"📊 财经网红评论情绪分析报告")
print(f"=" * 60)
print(f"\n📅 分析日期: 2026-05-09")
print(f"📝 总评论数: {len(comments)}")

# 关键词分类
stock_keywords = ['股票', 'A股', '大盘', '涨', '跌', '牛市', '熊市', '涨停', '跌停', '抄底', '割肉', '套牢', '解套', '板块', '热点', '龙头', '妖股', '基金', '理财', '投资', '炒股', '散户', '主力', '庄家']
emotion_positive = ['涨', '牛', '赚', '发财', '暴富', '翻倍', '起飞', '冲', '加仓', '满仓', '抄底', '牛市', '涨停', '红', '阳线']
emotion_negative = ['跌', '亏', '套', '割', '赔', '爆仓', '清仓', '跑', '撤', '坑', '熊市', '跌停', '绿', '阴线', '跳水', '暴跌']
hot_sectors = ['AI', '人工智能', '芯片', '半导体', '新能源', '锂电', '光伏', '白酒', '医药', '地产', '券商', '银行', '中字头', '国企', '央企', '军工', '汽车', '机器人', '科技', '消费', '金融']

# 韭菜特征关键词
leek_keywords = ['抄底', '加仓', '满仓', '梭哈', 'all in', '发财', '暴富', '翻倍', '起飞', '冲', '牛市', '涨停', '稳赚', '必涨', '铁底', '黄金坑', '主力', '庄家', '机构', '游资']

# 分析评论
stock_comments = []
emotion_counts = Counter()
sector_counts = Counter()
leek_comments = []

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

    # 识别韭菜特征
    if any(kw in content.lower() for kw in leek_keywords):
        leek_comments.append(content)

print(f"\n{'=' * 60}")
print(f"📈 股票相关评论分析")
print(f"{'=' * 60}")
print(f"\n股票相关评论数: {len(stock_comments)} ({len(stock_comments)/len(comments)*100:.1f}%)")

print(f"\n{'=' * 60}")
print(f"😊 情绪分析")
print(f"{'=' * 60}")
total_emotion = emotion_counts.get('positive', 0) + emotion_counts.get('negative', 0)
print(f"\n积极情绪: {emotion_counts.get('positive', 0)} 次")
print(f"消极情绪: {emotion_counts.get('negative', 0)} 次")
if total_emotion > 0:
    positive_ratio = emotion_counts.get('positive', 0) / total_emotion
    print(f"积极情绪占比: {positive_ratio:.2%}")

print(f"\n{'=' * 60}")
print(f"🔥 板块热度统计")
print(f"{'=' * 60}")
if sector_counts:
    for sector, count in sector_counts.most_common(10):
        print(f"  {sector}: {count} 次")
else:
    print("  未检测到明确的板块提及")

print(f"\n{'=' * 60}")
print(f"🥬 韭菜特征分析")
print(f"{'=' * 60}")
print(f"\n具有韭菜特征的评论数: {len(leek_comments)} ({len(leek_comments)/len(comments)*100:.1f}%)")
if leek_comments:
    print(f"\n典型韭菜评论:")
    for i, c in enumerate(leek_comments[:10]):
        print(f"  {i+1}. {c[:100]}...")

print(f"\n{'=' * 60}")
print(f"⚠️ 狂热风险评估")
print(f"{'=' * 60}")
if total_emotion > 0:
    positive_ratio = emotion_counts.get('positive', 0) / total_emotion
    if positive_ratio > 0.7:
        print(f"\n🚨 高风险：积极情绪占比 {positive_ratio:.2%}，市场情绪过热！")
        print(f"   建议：谨慎追高，注意风险控制")
    elif positive_ratio > 0.6:
        print(f"\n⚡ 中等风险：积极情绪占比 {positive_ratio:.2%}，情绪偏乐观")
        print(f"   建议：保持理性，避免盲目跟风")
    else:
        print(f"\n✅ 正常：积极情绪占比 {positive_ratio:.2%}，情绪处于合理区间")
        print(f"   建议：可正常参与，但仍需注意个股风险")
else:
    print(f"\n⚠️ 样本不足，无法准确评估情绪")

print(f"\n{'=' * 60}")
print(f"📋 总结")
print(f"{'=' * 60}")
print(f"""
1. 财经网红评论区整体情绪偏{'乐观' if emotion_counts.get('positive', 0) > emotion_counts.get('negative', 0) else '悲观'}
2. 热门板块：{', '.join([s for s, _ in sector_counts.most_common(3)]) if sector_counts else '无明显热点'}
3. 韭菜特征比例：{len(leek_comments)/len(comments)*100:.1f}% {'（偏高，需警惕）' if len(leek_comments)/len(comments) > 0.1 else '（正常）'}
4. 整体狂热风险：{'高' if total_emotion > 0 and emotion_counts.get('positive', 0) / total_emotion > 0.7 else '中' if total_emotion > 0 and emotion_counts.get('positive', 0) / total_emotion > 0.6 else '低'}
""")
