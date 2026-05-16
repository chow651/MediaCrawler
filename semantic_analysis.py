# -*- coding: utf-8 -*-
"""
语义分析脚本 - 区分玩梗和真实情绪
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

# 严格财经关键词
strict_finance_keywords = ['股票', 'A股', '大盘', '涨', '跌', '牛市', '熊市', '涨停', '跌停', '抄底', '割肉', '套牢', '解套', '基金', '理财', '投资', '炒股', '散户', '主力', '庄家', '赚钱', '亏钱', '梭哈', '满仓', '加仓', '清仓', '接盘', '韭菜', '被割', '回本', '解套', '板块', '热点', '龙头', '妖股', '游资', '机构', '建仓', '减仓', '持仓', '仓位', '止损', '止盈', '浮盈', '浮亏', '被套', '深套', '割韭菜', '杀猪盘', '骗炮', '暴涨', '暴跌', '跳水', '拉升', '洗盘', '出货', '吸筹', '控盘']

# 筛选严格财经相关评论
strict_finance_comments = []
for c in comments:
    content = c.get('content', '')
    if any(kw in content for kw in strict_finance_keywords):
        strict_finance_comments.append(content)

# 分类函数
def classify_comment(comment):
    """分类评论：玩梗 vs 真实情绪"""

    # 玩梗特征
    joke_indicators = [
        '哈哈', '笑死', '笑哭', '捂脸', '呲牙', '偷笑', '尬笑',
        '不如', '不就得了', '我给大家讲个笑话',
        '为了涨粉', '财经圈福利', '今天性感漂亮', '今天发福利',
        '投资丸子妹', '我以为是木头呢',
    ]

    # 真实情绪特征
    real_emotion_indicators = [
        '亏', '套', '割', '赔', '血本无归', '被套', '深套',
        '赚钱了', '回本', '解套', '抄底', '加仓', '清仓',
        '游资', '机构', '主力', '散户', '韭菜',
        '牛市', '熊市', '涨停', '跌停',
        '持仓', '仓位', '止损', '止盈',
    ]

    # 检查是否是玩梗
    is_joke = False
    for indicator in joke_indicators:
        if indicator in comment:
            is_joke = True
            break

    # 检查是否包含真实情绪
    has_real_emotion = False
    for indicator in real_emotion_indicators:
        if indicator in comment:
            has_real_emotion = True
            break

    # 分类逻辑
    if is_joke and not has_real_emotion:
        return '玩梗'
    elif has_real_emotion and not is_joke:
        return '真实情绪'
    elif is_joke and has_real_emotion:
        return '混合'  # 既有梗又有真实情绪
    else:
        return '中性'

# 分类评论
joke_comments = []
real_emotion_comments = []
mixed_comments = []
neutral_comments = []

for comment in strict_finance_comments:
    category = classify_comment(comment)
    if category == '玩梗':
        joke_comments.append(comment)
    elif category == '真实情绪':
        real_emotion_comments.append(comment)
    elif category == '混合':
        mixed_comments.append(comment)
    else:
        neutral_comments.append(comment)

# 输出结果
print("=" * 70)
print("📊 财经评论语义分析报告")
print("=" * 70)
print(f"\n总评论数: {len(comments)}")
print(f"严格财经相关评论: {len(strict_finance_comments)}")
print()
print(f"玩梗评论: {len(joke_comments)} ({len(joke_comments)/len(strict_finance_comments)*100:.1f}%)")
print(f"真实情绪评论: {len(real_emotion_comments)} ({len(real_emotion_comments)/len(strict_finance_comments)*100:.1f}%)")
print(f"混合评论: {len(mixed_comments)} ({len(mixed_comments)/len(strict_finance_comments)*100:.1f}%)")
print(f"中性评论: {len(neutral_comments)} ({len(neutral_comments)/len(strict_finance_comments)*100:.1f}%)")

print(f"\n{'=' * 70}")
print("🎭 玩梗评论样本")
print(f"{'=' * 70}")
for i, c in enumerate(joke_comments[:10]):
    print(f"{i+1}. {c[:100]}")

print(f"\n{'=' * 70}")
print("😤 真实情绪评论样本")
print(f"{'=' * 70}")
for i, c in enumerate(real_emotion_comments[:10]):
    print(f"{i+1}. {c[:100]}")

print(f"\n{'=' * 70}")
print("🔥 混合评论样本（既有梗又有真实情绪）")
print(f"{'=' * 70}")
for i, c in enumerate(mixed_comments[:10]):
    print(f"{i+1}. {c[:100]}")

# 情绪分析
emotion_keywords = {
    '积极': ['涨', '牛', '赚', '发财', '暴富', '翻倍', '起飞', '冲', '加仓', '满仓', '抄底', '牛市', '涨停', '红', '阳线', '回本', '解套'],
    '消极': ['跌', '亏', '套', '割', '赔', '爆仓', '清仓', '跑', '撤', '坑', '熊市', '跌停', '绿', '阴线', '跳水', '暴跌', '被割', '韭菜'],
}

emotion_counts = Counter()
for comment in real_emotion_comments + mixed_comments:
    for emotion, keywords in emotion_keywords.items():
        for kw in keywords:
            if kw in comment:
                emotion_counts[emotion] += 1
                break

print(f"\n{'=' * 70}")
print("📈 真实情绪分析")
print(f"{'=' * 70}")
total_emotion = sum(emotion_counts.values())
print(f"\n积极情绪: {emotion_counts.get('积极', 0)} 次")
print(f"消极情绪: {emotion_counts.get('消极', 0)} 次")
if total_emotion > 0:
    positive_ratio = emotion_counts.get('积极', 0) / total_emotion
    print(f"积极情绪占比: {positive_ratio:.2%}")

    print(f"\n{'=' * 70}")
    print("⚠️ 狂热风险评估")
    print(f"{'=' * 70}")
    if positive_ratio > 0.7:
        print(f"\n🚨 高风险：积极情绪占比 {positive_ratio:.2%}，市场情绪过热！")
    elif positive_ratio > 0.6:
        print(f"\n⚡ 中等风险：积极情绪占比 {positive_ratio:.2%}，情绪偏乐观")
    else:
        print(f"\n✅ 正常：积极情绪占比 {positive_ratio:.2%}，情绪处于合理区间")
