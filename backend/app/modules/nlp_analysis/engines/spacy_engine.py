"""
SpaCy NLP Engine
"""

from typing import Dict, Any, List
from loguru import logger
from collections import Counter


class SpaCyEngine:
    """Primary NLP Engine - spaCy"""
    
    def __init__(self, language: str = "en"):
        self._nlp = None
        self._ready = False
        self._language = language
        self._init_engine()
    
    def _init_engine(self):
        try:
            import spacy
            model_map = {
                "en": "en_core_web_sm",
                "zh": "zh_core_web_sm",
                "ch": "zh_core_web_sm",
                "de": "de_core_news_sm",
                "fr": "fr_core_news_sm",
                "es": "es_core_news_sm",
                "ja": "ja_core_news_sm"
            }
            model_name = model_map.get(self._language, "en_core_web_sm")
            try:
                self._nlp = spacy.load(model_name)
            except OSError:
                from spacy.cli import download
                download(model_name)
                self._nlp = spacy.load(model_name)
            self._ready = True
            logger.info(f"SpaCy engine initialized with model: {model_name}")
        except Exception as e:
            logger.warning(f"SpaCy initialization failed: {e}")
            self._ready = False
    
    def is_ready(self) -> bool:
        return self._ready
    
    def get_name(self) -> str:
        return "spaCy"
    
    async def extract_keywords(self, text: str, top_k: int = 10) -> List[Dict[str, Any]]:
        if not self._ready:
            raise RuntimeError("SpaCy engine not ready")
        doc = self._nlp(text)
        noun_chunks = [chunk.text.strip() for chunk in doc.noun_chunks if len(chunk.text.strip()) > 1]
        entities = [ent.text.strip() for ent in doc.ents]
        important_words = [token.text for token in doc if token.pos_ in ['NOUN', 'PROPN'] and len(token.text) > 1 and not token.is_stop]
        all_keywords = noun_chunks + entities + important_words
        keyword_counts = Counter(all_keywords)
        total = sum(keyword_counts.values())
        keywords = []
        for word, count in keyword_counts.most_common(top_k):
            keywords.append({
                "keyword": word,
                "score": round(count / total, 4) if total > 0 else 0,
                "frequency": count,
                "source": "spacy"
            })
        return keywords
    
    async def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        if not self._ready:
            raise RuntimeError("SpaCy engine not ready")
        import spacy
        doc = self._nlp(text)
        entities = []
        for ent in doc.ents:
            entities.append({
                "text": ent.text,
                "label": ent.label_,
                "label_description": spacy.explain(ent.label_) if hasattr(spacy, 'explain') else ent.label_,
                "start": ent.start_char,
                "end": ent.end_char,
                "source": "spacy"
            })
        return entities
