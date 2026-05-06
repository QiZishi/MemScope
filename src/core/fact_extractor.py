"""Fact Extraction Engine for MemScope Memory System.

Extracts structured facts from conversation text and stores them as
decisions, preferences, and knowledge health entries.

This is NOT RAG — it extracts semantic facts, not just stores text.
"""

import re
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class FactExtractor:
    """Extract structured facts from conversation messages.
    
    Three fact types:
    1. DECISION: "我们决定用React" → decision(title="技术选型: React", chosen="React")
    2. PREFERENCE: "我喜欢用VS Code" → preference(category="tool", key="editor", value="VS Code")
    3. KNOWLEDGE: "项目用的是PostgreSQL" → knowledge(topic="数据库", source="对话")
    """

    # Decision signal patterns (Chinese)
    DECISION_SIGNALS_ZH = [
        r'(?:我们|团队|大家)(?:决定|确认|选定|敲定|采用|定|同意)',
        r'(?:最终|最后)(?:决定|确认|选定|定|选择)',
        r'(?:经过|根据).*(?:讨论|评估|对比|分析).*(?:决定|确认|选定)',
        r'(?:就|那就)(?:定|用|选|确认|采用)',
        r'(?:结论|总结|决议)(?:是|：)',
        r'(?:确认|决定|选定|敲定|采用|定)(?:了|使用|用|为)',
        r'(?:投票|表决).*(?:通过|通过了)',
        r'(?:统一|规范化?)(?:使用|采用)',
        r'(?:切换|迁移|升级)(?:到|为|至)',
        r'(?:废弃|淘汰|下线)(?:了)?',
        r'(?:推迟|延期|延后)',
        r'(?:采用|使用|选定|确认)(?:了)?',
    ]

    # Decision signal patterns (English)
    DECISION_SIGNALS_EN = [
        r'(?:we|team|everyone)\s+(?:decided|confirmed|agreed|chose|picked)',
        r'(?:final|ultimately)\s+(?:decision|choice)',
        r'(?:approved|rejected|postponed)',
        r'(?:migrated?|switched?|upgraded?)\s+(?:to|from)',
        r'(?:deprecated|sunset|retired?)',
        r'(?:unified|standardized?)\s+(?:on|to)',
    ]

    # Preference signal patterns
    PREFERENCE_SIGNALS_ZH = [
        r'(?:我|我们)(?:喜欢|偏好|倾向|习惯|常用|爱用|一般用|总是用)',
        r'(?:更喜欢|更倾向于|更习惯)',
        r'(?:推荐|建议)(?:用|使用)',
        r'(?:不要|别|不想)(?:用|使用)',
        r'(?:偏好|首选|默认)(?:是|用|使用)',
    ]

    PREFERENCE_SIGNALS_EN = [
        r'(?:I|we)\s+(?:prefer|like|love|use|always use|tend to)',
        r'(?:my|our)\s+(?:preference|favorite|default)',
        r'(?:recommend|suggest)\s+(?:using|to use)',
        r'(?:don\'t|do not)\s+(?:like|prefer|use)',
    ]

    # Knowledge signal patterns (factual statements)
    KNOWLEDGE_SIGNALS_ZH = [
        r'(?:项目|系统|服务|应用)(?:用的是|使用的是|基于|采用的是|运行在)',
        r'(?:数据库|框架|语言|工具)(?:是|为|用的是|用|使用)',
        r'(?:部署在|运行在|托管在|放在)',
        r'(?:版本|ver)(?:是|为|=)',
        r'(?:配置|设置)(?:为|是|=)',
        r'(?:用|使用)\s*(?:的是)?\s*(?:PostgreSQL|MySQL|MongoDB|Redis|Docker|K8s|AWS|Azure|GCP)',
    ]

    KNOWLEDGE_SIGNALS_EN = [
        r'(?:project|system|service|app)\s+(?:uses|is based on|runs on)',
        r'(?:database|framework|language|tool)\s+(?:is|=)',
        r'(?:deployed?|hosted?|running)\s+(?:on|in|at)',
        r'(?:version|ver)\s+(?:is|=)',
    ]

    # Common tech terms for extraction
    TECH_TERMS = [
        'React', 'Vue', 'Angular', 'Next.js', 'Nuxt', 'Svelte',
        'Python', 'Java', 'Go', 'Rust', 'TypeScript', 'JavaScript', 'C++', 'C#',
        'PostgreSQL', 'MySQL', 'MongoDB', 'Redis', 'Elasticsearch', 'SQLite',
        'Docker', 'Kubernetes', 'K8s', 'AWS', 'Azure', 'GCP',
        'RabbitMQ', 'Kafka', 'Nginx', 'Apache', 'gRPC', 'GraphQL',
        'Git', 'Jenkins', 'GitHub', 'GitLab', 'CI/CD',
        'React Native', 'Flutter', 'Swift', 'Kotlin',
        'TensorFlow', 'PyTorch', 'Scikit-learn', 'Pandas',
        'Linux', 'Ubuntu', 'CentOS', 'Debian',
    ]

    def __init__(self, store):
        self.store = store

    def extract_from_text(
        self,
        text: str,
        owner: str = "default",
        source: str = "conversation",
        timestamp_ms: Optional[int] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Extract all facts from a text block.
        
        Returns:
            Dict with keys: 'decisions', 'preferences', 'knowledge'
            Each contains a list of extracted fact dicts.
        """
        ts = timestamp_ms or int(time.time() * 1000)
        
        results = {
            "decisions": [],
            "preferences": [],
            "knowledge": [],
        }

        # Extract decisions
        decisions = self._extract_decisions(text, owner, source, ts)
        results["decisions"] = decisions

        # Extract preferences
        preferences = self._extract_preferences(text, owner, source, ts)
        results["preferences"] = preferences

        # Extract knowledge
        knowledge = self._extract_knowledge(text, owner, source, ts)
        results["knowledge"] = knowledge

        return results

    def extract_and_store(
        self,
        text: str,
        owner: str = "default",
        source: str = "conversation",
        timestamp_ms: Optional[int] = None,
        detect_contradictions: bool = True,
    ) -> Dict[str, Any]:
        """Extract facts from text AND store them with contradiction detection.
        
        This is the main entry point for the memory pipeline.
        
        Returns:
            Dict with extraction results and contradiction info.
        """
        ts = timestamp_ms or int(time.time() * 1000)
        
        # Extract facts
        facts = self.extract_from_text(text, owner, source, ts)
        
        stored = {"decisions": [], "preferences": [], "knowledge": [], "contradictions": []}

        # Store decisions
        for decision in facts["decisions"]:
            if detect_contradictions:
                contradiction = self._check_decision_contradiction(decision, owner)
                if contradiction:
                    # Mark old decision as superseded
                    self.store.update_decision(contradiction["id"], {
                        "status": "superseded",
                        "outcome": f"Superseded by: {decision['title']}",
                    })
                    stored["contradictions"].append({
                        "type": "decision",
                        "old_id": contradiction["id"],
                        "old_title": contradiction["title"],
                        "new_title": decision["title"],
                    })

            did = self.store.insert_decision(
                owner=owner,
                title=decision["title"],
                project=decision.get("project"),
                context=decision.get("context"),
                chosen=decision["chosen"],
                alternatives=decision.get("alternatives"),
                tags=decision.get("tags"),
            )
            if did:
                stored["decisions"].append({"id": did, **decision})

        # Store preferences
        for pref in facts["preferences"]:
            if detect_contradictions:
                contradiction = self._check_preference_contradiction(pref, owner)
                if contradiction:
                    stored["contradictions"].append({
                        "type": "preference",
                        "category": pref["category"],
                        "key": pref["key"],
                        "old_value": contradiction["value"],
                        "new_value": pref["value"],
                    })

            pid = self.store.upsert_preference(
                owner=owner,
                category=pref["category"],
                key=pref["key"],
                value=pref["value"],
                confidence=pref.get("confidence", 0.8),
                source=source,
            )
            if pid:
                stored["preferences"].append({"id": pid, **pref})

        # Store knowledge
        for kn in facts["knowledge"]:
            if detect_contradictions:
                contradiction = self._check_knowledge_contradiction(kn, owner)
                if contradiction:
                    stored["contradictions"].append({
                        "type": "knowledge",
                        "topic": kn["topic"],
                        "old_value": contradiction.get("source", "unknown"),
                        "new_value": kn.get("value", ""),
                    })

            kid = self.store.upsert_knowledge_health(
                owner=owner,
                topic=kn["topic"],
                source=source,
                freshness_score=1.0,
                accuracy_score=1.0,
                completeness_score=kn.get("completeness", 0.8),
            )
            if kid:
                stored["knowledge"].append({"id": kid, **kn})

        return stored

    def _extract_decisions(
        self, text: str, owner: str, source: str, ts: int
    ) -> List[Dict[str, Any]]:
        """Extract decision facts from text."""
        decisions = []
        
        # Check for decision signals
        has_signal = False
        for pattern in self.DECISION_SIGNALS_ZH + self.DECISION_SIGNALS_EN:
            if re.search(pattern, text, re.IGNORECASE):
                has_signal = True
                break
        
        if not has_signal:
            return decisions

        # Extract tech terms as chosen/alternatives
        found_terms = []
        for term in self.TECH_TERMS:
            if term.lower() in text.lower():
                found_terms.append(term)

        # Try to extract the decision title and chosen option
        # Pattern: "决定/确认/选定 + X" - prefer shorter, cleaner extractions
        decision_patterns = [
            r'(?:决定|确认|选定|敲定|采用|定|用)(?:了|使用|用)?\s*(\w{2,15}?)(?:[，。,.]|$)',
            r'(?:decided|confirmed|chose|picked)\s+(?:to\s+)?(?:use\s+)?(\w{2,15}?)(?:[,.]|$)',
            r'(?:那就|就)\s*(?:定|用|选)\s*(\w{2,15}?)(?:[，。,.]|$)',
            r'(?:切换到|迁移到|升级到|换成)\s*(\w{2,15}?)(?:[，。,.]|$)',
            r'(?:switched?|migrated?|upgraded?)\s+(?:to\s+)?(\w{2,15}?)(?:[,.]|$)',
        ]

        chosen = None
        for pattern in decision_patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                chosen = m.group(1).strip()
                break

        # If no specific chosen found, use first tech term
        if not chosen and found_terms:
            chosen = found_terms[0]

        # Clean up chosen - extract just the tech term if possible
        if chosen:
            # If chosen contains a known tech term, use just that term
            for term in found_terms:
                if term.lower() in chosen.lower():
                    chosen = term
                    break
            # If chosen is still long, try to extract the last meaningful word
            if len(chosen) > 20:
                words = re.findall(r'[\w\u4e00-\u9fff]+', chosen)
                if words:
                    chosen = words[-1]
            
            # Build title from TOPIC (not from chosen value) for contradiction detection
            # e.g., '前端框架: React' -> title='前端框架', chosen='React'
            topic = self._extract_decision_topic(text, found_terms)
            title = topic
            alternatives = [t for t in found_terms if t != chosen]
            
            decisions.append({
                "title": title,
                "chosen": chosen,
                "alternatives": ", ".join(alternatives[:3]) if alternatives else None,
                "context": text[:200],
                "project": self._extract_project(text),
                "tags": "auto_extracted",
            })

        return decisions

    def _extract_preferences(
        self, text: str, owner: str, source: str, ts: int
    ) -> List[Dict[str, Any]]:
        """Extract preference facts from text."""
        preferences = []
        
        # Check for preference signals
        has_signal = False
        for pattern in self.PREFERENCE_SIGNALS_ZH + self.PREFERENCE_SIGNALS_EN:
            if re.search(pattern, text, re.IGNORECASE):
                has_signal = True
                break
        
        if not has_signal:
            return preferences

        # Extract the preferred item
        pref_patterns = [
            r'(?:喜欢|偏好|倾向|习惯|常用|爱用|一般用|总是用|首选)\s*(?:用|使用)?\s*(.{2,30}?)(?:[，。,.]|$)',
            r'(?:更喜欢|更倾向于|更习惯)\s*(?:用|使用)?\s*(.{2,30}?)(?:[，。,.]|$)',
            r'(?:prefer|like|love|use|always use)\s+(.{2,30}?)(?:[,.]|$)',
            r'(?:不要|别|不想)\s*(?:用|使用)\s*(.{2,30}?)(?:[，。,.]|$)',
        ]

        value = None
        is_negative = False
        for pattern in pref_patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                value = m.group(1).strip()
                if '不要' in text or '别' in text or "don't" in text.lower():
                    is_negative = True
                break

        if value:
            # Determine category and topic-based key
            category = self._categorize_preference(value, text)
            # Use topic-based key so contradictions can be detected
            # e.g., 'React' and 'Vue' both get key='前端框架' under category='framework'
            topic_key = self._get_preference_topic_key(category, value, text)
            
            preferences.append({
                "category": category,
                "key": topic_key,
                "value": value,  # Store the actual value (e.g., 'React')
                "confidence": 0.8,
            })

        return preferences

    def _extract_knowledge(
        self, text: str, owner: str, source: str, ts: int
    ) -> List[Dict[str, Any]]:
        """Extract knowledge facts from text."""
        knowledge = []
        
        # Check for knowledge signals
        has_signal = False
        for pattern in self.KNOWLEDGE_SIGNALS_ZH + self.KNOWLEDGE_SIGNALS_EN:
            if re.search(pattern, text, re.IGNORECASE):
                has_signal = True
                break
        
        if not has_signal:
            return knowledge

        # Extract tech stack knowledge
        tech_patterns = [
            (r'(?:数据库|database)\s*(?:是|=|:|：)\s*(\w+)', 'database'),
            (r'(?:框架|framework)\s*(?:是|=|:|：)\s*(\w+)', 'framework'),
            (r'(?:语言|language)\s*(?:是|=|:|：)\s*(\w+)', 'language'),
            (r'(?:部署在|运行在|deployed?|running)\s+(?:on\s+)?(\w+)', 'infrastructure'),
            (r'(?:版本|version|ver)\s*(?:是|=|:|：)\s*([\d.]+\w*)', 'version'),
        ]

        for pattern, topic_type in tech_patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                value = m.group(1).strip()
                knowledge.append({
                    "topic": f"{topic_type}:{value}",
                    "value": value,
                    "type": topic_type,
                    "completeness": 0.8,
                })

        # Also extract general "用的是" patterns (and shorter variants)
        uses_patterns = [
            r'(?:用的是|使用的是|基于|采用的是)\s*(.{2,30}?)(?:[，。,.]|$)',
            r'(?:数据库|database)\s*(?:用|使用)\s*(\w+)',
            r'(?:框架|framework)\s*(?:用|使用)\s*(\w+)',
            r'(?:部署|deploy)\s*(?:在|到)\s*(\w+)',
            r'(?:用|使用)\s*(PostgreSQL|MySQL|MongoDB|Redis|Docker|K8s|AWS|Azure|GCP)(?:[，。,.\s]|$)',
        ]
        for pattern in uses_patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                value = m.group(1).strip()
                # Determine topic type from context
                topic_type = 'tech_stack'
                if re.search(r'数据库|database|DB', text, re.IGNORECASE):
                    topic_type = 'database'
                elif re.search(r'框架|framework', text, re.IGNORECASE):
                    topic_type = 'framework'
                elif re.search(r'部署|deploy|云|cloud', text, re.IGNORECASE):
                    topic_type = 'infrastructure'
                
                knowledge.append({
                    "topic": f"{topic_type}:{value}",
                    "value": value,
                    "type": topic_type,
                    "completeness": 0.7,
                })
                break  # Only match the first pattern

        return knowledge

    def _check_decision_contradiction(
        self, new_decision: Dict[str, Any], owner: str
    ) -> Optional[Dict[str, Any]]:
        """Check if new decision contradicts an existing one.
        
        Contradiction: same project/topic but different chosen option.
        Uses multiple matching strategies: project, title similarity, keyword overlap.
        """
        # Strategy 1: Search by title keywords
        title_keywords = new_decision.get("title", "").split(":")[-1].split("：")[-1].strip()[:15]
        existing = self.store.search_decisions(owner=owner, query=title_keywords, limit=10)
        
        # Strategy 2: Search by chosen option
        chosen = new_decision.get("chosen", "")
        if chosen:
            chosen_results = self.store.search_decisions(owner=owner, query=chosen, limit=10)
            for r in chosen_results:
                if r not in existing:
                    existing.append(r)
        
        # Strategy 3: Search by project
        project = new_decision.get("project")
        if project:
            proj_results = self.store.search_decisions(owner=owner, project=project, limit=10)
            for r in proj_results:
                if r not in existing:
                    existing.append(r)
        
        for old in existing:
            if old.get("status") == "superseded":
                continue
            
            # Same project, different choice = contradiction
            if (old.get("project") and new_decision.get("project") 
                and old["project"] == new_decision["project"]
                and old.get("chosen") != new_decision.get("chosen")):
                return old
            
            # Title similarity > 40% = likely same topic (lowered threshold)
            sim = self._title_similarity(old.get("title", ""), new_decision.get("title", ""))
            if sim > 0.4:
                if old.get("chosen") != new_decision.get("chosen"):
                    return old
            
            # Keyword overlap in context (same domain, different choice)
            old_ctx = set(re.findall(r'[\w\u4e00-\u9fff]+', (old.get("context", "") + old.get("title", "")).lower()))
            new_ctx = set(re.findall(r'[\w\u4e00-\u9fff]+', (new_decision.get("context", "") + new_decision.get("title", "")).lower()))
            overlap = old_ctx & new_ctx
            # Remove common stop words from overlap
            stop_words = {'的', '是', '在', '了', '和', '与', '或', '我们', '决定', '确认', '选定'}
            meaningful_overlap = overlap - stop_words
            if len(meaningful_overlap) >= 2:
                if old.get("chosen") and new_decision.get("chosen") and old["chosen"] != new_decision["chosen"]:
                    return old
        
        return None

    def _check_preference_contradiction(
        self, new_pref: Dict[str, Any], owner: str
    ) -> Optional[Dict[str, Any]]:
        """Check if new preference contradicts an existing one."""
        existing = self.store.get_preference(
            owner=owner,
            category=new_pref["category"],
            key=new_pref["key"],
        )
        
        if existing and existing.get("value") != new_pref.get("value"):
            return existing
        return None

    def _check_knowledge_contradiction(
        self, new_kn: Dict[str, Any], owner: str
    ) -> Optional[Dict[str, Any]]:
        """Check if new knowledge contradicts existing knowledge."""
        existing = self.store.get_knowledge_health(
            owner=owner,
            topic=new_kn["topic"],
        )
        
        if existing and existing.get("source") != new_kn.get("value"):
            return existing
        return None

    def _extract_decision_topic(self, text: str, found_terms: List[str]) -> str:
        """Extract the TOPIC of a decision (not the chosen value).
        
        Examples:
            '我们决定用React作为前端框架' -> '前端框架选择'
            '数据库选定PostgreSQL' -> '数据库选型'
            '部署在AWS上' -> '部署方案'
        """
        topic_patterns = [
            (r'(?:前端|前端框架|UI框架|界面框架)', '前端框架选择'),
            (r'(?:后端|后端框架|服务端框架)', '后端框架选择'),
            (r'(?:数据库|DB|数据存储)', '数据库选型'),
            (r'(?:部署|部署方案|部署平台|云平台)', '部署方案'),
            (r'(?:消息队列|MQ|消息中间件)', '消息队列选型'),
            (r'(?:缓存|缓存方案|缓存系统)', '缓存方案'),
            (r'(?:容器|容器化|编排)', '容器化方案'),
            (r'(?:监控|监控系统|监控方案)', '监控方案'),
            (r'(?:CI/CD|持续集成|持续部署|流水线)', 'CI/CD方案'),
            (r'(?:框架|framework)', '框架选择'),
            (r'(?:工具|tool)', '工具选择'),
            (r'(?:技术选型|技术方案|技术栈)', '技术选型'),
            (r'(?:deadline|截止日期|交付日期|时间)', '时间安排'),
            (r'(?:负责人|owner|对接人)', '人员安排'),
            (r'(?:优先级|priority)', '优先级'),
        ]
        
        for pattern, topic in topic_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return topic
        
        # Fallback: use found terms to infer topic
        if found_terms:
            term = found_terms[0].lower()
            for tech, cat in [
                (['react', 'vue', 'angular', 'svelte', 'next.js', 'nuxt'], '前端框架选择'),
                (['django', 'flask', 'fastapi', 'spring', 'express'], '后端框架选择'),
                (['postgresql', 'mysql', 'mongodb', 'redis', 'sqlite'], '数据库选型'),
                (['docker', 'kubernetes', 'k8s'], '容器化方案'),
                (['aws', 'azure', 'gcp'], '部署方案'),
                (['jenkins', 'gitlab', 'github'], 'CI/CD方案'),
                (['rabbitmq', 'kafka'], '消息队列选型'),
            ]:
                if term in tech:
                    return cat
        
        return '技术决策'

    def _build_decision_title(self, text: str, chosen: str) -> str:
        """Build a descriptive title for a decision."""
        return self._extract_decision_topic(text, [chosen])

    def _extract_project(self, text: str) -> Optional[str]:
        """Extract project name from text."""
        project_patterns = [
            r'(?:项目|project)\s*(?:名|叫|是|=|：|:)\s*(.{2,20}?)(?:[，。,.]|$)',
            r'(?:在|for)\s+(.{2,20}?)\s+(?:项目|project)',
        ]
        for pattern in project_patterns:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return None

    def _get_preference_topic_key(self, category: str, value: str, context: str) -> str:
        """Get a topic-based key for a preference so contradictions can be detected.
        
        'React' + category='framework' -> '前端框架'
        'PostgreSQL' + category='database' -> '数据库'
        'VS Code' + category='editor' -> '代码编辑器'
        """
        topic_keys = {
            'framework': {'react': '前端框架', 'vue': '前端框架', 'angular': '前端框架', 
                         'svelte': '前端框架', 'next.js': '前端框架', 'nuxt': '前端框架',
                         'django': '后端框架', 'flask': '后端框架', 'fastapi': '后端框架',
                         'spring': '后端框架', 'express': '后端框架'},
            'database': {'postgresql': '数据库', 'mysql': '数据库', 'mongodb': '数据库',
                        'redis': '缓存', 'sqlite': '数据库', 'elasticsearch': '搜索引擎'},
            'editor': {'vscode': '代码编辑器', 'vim': '代码编辑器', 'emacs': '代码编辑器',
                      'sublime': '代码编辑器', 'intellij': '代码编辑器', 'pycharm': '代码编辑器',
                      'webstorm': '代码编辑器'},
            'language': {'python': '编程语言', 'java': '编程语言', 'go': '编程语言',
                        'rust': '编程语言', 'typescript': '编程语言', 'javascript': '编程语言',
                        'c++': '编程语言', 'c#': '编程语言'},
            'tool': {'docker': '容器工具', 'kubernetes': '容器编排', 'git': '版本控制',
                    'jenkins': 'CI/CD', 'nginx': 'Web服务器'},
        }
        
        value_lower = value.lower()
        if category in topic_keys:
            for key, topic in topic_keys[category].items():
                if key in value_lower:
                    return topic
        
        # Fallback: use category as key
        return category

    def _categorize_preference(self, value: str, context: str) -> str:
        """Categorize a preference based on value and context."""
        value_lower = value.lower()
        
        # Tool categories
        editors = ['vscode', 'vim', 'emacs', 'sublime', 'intellij', 'webstorm', 'pycharm']
        if any(e in value_lower for e in editors):
            return "editor"
        
        languages = ['python', 'java', 'go', 'rust', 'typescript', 'javascript', 'c++', 'c#']
        if any(l in value_lower for l in languages):
            return "language"
        
        frameworks = ['react', 'vue', 'angular', 'next.js', 'nuxt', 'svelte', 'django', 'flask', 'fastapi', 'spring']
        if any(f in value_lower for f in frameworks):
            return "framework"
        
        databases = ['postgresql', 'mysql', 'mongodb', 'redis', 'sqlite', 'elasticsearch']
        if any(d in value_lower for d in databases):
            return "database"
        
        tools = ['docker', 'kubernetes', 'git', 'jenkins', 'nginx', 'apache']
        if any(t in value_lower for t in tools):
            return "tool"
        
        return "general"

    def _title_similarity(self, title1: str, title2: str) -> float:
        """Simple character-level similarity between two titles."""
        if not title1 or not title2:
            return 0.0
        
        # Extract key terms (remove common words)
        stop_words = {'的', '是', '在', '了', '和', '与', '或', 'the', 'a', 'an', 'is', 'are', 'was'}
        
        def extract_terms(t):
            words = set(re.findall(r'[\w\u4e00-\u9fff]+', t.lower()))
            return words - stop_words
        
        terms1 = extract_terms(title1)
        terms2 = extract_terms(title2)
        
        if not terms1 or not terms2:
            return 0.0
        
        intersection = terms1 & terms2
        union = terms1 | terms2
        
        return len(intersection) / len(union) if union else 0.0


class MemoryManager:
    """High-level memory manager that orchestrates fact extraction,
    contradiction detection, and memory lifecycle.
    
    This is the main interface for the memory system (not just RAG).
    """

    def __init__(self, store):
        self.store = store
        self.extractor = FactExtractor(store)

    def ingest_conversation(
        self,
        messages: List[Dict[str, Any]],
        owner: str = "default",
        session_key: str = "default",
        extract_facts: bool = True,
    ) -> Dict[str, Any]:
        """Ingest a conversation with automatic fact extraction.
        
        For each message:
        1. Store as chunk (for RAG-style retrieval)
        2. Extract structured facts (decisions, preferences, knowledge)
        3. Detect and resolve contradictions
        
        Args:
            messages: List of {role, content} dicts
            owner: Memory owner
            session_key: Session identifier
            extract_facts: Whether to extract facts (set False for pure RAG)
        
        Returns:
            Summary of ingestion results.
        """
        result = {
            "chunks_stored": 0,
            "facts_extracted": {"decisions": 0, "preferences": 0, "knowledge": 0},
            "contradictions_resolved": 0,
        }

        for i, msg in enumerate(messages):
            content = msg.get("content", "")
            role = msg.get("role", "user")
            
            if not content:
                continue

            # 1. Store as chunk (RAG)
            chunk_id = self.store.insert_chunk({
                "sessionKey": session_key,
                "turnId": f"turn_{i}",
                "seq": i,
                "role": role,
                "content": content,
                "owner": owner,
                "visibility": "private",
            })
            result["chunks_stored"] += 1

            # 2. Extract facts from user/assistant messages
            if extract_facts and role in ("user", "assistant"):
                extracted = self.extractor.extract_and_store(
                    text=content,
                    owner=owner,
                    source="conversation",
                    detect_contradictions=True,
                )
                result["facts_extracted"]["decisions"] += len(extracted["decisions"])
                result["facts_extracted"]["preferences"] += len(extracted["preferences"])
                result["facts_extracted"]["knowledge"] += len(extracted["knowledge"])
                result["contradictions_resolved"] += len(extracted["contradictions"])

        return result

    def recall(
        self,
        query: str,
        owner: str = "default",
        max_chunks: int = 5,
        include_decisions: bool = True,
        include_preferences: bool = True,
        include_knowledge: bool = True,
    ) -> Dict[str, Any]:
        """Unified recall: search chunks + structured memories.
        
        Returns:
            Dict with 'chunks', 'decisions', 'preferences', 'knowledge'
        """
        results = {
            "chunks": [],
            "decisions": [],
            "preferences": [],
            "knowledge": [],
        }

        # 1. Chunk search (RAG)
        results["chunks"] = self.store.search_chunks(query, max_results=max_chunks)

        # 2. Decision search
        if include_decisions:
            results["decisions"] = self.store.search_decisions(owner=owner, query=query, limit=5)

        # 3. Preference search (by category matching)
        if include_preferences:
            prefs = self.store.list_preferences(owner=owner)
            # Filter preferences matching query
            query_lower = query.lower()
            for pref in prefs:
                if (query_lower in pref.get("key", "").lower() 
                    or query_lower in pref.get("value", "").lower()
                    or query_lower in pref.get("category", "").lower()):
                    results["preferences"].append(pref)

        # 4. Knowledge search
        if include_knowledge:
            # Search knowledge by topic
            cursor = self.store.conn.cursor()
            cursor.execute(
                "SELECT * FROM knowledge_health WHERE owner = ? AND topic LIKE ? ORDER BY freshness_score DESC LIMIT 5",
                (owner, f"%{query}%"),
            )
            results["knowledge"] = [dict(row) for row in cursor.fetchall()]

        return results

    def get_memory_summary(self, owner: str = "default") -> Dict[str, Any]:
        """Get a summary of all memories for an owner."""
        cursor = self.store.conn.cursor()
        
        summary = {
            "chunks": 0,
            "decisions": {"total": 0, "active": 0, "superseded": 0},
            "preferences": 0,
            "knowledge": 0,
        }

        # Count chunks
        cursor.execute("SELECT COUNT(*) FROM chunks WHERE owner = ?", (owner,))
        summary["chunks"] = cursor.fetchone()[0]

        # Count decisions
        cursor.execute("SELECT COUNT(*) FROM decisions WHERE owner = ?", (owner,))
        summary["decisions"]["total"] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM decisions WHERE owner = ? AND status = 'active'", (owner,))
        summary["decisions"]["active"] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM decisions WHERE owner = ? AND status = 'superseded'", (owner,))
        summary["decisions"]["superseded"] = cursor.fetchone()[0]

        # Count preferences
        cursor.execute("SELECT COUNT(*) FROM user_preferences WHERE owner = ?", (owner,))
        summary["preferences"] = cursor.fetchone()[0]

        # Count knowledge
        cursor.execute("SELECT COUNT(*) FROM knowledge_health WHERE owner = ?", (owner,))
        summary["knowledge"] = cursor.fetchone()[0]

        return summary

    def consolidate_memories(self, owner: str = "default") -> Dict[str, Any]:
        """Consolidate related memories into higher-level knowledge.
        
        This is what makes MemScope a MEMORY system, not just RAG.
        
        Consolidation rules:
        1. Multiple decisions about same topic -> Decision timeline summary
        2. Multiple preferences in same category -> Preference profile
        3. Related knowledge entries -> Knowledge graph node
        """
        result = {
            "decision_timelines": 0,
            "preference_profiles": 0,
            "knowledge_graphs": 0,
        }
        
        result["decision_timelines"] = self._consolidate_decisions(owner)
        result["preference_profiles"] = self._consolidate_preferences(owner)
        result["knowledge_graphs"] = self._consolidate_knowledge(owner)
        
        return result

    def _consolidate_decisions(self, owner: str) -> int:
        """Consolidate decisions about the same topic into timelines."""
        cursor = self.store.conn.cursor()
        
        cursor.execute(
            "SELECT title, COUNT(*) as cnt, "
            "GROUP_CONCAT(chosen, ' -> ') as timeline, "
            "MAX(CASE WHEN status='active' THEN chosen END) as current "
            "FROM decisions WHERE owner = ? GROUP BY title HAVING cnt > 1",
            (owner,),
        )
        
        consolidated = 0
        for row in cursor.fetchall():
            title, count, timeline, current = row[0], row[1], row[2], row[3]
            
            if count > 1 and timeline:
                summary_text = f"[Decision History] {title}: {timeline}"
                if current:
                    summary_text += f" (current: {current})"
                
                self.store.insert_chunk({
                    "sessionKey": f"consolidated_{owner}",
                    "turnId": f"decision_timeline_{title}",
                    "seq": 0,
                    "role": "system",
                    "content": summary_text,
                    "kind": "consolidated_decision",
                    "summary": f"{title} decision history",
                    "owner": owner,
                    "visibility": "private",
                })
                consolidated += 1
        
        return consolidated

    def _consolidate_preferences(self, owner: str) -> int:
        """Consolidate preferences into user profiles."""
        cursor = self.store.conn.cursor()
        
        cursor.execute(
            "SELECT category, GROUP_CONCAT(key || '=' || value, ', ') as prefs, COUNT(*) as cnt "
            "FROM user_preferences WHERE owner = ? GROUP BY category HAVING cnt > 0",
            (owner,),
        )
        
        consolidated = 0
        for row in cursor.fetchall():
            category, prefs_str, count = row[0], row[1], row[2]
            
            if prefs_str:
                pref_items = []
                for pref in prefs_str.split(', '):
                    if '=' in pref:
                        key, value = pref.split('=', 1)
                        if value == 'avoid':
                            pref_items.append(f"avoid {key}")
                        elif value == 'prefer':
                            pref_items.append(f"prefer {key}")
                        else:
                            pref_items.append(f"{key}={value}")
                
                if pref_items:
                    summary_text = f"[User Preferences] {category}: {', '.join(pref_items)}"
                    
                    self.store.insert_chunk({
                        "sessionKey": f"consolidated_{owner}",
                        "turnId": f"preference_profile_{category}",
                        "seq": 0,
                        "role": "system",
                        "content": summary_text,
                        "kind": "consolidated_preference",
                        "summary": f"{category} preference profile",
                        "owner": owner,
                        "visibility": "private",
                    })
                    consolidated += 1
        
        return consolidated

    def _consolidate_knowledge(self, owner: str) -> int:
        """Consolidate related knowledge into graph nodes."""
        cursor = self.store.conn.cursor()
        
        cursor.execute(
            "SELECT topic, source, freshness_score, accuracy_score "
            "FROM knowledge_health WHERE owner = ? ORDER BY topic",
            (owner,),
        )
        
        rows = cursor.fetchall()
        if not rows:
            return 0
        
        topic_groups = {}
        for row in rows:
            topic = row[0]
            topic_type = topic.split(':')[0] if ':' in topic else 'general'
            if topic_type not in topic_groups:
                topic_groups[topic_type] = []
            topic_groups[topic_type].append(topic)
        
        consolidated = 0
        for topic_type, topics in topic_groups.items():
            if topics:
                values = [t.split(':', 1)[1] for t in topics if ':' in t]
                if values:
                    summary_text = f"[Knowledge Graph] {topic_type}: {', '.join(values)}"
                    
                    self.store.insert_chunk({
                        "sessionKey": f"consolidated_{owner}",
                        "turnId": f"knowledge_graph_{topic_type}",
                        "seq": 0,
                        "role": "system",
                        "content": summary_text,
                        "kind": "consolidated_knowledge",
                        "summary": f"{topic_type} knowledge summary",
                        "owner": owner,
                        "visibility": "private",
                    })
                    consolidated += 1
        
        return consolidated

    def get_decision_timeline(self, owner: str, topic: str) -> List[Dict[str, Any]]:
        """Get the decision timeline for a specific topic."""
        cursor = self.store.conn.cursor()
        cursor.execute(
            "SELECT * FROM decisions WHERE owner = ? AND title LIKE ? ORDER BY createdAt ASC",
            (owner, f"%{topic}%"),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_preference_profile(self, owner: str) -> Dict[str, Any]:
        """Get the user complete preference profile."""
        cursor = self.store.conn.cursor()
        cursor.execute(
            "SELECT category, key, value, confidence, source "
            "FROM user_preferences WHERE owner = ? ORDER BY category, key",
            (owner,),
        )
        
        profile = {}
        for row in cursor.fetchall():
            cat = row[0]
            if cat not in profile:
                profile[cat] = []
            profile[cat].append({
                "key": row[1],
                "value": row[2],
                "confidence": row[3],
                "source": row[4],
            })
        
        return profile

    def get_knowledge_graph(self, owner: str) -> Dict[str, Any]:
        """Get the knowledge graph for an owner."""
        cursor = self.store.conn.cursor()
        cursor.execute(
            "SELECT topic, source, freshness_score, accuracy_score "
            "FROM knowledge_health WHERE owner = ? ORDER BY topic",
            (owner,),
        )
        
        graph = {}
        for row in cursor.fetchall():
            topic = row[0]
            topic_type = topic.split(':')[0] if ':' in topic else 'general'
            if topic_type not in graph:
                graph[topic_type] = []
            graph[topic_type].append({
                "topic": topic,
                "source": row[1],
                "freshness": row[2],
                "accuracy": row[3],
            })
        
        return graph

    def context_aware_recall(
        self,
        query: str,
        conversation_context: List[str] = None,
        owner: str = "default",
        max_results: int = 5,
    ) -> Dict[str, Any]:
        """Context-aware memory recall.
        
        Uses conversation context to disambiguate and improve search.
        
        Strategy:
        1. Extract context keywords from recent messages
        2. Boost memories that match both query AND context
        3. Filter out memories that are irrelevant to current context
        
        Args:
            query: The search query
            conversation_context: Recent conversation messages for context
            owner: Memory owner
            max_results: Maximum results to return
        """
        results = {
            "chunks": [],
            "decisions": [],
            "preferences": [],
            "knowledge": [],
            "context_boost": [],
        }

        # 1. Extract context keywords
        context_keywords = set()
        if conversation_context:
            for msg in conversation_context[-3:]:  # Last 3 messages
                words = re.findall(r'[\w\u4e00-\u9fff]{2,}', msg.lower())
                context_keywords.update(words)

        # 2. Standard recall
        base_recall = self.recall(query, owner=owner, max_chunks=max_results)
        
        # 3. Boost results that match context
        for chunk in base_recall.get("chunks", []):
            content = chunk.get("content", "").lower()
            context_match = sum(1 for kw in context_keywords if kw in content)
            chunk["_context_score"] = context_match
            chunk["_relevance"] = chunk.get("_score", 0) + context_match * 0.1

        # Sort by combined relevance
        base_recall["chunks"].sort(key=lambda x: x.get("_relevance", 0), reverse=True)
        
        # 4. Also search structured memories with context
        if context_keywords:
            context_query = " ".join(list(context_keywords)[:5])
            context_decisions = self.store.search_decisions(owner=owner, query=context_query, limit=3)
            
            # Merge with base results (avoid duplicates)
            seen_ids = {d["id"] for d in base_recall.get("decisions", [])}
            for d in context_decisions:
                if d["id"] not in seen_ids:
                    base_recall["decisions"].append(d)
                    results["context_boost"].append({"type": "decision", "id": d["id"], "title": d.get("title", "")})

        results.update(base_recall)
        return results

    def smart_ingest(
        self,
        messages: List[Dict[str, Any]],
        owner: str = "default",
        session_key: str = "default",
    ) -> Dict[str, Any]:
        """Smart ingestion that does everything:
        1. Store chunks
        2. Extract facts
        3. Detect contradictions
        4. Consolidate if enough new facts
        """
        # Step 1-3: Standard ingestion with fact extraction
        result = self.ingest_conversation(messages, owner, session_key, extract_facts=True)
        
        # Step 4: Consolidate if we extracted enough new facts
        total_facts = sum(result["facts_extracted"].values())
        if total_facts >= 2:
            consolidation = self.consolidate_memories(owner)
            result["consolidation"] = consolidation
        
        return result


    def check_memory_health(self, owner: str = "default") -> Dict[str, Any]:
        """Check the health of all memories for an owner.
        
        Health indicators:
        - Freshness: how recently memories were updated
        - Coverage: do we have memories for all important topics?
        - Consistency: are there any conflicting memories?
        - Staleness: are any memories outdated?
        """
        cursor = self.store.conn.cursor()
        now = int(time.time() * 1000)
        
        health = {
            "overall_score": 1.0,
            "freshness": {"score": 1.0, "stale_count": 0, "details": []},
            "consistency": {"score": 1.0, "conflicts": 0, "details": []},
            "coverage": {"score": 1.0, "gaps": [], "details": []},
        }
        
        # 1. Freshness check - decisions older than 30 days without update
        thirty_days_ago = now - 30 * 24 * 3600 * 1000
        cursor.execute(
            "SELECT id, title, updatedAt FROM decisions WHERE owner = ? AND status = 'active' AND updatedAt < ?",
            (owner, thirty_days_ago),
        )
        stale_decisions = cursor.fetchall()
        if stale_decisions:
            health["freshness"]["stale_count"] = len(stale_decisions)
            for d in stale_decisions:
                days_old = (now - d[2]) / (24 * 3600 * 1000)
                health["freshness"]["details"].append({
                    "id": d[0], "title": d[1], "days_old": int(days_old)
                })
            health["freshness"]["score"] = max(0.5, 1.0 - 0.05 * len(stale_decisions))
        
        # 2. Consistency check - active decisions with same title but different chosen
        cursor.execute(
            "SELECT title, COUNT(DISTINCT chosen) as cnt FROM decisions "
            "WHERE owner = ? AND status = 'active' GROUP BY title HAVING cnt > 1",
            (owner,),
        )
        conflicts = cursor.fetchall()
        if conflicts:
            health["consistency"]["conflicts"] = len(conflicts)
            for c in conflicts:
                health["consistency"]["details"].append({"title": c[0], "variants": c[1]})
            health["consistency"]["score"] = max(0.5, 1.0 - 0.1 * len(conflicts))
        
        # 3. Coverage check - common topic categories
        expected_topics = ["database", "framework", "language", "tool", "infrastructure"]
        cursor.execute(
            "SELECT topic FROM knowledge_health WHERE owner = ?",
            (owner,),
        )
        existing_topics = set()
        for row in cursor.fetchall():
            topic_type = row[0].split(":")[0] if ":" in row[0] else row[0]
            existing_topics.add(topic_type)
        
        cursor.execute(
            "SELECT DISTINCT category FROM user_preferences WHERE owner = ?",
            (owner,),
        )
        for row in cursor.fetchall():
            existing_topics.add(row[0])
        
        gaps = [t for t in expected_topics if t not in existing_topics]
        if gaps:
            health["coverage"]["gaps"] = gaps
            health["coverage"]["score"] = max(0.5, 1.0 - 0.1 * len(gaps))
        
        # Overall score
        health["overall_score"] = (
            0.4 * health["freshness"]["score"] +
            0.3 * health["consistency"]["score"] +
            0.3 * health["coverage"]["score"]
        )
        
        return health

    def share_memory(self, memory_type: str, memory_id: str, target_owner: str) -> bool:
        """Share a memory with another owner (cross-agent sharing)."""
        try:
            cursor = self.store.conn.cursor()
            conn = self.store.conn
            now = int(time.time() * 1000)
            
            if memory_type == "decision":
                cursor.execute("SELECT * FROM decisions WHERE id = ?", (memory_id,))
                row = cursor.fetchone()
                if row:
                    row_dict = dict(row)
                    cursor.execute(
                        "INSERT OR REPLACE INTO decisions (id, owner, project, title, context, chosen, alternatives, outcome, status, tags, createdAt, updatedAt) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (str(uuid.uuid4()), target_owner, row_dict.get("project"), row_dict["title"],
                         row_dict.get("context"), row_dict.get("chosen"), row_dict.get("alternatives"),
                         row_dict.get("outcome"), "active", "shared:" + row_dict.get("owner", ""), now, now),
                    )
                    conn.commit()
                    return True
            
            elif memory_type == "preference":
                cursor.execute("SELECT * FROM user_preferences WHERE id = ?", (memory_id,))
                row = cursor.fetchone()
                if row:
                    row_dict = dict(row)
                    cursor.execute(
                        "INSERT OR REPLACE INTO user_preferences (id, owner, category, key, value, confidence, source, createdAt, updatedAt) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (str(uuid.uuid4()), target_owner, row_dict["category"], row_dict["key"],
                         row_dict["value"], row_dict.get("confidence", 0.8), "shared", now, now),
                    )
                    conn.commit()
                    return True
            
            return False
        except Exception as e:
            logger.error(f"share_memory failed: {e}")
            return False

    def get_shared_memories(self, owner: str, memory_type: str = None) -> List[Dict[str, Any]]:
        """Get memories shared with this owner."""
        try:
            cursor = self.store.conn.cursor()
            results = []
            
            if memory_type in (None, "decision"):
                cursor.execute(
                    "SELECT * FROM decisions WHERE owner = ? AND tags LIKE 'shared:%' ORDER BY updatedAt DESC LIMIT 20",
                    (owner,),
                )
                results.extend([dict(row) for row in cursor.fetchall()])
            
            if memory_type in (None, "preference"):
                cursor.execute(
                    "SELECT * FROM user_preferences WHERE owner = ? AND source = 'shared' ORDER BY updatedAt DESC LIMIT 20",
                    (owner,),
                )
                results.extend([dict(row) for row in cursor.fetchall()])
            
            return results
        except Exception as e:
            logger.error(f"get_shared_memories failed: {e}")
            return []


    def proactive_recommend(
        self,
        message: str,
        owner: str = "default",
        max_recommendations: int = 5,
    ) -> Dict[str, Any]:
        """Proactively recommend relevant memories based on a new message.
        
        Unlike recall() which requires an explicit query, this method:
        1. Analyzes the incoming message for topics/entities
        2. Searches all memory types for relevant entries
        3. Ranks by relevance and importance
        4. Returns top recommendations with context
        
        Args:
            message: The new user message to find context for
            owner: Memory owner
            max_recommendations: Max items to recommend
            
        Returns:
            Dict with 'recommendations' list and 'topics_detected' list.
        """
        import re as _re
        
        # Step 1: Extract topics and entities from message
        topics = self._extract_topics(message)
        
        # Step 2: Search each memory type
        candidates = []
        
        # Search decisions (broader matching: also search by chosen value and context)
        seen_decision_ids = set()
        for topic in topics:
            # Search by title/context/chosen
            decisions = self.store.search_decisions(owner=owner, query=topic, limit=3)
            for d in decisions:
                if d.get("status") == "active" and d["id"] not in seen_decision_ids:
                    seen_decision_ids.add(d["id"])
                    candidates.append({
                        "type": "decision",
                        "id": d["id"],
                        "title": d.get("title", ""),
                        "value": d.get("chosen", ""),
                        "context": d.get("context", ""),
                        "topic_match": topic,
                        "status": d.get("status", "active"),
                    })
        
        # Also get ALL active decisions as broader context
        all_active = self.store.search_decisions(owner=owner, limit=20)
        for d in all_active:
            if d.get("status") == "active" and d["id"] not in seen_decision_ids:
                # Check if any topic word appears in title/context/chosen
                title_ctx = f"{d.get('title', '')} {d.get('context', '')} {d.get('chosen', '')}"
                for topic in topics:
                    if topic.lower() in title_ctx.lower() or any(
                        t in title_ctx for t in ['框架', '选型', '技术', '方案', '工具']
                    ):
                        seen_decision_ids.add(d["id"])
                        candidates.append({
                            "type": "decision",
                            "id": d["id"],
                            "title": d.get("title", ""),
                            "value": d.get("chosen", ""),
                            "context": d.get("context", ""),
                            "topic_match": topic,
                            "status": d.get("status", "active"),
                        })
                        break
        
        # Search preferences
        prefs = self.store.list_preferences(owner=owner)
        for pref in prefs:
            pref_text = f"{pref.get('category', '')} {pref.get('key', '')} {pref.get('value', '')}"
            for topic in topics:
                if topic.lower() in pref_text.lower():
                    candidates.append({
                        "type": "preference",
                        "category": pref.get("category", ""),
                        "key": pref.get("key", ""),
                        "value": pref.get("value", ""),
                        "topic_match": topic,
                    })
                    break
        
        # Search knowledge (topic-matched + all active knowledge for context)
        cursor = self.store.conn.cursor()
        seen_knowledge = set()
        for topic in topics:
            cursor.execute(
                "SELECT * FROM knowledge_health WHERE owner = ? AND topic LIKE ? ORDER BY freshness_score DESC LIMIT 3",
                (owner, f"%{topic}%"),
            )
            for row in cursor.fetchall():
                row_dict = dict(row)
                if row_dict["id"] not in seen_knowledge:
                    seen_knowledge.add(row_dict["id"])
                    candidates.append({
                        "type": "knowledge",
                        "topic": row_dict.get("topic", ""),
                        "freshness": row_dict.get("freshness_score", 0),
                        "accuracy": row_dict.get("accuracy_score", 0),
                        "topic_match": topic,
                    })
        
        # Also include high-freshness knowledge as general context
        cursor.execute(
            "SELECT * FROM knowledge_health WHERE owner = ? AND freshness_score > 0.7 ORDER BY freshness_score DESC LIMIT 5",
            (owner,),
        )
        for row in cursor.fetchall():
            row_dict = dict(row)
            if row_dict["id"] not in seen_knowledge:
                seen_knowledge.add(row_dict["id"])
                candidates.append({
                    "type": "knowledge",
                    "topic": row_dict.get("topic", ""),
                    "freshness": row_dict.get("freshness_score", 0),
                    "accuracy": row_dict.get("accuracy_score", 0),
                    "topic_match": "(context)",
                })
        
        # Search consolidated chunks
        for topic in topics:
            cursor.execute(
                "SELECT * FROM chunks WHERE owner = ? AND content LIKE ? AND kind LIKE 'consolidated%' LIMIT 2",
                (owner, f"%{topic}%"),
            )
            for row in cursor.fetchall():
                row_dict = dict(row)
                candidates.append({
                    "type": "consolidated",
                    "content": row_dict.get("content", ""),
                    "kind": row_dict.get("kind", ""),
                    "topic_match": topic,
                })
        
        # Step 3: Deduplicate and rank
        seen = set()
        unique = []
        for c in candidates:
            key = f"{c['type']}:{c.get('id', '')}{c.get('topic', '')}{c.get('key', '')}"
            if key not in seen:
                seen.add(key)
                unique.append(c)
        
        # Step 4: Limit
        recommendations = unique[:max_recommendations]
        
        return {
            "recommendations": recommendations,
            "topics_detected": topics,
            "total_candidates": len(candidates),
            "unique_candidates": len(unique),
        }

    def _extract_topics(self, text: str) -> list:
        """Extract key topics/entities from text for proactive matching."""
        import re as _re
        
        topics = set()
        
        # Tech terms
        tech_terms = [
            'React', 'Vue', 'Angular', 'Next.js', 'Svelte',
            'Python', 'Java', 'Go', 'Rust', 'TypeScript', 'JavaScript',
            'PostgreSQL', 'MySQL', 'MongoDB', 'Redis', 'SQLite',
            'Docker', 'Kubernetes', 'K8s', 'AWS', 'Azure', 'GCP',
            'RabbitMQ', 'Kafka', 'Nginx', 'gRPC', 'GraphQL',
            'Git', 'Jenkins', 'GitHub', 'GitLab',
            'FastAPI', 'Django', 'Flask', 'Spring',
            'Prometheus', 'Grafana', 'ELK',
        ]
        for term in tech_terms:
            if term.lower() in text.lower():
                topics.add(term)
        
        # Chinese topic patterns
        topic_patterns = [
            (r'(?:数据库|DB|数据存储)', '数据库'),
            (r'(?:前端|前端框架|UI)', '前端'),
            (r'(?:后端|后端框架|服务端)', '后端'),
            (r'(?:部署|部署方案|云平台)', '部署'),
            (r'(?:消息队列|MQ)', '消息队列'),
            (r'(?:缓存)', '缓存'),
            (r'(?:容器|容器化)', '容器'),
            (r'(?:监控|监控系统)', '监控'),
            (r'(?:CI/CD|持续集成|流水线)', 'CI/CD'),
            (r'(?:测试|测试框架)', '测试'),
            (r'(?:安全|认证|授权)', '安全'),
            (r'(?:性能|优化)', '性能'),
            (r'(?:架构|系统架构)', '架构'),
            (r'(?:框架|技术栈|技术选型)', '技术选型'),
        ]
        for pattern, topic in topic_patterns:
            if _re.search(pattern, text, _re.IGNORECASE):
                topics.add(topic)
        
        # Also extract any quoted or backticked terms
        quoted = _re.findall(r'["\']([^"\' ]+)["\']|`([^`]+)`', text)
        for q in quoted:
            term = q[0] or q[1]
            if len(term) >= 2:
                topics.add(term)
        
        return list(topics)

    def prefetch(
        self,
        session_key: str,
        owner: str = "default",
    ) -> Dict[str, Any]:
        """Prefetch relevant memories at session start.
        
        Called when a new conversation session begins.
        Returns a memory briefing: recent decisions, active preferences,
        relevant knowledge, and consolidated summaries.
        
        This is the Memory system's prefetch() lifecycle hook.
        """
        cursor = self.store.conn.cursor()
        
        briefing = {
            "recent_decisions": [],
            "active_preferences": [],
            "knowledge_summary": [],
            "consolidated": [],
        }
        
        # Recent active decisions (last 10)
        cursor.execute(
            "SELECT * FROM decisions WHERE owner = ? AND status = 'active' ORDER BY updatedAt DESC LIMIT 10",
            (owner,),
        )
        briefing["recent_decisions"] = [dict(row) for row in cursor.fetchall()]
        
        # Active preferences
        cursor.execute(
            "SELECT * FROM user_preferences WHERE owner = ? ORDER BY updatedAt DESC LIMIT 10",
            (owner,),
        )
        briefing["active_preferences"] = [dict(row) for row in cursor.fetchall()]
        
        # Knowledge with high freshness
        cursor.execute(
            "SELECT * FROM knowledge_health WHERE owner = ? AND freshness_score > 0.5 ORDER BY freshness_score DESC LIMIT 10",
            (owner,),
        )
        briefing["knowledge_summary"] = [dict(row) for row in cursor.fetchall()]
        
        # Consolidated summaries
        cursor.execute(
            "SELECT * FROM chunks WHERE owner = ? AND kind LIKE 'consolidated%' ORDER BY createdAt DESC LIMIT 5",
            (owner,),
        )
        briefing["consolidated"] = [dict(row) for row in cursor.fetchall()]
        
        return briefing
