"""
NLP Service - Keyword Extraction and Named Entity Recognition
Primary: spaCy | Fallback: HanLP | Alternative: Simple Regex-based
"""

from typing import Dict, Any, List, Optional, Tuple
from abc import ABC, abstractmethod
from loguru import logger
import re
from collections import Counter


class BaseNLPEngine(ABC):
    """Abstract base class for NLP engines"""
    
    @abstractmethod
    def is_ready(self) -> bool:
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        pass
    
    @abstractmethod
    async def extract_keywords(self, text: str, top_k: int = 10) -> List[Dict[str, Any]]:
        pass
    
    @abstractmethod
    async def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        pass


class SpaCyEngine(BaseNLPEngine):
    """
    Primary NLP Engine - spaCy
    
    Advantages:
    - Fast and efficient
    - Good for NER and keyword extraction
    - Multi-language support
    - Well-documented API
    """
    
    def __init__(self, language: str = "en"):
        self._nlp = None
        self._ready = False
        self._language = language
        self._init_engine()
    
    def _init_engine(self):
        try:
            import spacy
            
            # Try to load language model
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
                # Try to download the model
                logger.info(f"Downloading spaCy model: {model_name}")
                from spacy.cli import download
                download(model_name)
                self._nlp = spacy.load(model_name)
            
            self._ready = True
            logger.info(f"spaCy engine initialized with model: {model_name}")
        except ImportError as e:
            logger.warning(f"spaCy not installed: {e}")
            self._ready = False
        except Exception as e:
            logger.warning(f"spaCy initialization failed: {e}")
            self._ready = False
    
    def is_ready(self) -> bool:
        return self._ready
    
    def get_name(self) -> str:
        return "spaCy"
    
    async def extract_keywords(self, text: str, top_k: int = 10) -> List[Dict[str, Any]]:
        if not self._ready:
            raise RuntimeError("spaCy engine not ready")
        
        doc = self._nlp(text)
        
        # Extract noun phrases and important words
        keywords = []
        
        # Get noun chunks
        noun_chunks = [chunk.text.strip() for chunk in doc.noun_chunks 
                       if len(chunk.text.strip()) > 1]
        
        # Get named entities
        entities = [ent.text.strip() for ent in doc.ents]
        
        # Get important nouns and proper nouns
        important_words = [token.text for token in doc 
                         if token.pos_ in ['NOUN', 'PROPN'] 
                         and len(token.text) > 1
                         and not token.is_stop]
        
        # Combine and count
        all_keywords = noun_chunks + entities + important_words
        keyword_counts = Counter(all_keywords)
        
        # Get top keywords with scores
        total = sum(keyword_counts.values())
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
            raise RuntimeError("spaCy engine not ready")
        
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


class HanLPEngine(BaseNLPEngine):
    """
    Fallback NLP Engine - HanLP
    
    Advantages:
    - Excellent Chinese language support
    - Full-featured NLP pipeline
    - Named Entity Recognition
    - Keyword extraction
    """
    
    def __init__(self):
        self._hanlp = None
        self._ready = False
        self._init_engine()
    
    def _init_engine(self):
        try:
            import hanlp
            
            # Load pre-trained pipeline
            self._hanlp = hanlp.load(hanlp.pretrained.mtl.CLOSE_TOK_POS_NER_SRL_DEP_SDP_CON_ELECTRA_SMALL_ZH)
            self._ready = True
            logger.info("HanLP engine initialized successfully")
        except ImportError as e:
            logger.warning(f"HanLP not installed: {e}")
            self._ready = False
        except Exception as e:
            logger.warning(f"HanLP initialization failed: {e}")
            self._ready = False
    
    def is_ready(self) -> bool:
        return self._ready
    
    def get_name(self) -> str:
        return "HanLP"
    
    async def extract_keywords(self, text: str, top_k: int = 10) -> List[Dict[str, Any]]:
        if not self._ready:
            raise RuntimeError("HanLP engine not ready")
        
        try:
            import hanlp
            
            # Use keyword extraction
            result = self._hanlp(text)
            
            keywords = []
            
            # Extract from NER results
            if 'ner/msra' in result:
                entities = result['ner/msra']
                for entity, label in entities:
                    keywords.append({
                        "keyword": entity,
                        "label": label,
                        "source": "hanlp_ner"
                    })
            
            # Extract nouns from POS tagging
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
                        keywords.append({
                            "keyword": word,
                            "frequency": count,
                            "source": "hanlp_pos"
                        })
            
            # Calculate scores
            total = sum(k.get('frequency', 1) for k in keywords)
            for kw in keywords:
                kw['score'] = round(kw.get('frequency', 1) / total, 4) if total > 0 else 0
            
            return keywords[:top_k]
            
        except Exception as e:
            logger.error(f"HanLP keyword extraction failed: {e}")
            raise
    
    async def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        if not self._ready:
            raise RuntimeError("HanLP engine not ready")
        
        try:
            result = self._hanlp(text)
            
            entities = []
            
            if 'ner/msra' in result:
                tokens = result['tok/fine']
                ner_results = result['ner/msra']
                
                for entity, label in ner_results:
                    entities.append({
                        "text": entity,
                        "label": label,
                        "label_description": self._get_label_description(label),
                        "source": "hanlp"
                    })
            
            return entities
            
        except Exception as e:
            logger.error(f"HanLP NER failed: {e}")
            raise
    
    def _get_label_description(self, label: str) -> str:
        """Get human-readable description for NER labels"""
        descriptions = {
            "PER": "Person",
            "LOC": "Location",
            "ORG": "Organization",
            "TIME": "Time",
            "DATE": "Date",
            "MONEY": "Money",
            "PERCENT": "Percentage",
            "QUANTITY": "Quantity"
        }
        return descriptions.get(label, label)


