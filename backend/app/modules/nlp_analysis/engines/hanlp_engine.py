"""
HanLP NLP Engine (Optional)
"""

from typing import Dict, Any, List
from loguru import logger
from collections import Counter


class HanLPEngine:
    """Fallback NLP Engine - HanLP (Best for Chinese)"""
    
    def __init__(self):
        self._hanlp = None
        self._ready = False
        self._init_engine()
    
    def _init_engine(self):
        try:
            import hanlp
            self._hanlp = hanlp.load(hanlp.pretrained.mtl.CLOSE_TOK_POS_NER_SRL_DEP_SDP_CON_ELECTRA_SMALL_ZH)
            self._ready = True
            logger.info("HanLP engine initialized successfully")
        except Exception as e:
            logger.debug(f"HanLP not available: {e}")
            self._ready = False
    
    def is_ready(self) -> bool:
        return self._ready
    
    def get_name(self) -> str:
        return "HanLP"
    
    async def extract_keywords(self, text: str, top_k: int = 10) -> List[Dict[str, Any]]:
        if not self._ready:
            raise RuntimeError("HanLP engine not ready")
        result = self._hanlp(text)
        keywords = []
        if 'ner/msra' in result:
            entities = result['ner/msra']
            for entity, label in entities:
                keywords.append({"keyword": entity, "label": label, "source": "hanlp_ner"})
        if 'pos/ctb' in result:
            tokens = result['tok/fine']
            pos_tags = result['pos/ctb']
            noun_tags = ['NN', 'NR', 'NT', 'NNS']
            word_counts = Counter()
            for token, pos in zip(tokens, pos_tags):
                if pos in noun_tags and len(token) > 1:
                    word_counts[token] += 1
            for word, count in word_counts.most_common(top_k):
                if not any(k['keyword'] == word for k in keywords):
                    keywords.append({"keyword": word, "frequency": count, "source": "hanlp_pos"})
        total = sum(k.get('frequency', 1) for k in keywords)
        for kw in keywords:
            kw['score'] = round(kw.get('frequency', 1) / total, 4) if total > 0 else 0
        return keywords[:top_k]
    
    async def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        if not self._ready:
            raise RuntimeError("HanLP engine not ready")
        result = self._hanlp(text)
        entities = []
        if 'ner/msra' in result:
            ner_results = result['ner/msra']
            for entity, label in ner_results:
                entities.append({
                    "text": entity,
                    "label": label,
                    "label_description": self._get_label_description(label),
                    "source": "hanlp"
                })
        return entities
    
    def _get_label_description(self, label: str) -> str:
        descriptions = {
            "PER": "Person", "LOC": "Location", "ORG": "Organization",
            "TIME": "Time", "DATE": "Date", "MONEY": "Money",
            "PERCENT": "Percentage", "QUANTITY": "Quantity"
        }
        return descriptions.get(label, label)
