"""
Simple NLP Engine - Regex-based fallback
"""

from typing import Dict, Any, List
from loguru import logger
import re
from collections import Counter


class SimpleNLPEngine:
    """Simple regex-based NLP Engine (Always available)"""
    
    STOP_WORDS_EN = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'shall', 'of', 'to', 'in', 'for', 'on', 'with', 'at', 'by', 'from', 'and', 'or', 'but', 'if', 'then', 'else', 'when', 'up', 'out', 'about', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'between', 'under', 'again', 'further', 'once', 'here', 'there', 'all', 'each', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just', 'can', 'this', 'that', 'these', 'those', 'am', 'as', 'it', 'its', 'he', 'she', 'they', 'them', 'his', 'her', 'their', 'we', 'us', 'our', 'you', 'your', 'i', 'me', 'my'}
    STOP_WORDS_ZH = {'的', '了', '和', '是', '就', '都', '而', '及', '与', '着', '或', '一个', '没有', '我们', '你们', '他们', '她们', '它们', '这', '那', '这个', '那个', '这些', '那些', '有', '在', '不', '也', '很', '要', '会', '能', '可以', '但', '但是', '如果', '因为', '所以', '虽然', '然后', '还', '又', '再', '已经'}
    
    def __init__(self):
        self._ready = True
        logger.info("Simple NLP engine initialized")
    
    def is_ready(self) -> bool:
        return self._ready
    
    def get_name(self) -> str:
        return "SimpleNLP"
    
    async def extract_keywords(self, text: str, top_k: int = 10) -> List[Dict[str, Any]]:
        words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', text)
        stop_words = self.STOP_WORDS_EN | self.STOP_WORDS_ZH
        filtered_words = [w for w in words if w.lower() not in stop_words and len(w) >= 2]
        word_counts = Counter(filtered_words)
        total_words = len(filtered_words)
        unique_words = len(word_counts)
        keywords = []
        for word, count in word_counts.most_common(top_k):
            tf = count / total_words if total_words > 0 else 0
            idf = 1 + (1 / (count + 1))
            score = tf * idf
            keywords.append({
                "keyword": word,
                "score": round(score, 4),
                "frequency": count,
                "source": "simple"
            })
        return keywords
    
    async def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        entities = []
        emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        for email in emails:
            entities.append({"text": email, "label": "EMAIL", "label_description": "Email Address", "source": "regex"})
        phones = re.findall(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)
        for phone in phones:
            entities.append({"text": phone, "label": "PHONE", "label_description": "Phone Number", "source": "regex"})
        dates = re.findall(r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}', text)
        for date in dates:
            entities.append({"text": date, "label": "DATE", "label_description": "Date", "source": "regex"})
        money = re.findall(r'[\$€£¥]\s*[\d,]+\.?\d*|[\d,]+\.?\d*\s*(?:dollars?|euros?|pounds?|yuan|元|美元|欧元)', text, re.IGNORECASE)
        for m in money:
            entities.append({"text": m, "label": "MONEY", "label_description": "Monetary Value", "source": "regex"})
        percentages = re.findall(r'[\d.]+\s*%', text)
        for p in percentages:
            entities.append({"text": p, "label": "PERCENT", "label_description": "Percentage", "source": "regex"})
        urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', text)
        for url in urls:
            entities.append({"text": url, "label": "URL", "label_description": "URL", "source": "regex"})
        return entities