class SimpleNLPEngine(BaseNLPEngine):
    """
    Simple regex-based NLP Engine (Always available fallback)
    
    Uses basic text processing techniques:
    - TF-IDF inspired scoring
    - Regex-based entity extraction
    - Stop word filtering
    """
    
    # English stop words
    STOP_WORDS_EN = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'shall', 'of', 'to', 'in', 'for',
        'on', 'with', 'at', 'by', 'from', 'and', 'or', 'but', 'if', 'then',
        'else', 'when', 'up', 'out', 'about', 'into', 'through', 'during',
        'before', 'after', 'above', 'below', 'between', 'under', 'again',
        'further', 'once', 'here', 'there', 'all', 'each', 'few', 'more',
        'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
        'same', 'so', 'than', 'too', 'very', 'just', 'can', 'this', 'that',
        'these', 'those', 'am', 'as', 'it', 'its', 'he', 'she', 'they', 'them',
        'his', 'her', 'their', 'we', 'us', 'our', 'you', 'your', 'i', 'me', 'my'
    }
    
    # Chinese stop words (common)
    STOP_WORDS_ZH = {
        '的', '了', '和', '是', '就', '都', '而', '及', '与', '着',
        '或', '一个', '没有', '我们', '你们', '他们', '她们', '它们',
        '这', '那', '这个', '那个', '这些', '那些', '有', '在', '不',
        '也', '很', '要', '会', '能', '可以', '但', '但是', '如果',
        '因为', '所以', '虽然', '然后', '还', '又', '再', '已经'
    }
    
    def __init__(self):
        self._ready = True
        logger.info("Simple NLP engine initialized")
    
    def is_ready(self) -> bool:
        return self._ready
    
    def get_name(self) -> str:
        return "SimpleNLP"
    
    async def extract_keywords(self, text: str, top_k: int = 10) -> List[Dict[str, Any]]:
        # Extract words (English and Chinese)
        words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', text)
        
        # Filter stop words and short words
        stop_words = self.STOP_WORDS_EN | self.STOP_WORDS_ZH
        filtered_words = [
            w for w in words 
            if w.lower() not in stop_words and len(w) >= 2
        ]
        
        # Count word frequency
        word_counts = Counter(filtered_words)
        
        # Calculate TF-IDF inspired score
        total_words = len(filtered_words)
        unique_words = len(word_counts)
        
        keywords = []
        for word, count in word_counts.most_common(top_k):
            # Simple TF-IDF: tf * log(N/df) approximated
            tf = count / total_words if total_words > 0 else 0
            idf = 1 + (1 / (count + 1))  # Simplified IDF
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
        
        # Email pattern
        emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        for email in emails:
            entities.append({
                "text": email,
                "label": "EMAIL",
                "label_description": "Email Address",
                "source": "regex"
            })
        
        # Phone pattern (various formats)
        phones = re.findall(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)
        for phone in phones:
            entities.append({
                "text": phone,
                "label": "PHONE",
                "label_description": "Phone Number",
                "source": "regex"
            })
        
        # Date patterns
        dates = re.findall(
            r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}',
            text
        )
        for date in dates:
            entities.append({
                "text": date,
                "label": "DATE",
                "label_description": "Date",
                "source": "regex"
            })
        
        # Money patterns
        money = re.findall(
            r'[\$€£¥]\s*[\d,]+\.?\d*|[\d,]+\.?\d*\s*(?:dollars?|euros?|pounds?|yuan|元|美元|欧元)',
            text, re.IGNORECASE
        )
        for m in money:
            entities.append({
                "text": m,
                "label": "MONEY",
                "label_description": "Monetary Value",
                "source": "regex"
            })
        
        # Percentage
        percentages = re.findall(r'[\d.]+\s*%', text)
        for p in percentages:
            entities.append({
                "text": p,
                "label": "PERCENT",
                "label_description": "Percentage",
                "source": "regex"
            })
        
        # URL pattern
        urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', text)
        for url in urls:
            entities.append({
                "text": url,
                "label": "URL",
                "label_description": "URL",
                "source": "regex"
            })
        
        return entities


