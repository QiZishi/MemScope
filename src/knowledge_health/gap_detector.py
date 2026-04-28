"""
团队知识缺口检测器
10大知识领域覆盖分析 + 单点故障识别
"""
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GapDetector:
    """团队知识缺口检测器，覆盖10大核心知识领域分析。"""

    # 10大核心知识领域
    KNOWLEDGE_DOMAINS: List[str] = [
        'architecture',    # 系统架构
        'api_design',      # API设计
        'database',        # 数据库
        'devops',          # DevOps/部署
        'security',        # 安全
        'frontend',        # 前端
        'backend',         # 后端
        'testing',         # 测试
        'business',        # 业务逻辑
        'infrastructure',  # 基础设施
    ]

    # 领域关键词映射，用于分类知识条目
    DOMAIN_KEYWORDS: Dict[str, List[str]] = {
        'architecture': ['架构', 'architecture', 'microservice', '微服务', '设计模式', 'design pattern', '系统设计'],
        'api_design': ['api', 'restful', 'graphql', 'endpoint', '接口', 'swagger', 'openapi'],
        'database': ['database', '数据库', 'sql', 'postgres', 'mysql', 'redis', 'mongo', '索引', 'migration'],
        'devops': ['devops', 'deploy', '部署', 'ci/cd', 'docker', 'kubernetes', 'k8s', 'jenkins', 'pipeline'],
        'security': ['security', '安全', 'auth', '认证', '加密', 'ssl', 'oauth', 'jwt', 'permission', '权限'],
        'frontend': ['frontend', '前端', 'react', 'vue', 'angular', 'css', 'html', 'javascript', 'typescript'],
        'backend': ['backend', '后端', 'server', '服务端', 'python', 'java', 'go', 'node'],
        'testing': ['test', '测试', 'unit test', '集成测试', 'e2e', 'benchmark', 'mock', 'coverage'],
        'business': ['business', '业务', 'requirement', '需求', 'product', '产品', 'workflow', '流程'],
        'infrastructure': ['infrastructure', '基础设施', 'network', '网络', 'monitoring', '监控', 'logging', '日志', 'nginx', 'load balancer'],
    }

    def __init__(self, store: Any) -> None:
        self.store = store

    # ------------------------------------------------------------------
    # 覆盖率分析
    # ------------------------------------------------------------------

    def analyze_coverage(self, team_id: str) -> Dict[str, Any]:
        """分析团队知识覆盖率。

        Returns:
            各领域的覆盖率统计
        """
        try:
            records = self.store.list_knowledge_health(team_id)
            map_entries = self.store.get_team_knowledge_map(team_id)

            # 将 knowledge_health 和 team_knowledge_map 按 domain 分类
            domain_stats: Dict[str, Dict[str, Any]] = {}
            for domain in self.KNOWLEDGE_DOMAINS:
                domain_stats[domain] = {
                    'knowledge_count': 0,
                    'holders': set(),
                    'topics': [],
                }

            # 从 knowledge_health 分类
            for rec in records:
                metadata = self._parse_metadata(rec.get('metadata'))
                topic_text = rec.get('topic', '') + ' ' + metadata.get('category', '')
                domains = self._classify_domains(topic_text)
                holder_count = metadata.get('holder_count', 1)
                holders_list = metadata.get('holders', [])

                for domain in domains:
                    if domain in domain_stats:
                        domain_stats[domain]['knowledge_count'] += 1
                        domain_stats[domain]['topics'].append(rec.get('topic', ''))
                        for h in holders_list:
                            domain_stats[domain]['holders'].add(h)

            # 从 team_knowledge_map 补充
            for entry in map_entries:
                topic_text = entry.get('topic', '') + ' ' + (entry.get('tags', '') or '')
                expert = entry.get('expert', '')
                domains = self._classify_domains(topic_text)
                for domain in domains:
                    if domain in domain_stats:
                        domain_stats[domain]['knowledge_count'] += 1
                        if expert:
                            domain_stats[domain]['holders'].add(expert)

            # 计算覆盖率
            total_domains = len(self.KNOWLEDGE_DOMAINS)
            covered = 0
            result: Dict[str, Any] = {
                'team_id': team_id,
                'total_domains': total_domains,
                'domain_details': {},
                'single_point_domains': [],
                'coverage_ratio': 0.0,
            }

            for domain, stats in domain_stats.items():
                holder_count = len(stats['holders'])
                is_covered = stats['knowledge_count'] > 0
                is_single_point = holder_count == 1

                if is_covered:
                    covered += 1
                if is_single_point and stats['knowledge_count'] > 0:
                    result['single_point_domains'].append(domain)

                result['domain_details'][domain] = {
                    'knowledge_count': stats['knowledge_count'],
                    'holder_count': holder_count,
                    'is_covered': is_covered,
                    'is_single_point': is_single_point,
                    'topics': stats['topics'][:5],  # 最多显示5个
                }

            result['coverage_ratio'] = round(covered / total_domains, 4) if total_domains else 0.0
            return result
        except Exception as e:
            logger.error(f"analyze_coverage failed: {e}")
            return {'team_id': team_id, 'error': str(e)}

    # ------------------------------------------------------------------
    # 缺口检测
    # ------------------------------------------------------------------

    def detect_gaps(
        self, team_id: str, domain: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """检测知识缺口。

        Args:
            team_id: 团队 ID
            domain: 指定领域，None 表示所有领域

        Returns:
            缺口列表
        """
        try:
            coverage = self.analyze_coverage(team_id)
            details = coverage.get('domain_details', {})
            gaps: List[Dict[str, Any]] = []

            domains_to_check = [domain] if domain and domain in details else list(details.keys())

            for d in domains_to_check:
                info = details.get(d, {})
                knowledge_count = info.get('knowledge_count', 0)
                holder_count = info.get('holder_count', 0)

                if knowledge_count == 0:
                    severity = 'critical'
                    recommendation = f"领域 [{d}] 完全无知识覆盖，建议立即补充文档或引入专家"
                elif holder_count <= 1:
                    severity = 'high'
                    recommendation = f"领域 [{d}] 仅有 {holder_count} 人掌握，存在单点故障风险，建议知识共享"
                elif knowledge_count < 3:
                    severity = 'medium'
                    recommendation = f"领域 [{d}] 知识条目较少（{knowledge_count}），建议持续积累"
                else:
                    severity = 'low'
                    recommendation = f"领域 [{d}] 覆盖良好"

                if severity in ('critical', 'high', 'medium'):
                    gaps.append({
                        'domain': d,
                        'gap_description': f"{d} 领域知识不足: {knowledge_count} 条, {holder_count} 人掌握",
                        'severity': severity,
                        'knowledge_count': knowledge_count,
                        'holder_count': holder_count,
                        'recommendation': recommendation,
                    })

            # 按严重程度排序
            severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
            gaps.sort(key=lambda g: severity_order.get(g['severity'], 99))
            return gaps
        except Exception as e:
            logger.error(f"detect_gaps failed: {e}")
            return []

    # ------------------------------------------------------------------
    # 单点故障检测
    # ------------------------------------------------------------------

    def detect_single_points(self, team_id: str) -> List[Dict[str, Any]]:
        """检测单点故障（关键知识仅1人掌握）。

        Returns:
            高风险单点条目列表
        """
        try:
            records = self.store.list_knowledge_health(team_id)
            single_points: List[Dict[str, Any]] = []

            for rec in records:
                metadata = self._parse_metadata(rec.get('metadata'))
                holder_count = metadata.get('holder_count', 1)
                importance = metadata.get('importance', 0.5)

                if holder_count <= 1 and importance > 0.7:
                    single_points.append({
                        'topic': rec.get('topic', ''),
                        'importance': importance,
                        'holder_count': holder_count,
                        'holders': metadata.get('holders', []),
                        'category': metadata.get('category', 'general'),
                        'risk_score': round(importance / max(holder_count, 1), 4),
                    })

            # 按风险分数排序
            single_points.sort(key=lambda x: x['risk_score'], reverse=True)
            return single_points
        except Exception as e:
            logger.error(f"detect_single_points failed: {e}")
            return []

    # ------------------------------------------------------------------
    # 知识孤岛检测
    # ------------------------------------------------------------------

    def detect_isolation(self, team_id: str) -> List[Dict[str, Any]]:
        """检测知识孤岛（知识不共享的成员）。

        Returns:
            被孤立成员列表
        """
        try:
            records = self.store.list_knowledge_health(team_id)
            member_coverage: Dict[str, Dict[str, Any]] = {}

            for rec in records:
                metadata = self._parse_metadata(rec.get('metadata'))
                holders = metadata.get('holders', [])
                importance = metadata.get('importance', 0.5)

                for holder in holders:
                    if holder not in member_coverage:
                        member_coverage[holder] = {
                            'member': holder,
                            'topics': [],
                            'total_importance': 0.0,
                            'shared_topics': 0,
                        }
                    member_coverage[holder]['topics'].append(rec.get('topic', ''))
                    member_coverage[holder]['total_importance'] += importance

                    # 如果 holder_count > 1，说明该知识被共享
                    if metadata.get('holder_count', 1) > 1:
                        member_coverage[holder]['shared_topics'] += 1

            # 识别孤岛: 知识很多但共享很少的成员
            isolated: List[Dict[str, Any]] = []
            for member, info in member_coverage.items():
                total_topics = len(info['topics'])
                shared = info['shared_topics']
                if total_topics > 0:
                    isolation_ratio = 1.0 - (shared / total_topics)
                else:
                    isolation_ratio = 0.0

                if total_topics >= 2 and isolation_ratio > 0.6:
                    isolated.append({
                        'member': member,
                        'total_topics': total_topics,
                        'shared_topics': shared,
                        'isolation_ratio': round(isolation_ratio, 4),
                        'total_importance': round(info['total_importance'], 4),
                        'topics': info['topics'][:10],
                    })

            isolated.sort(key=lambda x: x['isolation_ratio'], reverse=True)
            return isolated
        except Exception as e:
            logger.error(f"detect_isolation failed: {e}")
            return []

    # ------------------------------------------------------------------
    # 团队知识地图
    # ------------------------------------------------------------------

    def update_team_map(self, team_id: str) -> Dict[str, Any]:
        """更新团队知识地图。

        Returns:
            变更摘要
        """
        try:
            coverage = self.analyze_coverage(team_id)
            details = coverage.get('domain_details', {})
            updated_count = 0

            for domain, info in details.items():
                if info.get('knowledge_count', 0) > 0:
                    holders_list = list(info.get('holders', set())) if isinstance(info.get('holders'), set) else info.get('holders', [])
                    expert = holders_list[0] if holders_list else None
                    tags = json.dumps({
                        'knowledge_count': info['knowledge_count'],
                        'holder_count': info.get('holder_count', 0),
                        'is_single_point': info.get('is_single_point', False),
                    })

                    self.store.upsert_team_knowledge_map(
                        owner=team_id,
                        topic=domain,
                        expert=expert,
                        description=f"{domain} 领域: {info['knowledge_count']} 条知识, {info.get('holder_count', 0)} 人掌握",
                        tags=tags,
                    )
                    updated_count += 1

            return {
                'team_id': team_id,
                'updated_domains': updated_count,
                'total_domains': len(self.KNOWLEDGE_DOMAINS),
                'coverage_ratio': coverage.get('coverage_ratio', 0.0),
                'single_point_domains': coverage.get('single_point_domains', []),
            }
        except Exception as e:
            logger.error(f"update_team_map failed: {e}")
            return {'team_id': team_id, 'error': str(e)}

    def get_team_map(self, team_id: str) -> Dict[str, Any]:
        """获取团队知识地图。

        Returns:
            团队知识地图数据
        """
        try:
            map_entries = self.store.get_team_knowledge_map(team_id)
            result: Dict[str, Any] = {
                'team_id': team_id,
                'domains': {},
                'total_entries': len(map_entries),
            }

            for entry in map_entries:
                topic = entry.get('topic', '')
                tags = self._parse_metadata(entry.get('tags'))
                result['domains'][topic] = {
                    'expert': entry.get('expert'),
                    'description': entry.get('description'),
                    'knowledge_count': tags.get('knowledge_count', 0),
                    'holder_count': tags.get('holder_count', 0),
                    'is_single_point': tags.get('is_single_point', False),
                    'resource_url': entry.get('resource_url'),
                }

            return result
        except Exception as e:
            logger.error(f"get_team_map failed: {e}")
            return {'team_id': team_id, 'error': str(e)}

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _classify_domains(self, text: str) -> List[str]:
        """根据文本内容分类到知识领域。"""
        text_lower = text.lower()
        matched: List[str] = []
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in text_lower:
                    matched.append(domain)
                    break
        if not matched:
            matched.append('backend')  # 默认归到 backend
        return matched

    @staticmethod
    def _parse_metadata(metadata: Optional[str]) -> Dict[str, Any]:
        """安全解析 metadata/tags JSON 字符串。"""
        if not metadata:
            return {}
        try:
            return json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            return {}
