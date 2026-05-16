# -*- coding: utf-8 -*-
"""
韭菜画像分析 - 基于 jiucai skill 框架
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

# 财经相关关键词
finance_keywords = ['股票', 'A股', '大盘', '涨', '跌', '牛市', '熊市', '涨停', '跌停', '抄底', '割肉', '套牢', '解套', '板块', '热点', '龙头', '妖股', '基金', '理财', '投资', '炒股', '散户', '主力', '庄家', '赚钱', '亏钱', '发财', '暴富', '翻倍', '梭哈', 'all in', '满仓', '加仓', '清仓', '割肉', '跑路', '撤退', '上车', '下车', '站岗', '接盘', '韭菜', '被割', '回本', '解套']

# 筛选财经相关评论
finance_comments = []
for c in comments:
    content = c.get('content', '')
    if any(kw in content for kw in finance_keywords):
        finance_comments.append(content)

# 韭菜模式分类
patterns = {
    # 认知层
    '锚定效应': ['之前', '本来', '原来', '以前', '历史', '高位', '低位', '高点', '低点'],
    '幸存者偏差': ['别人', '大家都', '听说', '看到', '赚到', '发财', '暴富', '翻倍'],
    '沉没成本谬误': ['坚持', '已经', '都', '这么久', '不能白', '回本', '解套'],
    '确定性幻觉': ['稳', '一定', '肯定', '必须', '肯定', '绝对', '稳赚', '铁定'],
    '近因偏误': ['最近', '这两天', '这几天', '这周', '这个月', '都在涨', '都在跌'],

    # 情绪层
    '追涨焦虑': ['怕错过', '赶紧', '马上', '快', '上车', '追', '冲', '梭哈', 'all in'],
    '损失厌恶': ['亏', '套', '割', '赔', '血本无归', '倾家荡产', '跳楼'],
    '面子驱动': ['面子', '别人', '怎么看', '丢人', '丢脸', '不能输', '不能亏'],
    '从众冲动': ['大家都', '都在', '跟', '一起', '组团', '抱团', '集体'],

    # 结构层
    '现金流错配': ['借钱', '贷款', '负债', '杠杆', '透支', '月供', '还款'],
    '博弈位置误判': ['主力', '庄家', '机构', '游资', '大户', '散户'],
    '机会成本盲区': ['时间', '精力', '机会', '错过', '耽误', '浪费'],
    '退出条件缺失': ['一直', '永远', '长期', '死拿', '不卖', '持有', '坚守'],
}

# 统计每种模式的出现次数
pattern_counts = Counter()
pattern_examples = {p: [] for p in patterns}

for comment in finance_comments:
    for pattern, keywords in patterns.items():
        for kw in keywords:
            if kw in comment:
                pattern_counts[pattern] += 1
                if len(pattern_examples[pattern]) < 3:
                    pattern_examples[pattern].append(comment[:100])
                break

# 输出分析结果
print("=" * 70)
print("📊 抖音财经网红评论区 - 韭菜画像分析报告")
print("=" * 70)
print(f"\n📅 分析日期: 2026-05-09")
print(f"📝 总评论数: {len(comments)}")
print(f"📈 财经相关评论: {len(finance_comments)} ({len(finance_comments)/len(comments)*100:.1f}%)")

print(f"\n{'=' * 70}")
print("🧠 认知层韭菜模式")
print(f"{'=' * 70}")

cognitive_patterns = ['锚定效应', '幸存者偏差', '沉没成本谬误', '确定性幻觉', '近因偏误']
for p in cognitive_patterns:
    count = pattern_counts.get(p, 0)
    if count > 0:
        print(f"\n【{p}】出现 {count} 次")
        for ex in pattern_examples[p]:
            print(f"  • {ex}...")

print(f"\n{'=' * 70}")
print("😤 情绪层韭菜模式")
print(f"{'=' * 70}")

emotion_patterns = ['追涨焦虑', '损失厌恶', '面子驱动', '从众冲动']
for p in emotion_patterns:
    count = pattern_counts.get(p, 0)
    if count > 0:
        print(f"\n【{p}】出现 {count} 次")
        for ex in pattern_examples[p]:
            print(f"  • {ex}...")

print(f"\n{'=' * 70}")
print("🏗️ 结构层韭菜模式")
print(f"{'=' * 70}")

structure_patterns = ['现金流错配', '博弈位置误判', '机会成本盲区', '退出条件缺失']
for p in structure_patterns:
    count = pattern_counts.get(p, 0)
    if count > 0:
        print(f"\n【{p}】出现 {count} 次")
        for ex in pattern_examples[p]:
            print(f"  • {ex}...")

# 计算综合韭菜指数
total_patterns = sum(pattern_counts.values())
max_possible = len(finance_comments) * len(patterns)
leek_index = total_patterns / max_possible * 100 if max_possible > 0 else 0

print(f"\n{'=' * 70}")
print("📊 综合韭菜指数")
print(f"{'=' * 70}")
print(f"\n模式命中总次数: {total_patterns}")
print(f"理论最大命中: {max_possible}")
print(f"韭菜指数: {leek_index:.2f}%")

if leek_index > 30:
    print(f"\n🚨 高风险：韭菜特征明显，市场情绪过热！")
elif leek_index > 20:
    print(f"\n⚡ 中等风险：韭菜特征偏高，需警惕非理性行为")
elif leek_index > 10:
    print(f"\n⚠️ 低风险：存在一定韭菜特征，整体可控")
else:
    print(f"\� 正常：韭菜特征不明显，市场情绪理性")

print(f"\n{'=' * 70}")
print("🎯 典型韭菜画像")
print(f"{'=' * 70}")

# 提取典型韭菜评论
leek_keywords = ['梭哈', 'all in', '满仓', '抄底', '稳赚', '必涨', '铁底', '黄金坑', '发财', '暴富', '翻倍', '涨停']
leek_comments = [c for c in finance_comments if any(kw in c.lower() for kw in leek_keywords)]

print(f"\n典型韭菜评论数: {len(leek_comments)}")
print(f"\n典型韭菜评论:")
for i, c in enumerate(leek_comments[:15]):
    print(f"  {i+1}. {c[:120]}...")

print(f"\n{'=' * 70}")
print("💡 纠偏建议")
print(f"{'=' * 70}")
print("""
1. 认知层纠偏：
   • 警惕锚定效应：不要用过去的价格判断当前价值
   • 破除幸存者偏差：关注失败案例，不只是成功故事
   • 避免沉没成本谬误：已经亏损不是继续持有的理由
   • 打破确定性幻觉：没有稳赚不赔的投资
   • 克服近因偏误：短期波动不代表长期趋势

2. 情绪层纠偏：
   • 控制追涨焦虑：错过机会比高位接盘损失更小
   • 克服损失厌恶：及时止损，避免越套越深
   • 摆脱面子驱动：投资决策不受他人评价影响
   • 避免从众冲动：独立思考，不盲目跟风

3. 结构层纠偏：
   • 匹配现金流：不要借钱炒股，不要透支未来
   • 认清博弈位置：散户不是主力的对手，要认清现实
   • 计算机会成本：时间和精力也是成本
   • 设定退出条件：知道何时止盈，何时止损
""")