class NLPService:
    """
    NLP Service with multi-engine support
    
    Supports automatic fallback:
    1. spaCy (Primary - Recommended)
    2. HanLP (Fallback - Best for Chinese)
    3. SimpleNLP (Always available fallback)
    """
    
    def __init__(self, language: str = "en"):
        self.engines: Dict[str, BaseNLPEngine] = {}
        self.default_engine = "spacy"
        self._language = language
        self._init_engines()
    
    def _init_engines(self):
        """Initialize all available NLP engines"""
        # Primary: spaCy
        spacy_engine = SpaCyEngine(language=self._language)
        if spacy_engine.is_ready():
            self.engines["spacy"] = spacy_engine
        
        # Fallback: HanLP (especially for Chinese)
        if self._language in ["zh", "ch"]:
            hanlp_engine = HanLPEngine()
            if hanlp_engine.is_ready():
                self.engines["hanlp"] = hanlp_engine
        
        # Always available: Simple NLP
        self.engines["simple"] = SimpleNLPEngine()
        
        logger.info(f"Available NLP engines: {list(self.engines.keys())}")
    
    def is_ready(self) -> bool:
        """Check if any NLP engine is available"""
        return len(self.engines) > 0
    
    def get_available_engines(self) -> List[str]:
        """Get list of available engines"""
        return list(self.engines.keys())
    
    def get_engine(self, engine_name: Optional[str] = None) -> BaseNLPEngine:
        """Get specified engine or default/fallback"""
        if engine_name and engine_name in self.engines:
            return self.engines[engine_name]
        
        if self.default_engine in self.engines:
            return self.engines[self.default_engine]
        
        if self.engines:
            return list(self.engines.values())[0]
        
        raise RuntimeError("No NLP engine available")
    
    async def extract_keywords(
        self,
        text: str,
        top_k: int = 10,
        engine: Optional[str] = None,
        fallback: bool = True
    ) -> Dict[str, Any]:
        """
        Extract keywords from text
        
        Args:
            text: Input text
            top_k: Number of top keywords to return
            engine: Specific engine to use
            fallback: Whether to try fallback engines on failure
        
        Returns:
            Dictionary with keywords and metadata
        """
        engines_to_try = []
        
        if engine and engine in self.engines:
            engines_to_try.append(engine)
        else:
            for eng in ["spacy", "hanlp", "simple"]:
                if eng in self.engines:
                    engines_to_try.append(eng)
        
        last_error = None
        
        for eng_name in engines_to_try:
            try:
                eng = self.engines[eng_name]
                logger.info(f"Extracting keywords with {eng.get_name()}...")
                keywords = await eng.extract_keywords(text, top_k)
                
                return {
                    "keywords": keywords,
                    "engine_used": eng_name,
                    "count": len(keywords)
                }
            except Exception as e:
                logger.warning(f"{eng_name} failed: {e}")
                last_error = e
                if not fallback:
                    raise
        
        raise RuntimeError(f"All NLP engines failed. Last error: {last_error}")
    
    async def extract_entities(
        self,
        text: str,
        engine: Optional[str] = None,
        fallback: bool = True
    ) -> Dict[str, Any]:
        """
        Extract named entities from text
        
        Args:
            text: Input text
            engine: Specific engine to use
            fallback: Whether to try fallback engines on failure
        
        Returns:
            Dictionary with entities and metadata
        """
        engines_to_try = []
        
        if engine and engine in self.engines:
            engines_to_try.append(engine)
        else:
            for eng in ["spacy", "hanlp", "simple"]:
                if eng in self.engines:
                    engines_to_try.append(eng)
        
        last_error = None
        
        for eng_name in engines_to_try:
            try:
                eng = self.engines[eng_name]
                logger.info(f"Extracting entities with {eng.get_name()}...")
                entities = await eng.extract_entities(text)
                
                # Group entities by label
                grouped = {}
                for entity in entities:
                    label = entity["label"]
                    if label not in grouped:
                        grouped[label] = []
                    grouped[label].append(entity)
                
                return {
                    "entities": entities,
                    "grouped": grouped,
                    "engine_used": eng_name,
                    "count": len(entities)
                }
            except Exception as e:
                logger.warning(f"{eng_name} failed: {e}")
                last_error = e
                if not fallback:
                    raise
        
        raise RuntimeError(f"All NLP engines failed. Last error: {last_error}")
    
    async def analyze_text(
        self,
        text: str,
        top_k_keywords: int = 10,
        engine: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Full text analysis including keywords and entities
        
        Args:
            text: Input text
            top_k_keywords: Number of keywords
            engine: Specific engine to use
        
        Returns:
            Complete analysis result
        """
        keywords_result = await self.extract_keywords(text, top_k_keywords, engine)
        entities_result = await self.extract_entities(text, engine)
        
        return {
            "keywords": keywords_result["keywords"],
            "entities": entities_result["entities"],
            "entities_grouped": entities_result["grouped"],
            "engines_used": {
                "keywords": keywords_result["engine_used"],
                "entities": entities_result["engine_used"]
            },
            "statistics": {
                "keyword_count": len(keywords_result["keywords"]),
                "entity_count": len(entities_result["entities"]),
                "text_length": len(text),
                "word_count": len(text.split())
            }
        }

