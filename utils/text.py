"""
文本处理工具函数

从 database.py 提取的文本处理逻辑。
"""

import re
from typing import List

try:
    import jieba
    import jieba.analyse

    HAS_JIEBA = True
except ImportError:
    HAS_JIEBA = False

# 正则模式
EN_WORD_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9]*")
NUM_PATTERN = re.compile(r"\d{2,}")
TIMESTAMP_PATTERN = re.compile(r"^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\s*\d{1,2}:\d{1,2}\s*")

# 中文停用词
_STOP_WORDS = frozenset(
    {
        "的", "了", "在", "是", "我", "你", "他", "她", "它", "们",
        "这", "那", "有", "和", "与", "也", "都", "又", "就", "但",
        "而", "或", "到", "被", "把", "让", "从", "对", "为", "以",
        "及", "等", "个", "不", "没", "很", "太", "吗", "呢", "吧",
        "啊", "嗯", "哦", "哈", "呀", "嘛", "么", "啦", "哇", "喔",
        "会", "能", "要", "想", "去", "来", "说", "做", "看", "给",
        "上", "下", "里", "中", "大", "小", "多", "少", "好", "可以",
        "什么", "怎么", "如何", "哪里", "哪个", "为什么", "还是", "然后",
        "因为", "所以", "虽然", "但是", "可以", "已经", "一个", "一些",
        "一下", "一点", "一起", "一样", "比较", "应该", "可能", "如果",
        "这个", "那个", "自己", "知道", "觉得", "感觉", "时候", "现在",
    }
)

# jieba 用户词典补充
if HAS_JIEBA:
    for _w in ["手账", "手帐", "搭子", "种草", "拔草", "安利", "内卷", "摆烂", "emo", "网关"]:
        jieba.add_word(_w)


def extract_search_keywords(query: str) -> List[str]:
    """
    从查询中提取搜索关键词（TF-IDF + 正则）

    1. 去掉开头的时间戳噪音
    2. 用 jieba.analyse.extract_tags (TF-IDF) 提取中文关键词
    3. 正则提取英文单词
    4. 保留4位以上数字（年份等，过滤短数字噪音）

    例如：
    "2026-05-02 20:26 写写手账看看书 放松大脑" → ["手账", "放松", "大脑"]
    "我昨天在手机上部署了Render然后吃了晚饭" → ["手机", "部署", "Render", "晚饭"]
    "春节干了什么" → ["春节"]
    "2026除夕"    → ["2026", "除夕"]
    """
    # 去掉时间戳前缀
    cleaned = TIMESTAMP_PATTERN.sub("", query).strip()
    if not cleaned:
        cleaned = query

    keywords = set()

    # 英文单词（2字符以上）
    for match in EN_WORD_PATTERN.finditer(cleaned):
        word = match.group()
        if len(word) >= 2:
            keywords.add(word)

    # 数字串（只保留4位以上，过滤 "05" "20" 这种时间噪音）
    for match in NUM_PATTERN.finditer(cleaned):
        num = match.group()
        if len(num) >= 4:
            keywords.add(num)

    # TF-IDF 关键词提取
    if HAS_JIEBA:
        tags = jieba.analyse.extract_tags(cleaned, topK=10)
        for tag in tags:
            # 跳过纯英文/数字（已在上面处理）
            if EN_WORD_PATTERN.fullmatch(tag) or NUM_PATTERN.fullmatch(tag):
                continue
            if tag in _STOP_WORDS:
                continue
            keywords.add(tag)

    return list(keywords)
