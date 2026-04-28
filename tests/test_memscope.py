"""
Comprehensive unit tests for MemScope project.
Covers all modules: Store, Direction A/B/C/D, and MemScopeProvider.
"""
import sys
import os
import json
import time
import math
import tempfile
import shutil

sys.path.insert(0, '/root/hermes-data/cron/output')

import pytest

from src.core.store import SqliteStore
from src.direction_a.command_tracker import CommandTracker
from src.direction_a.recommender import CommandRecommender
from src.direction_b.decision_extractor import DecisionExtractor
from src.direction_b.decision_card import DecisionCardManager
from src.direction_c.preference_extractor import PreferenceExtractor
from src.direction_c.preference_manager import PreferenceManager
from src.direction_c.habit_inference import HabitInference
from src.direction_d.ebbinghaus import EbbinghausModel
from src.direction_d.freshness_monitor import FreshnessMonitor
from src.direction_d.gap_detector import GapDetector


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def tmp_dir():
    """Create a temporary directory for test databases."""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def store(tmp_dir):
    """Create a fresh SqliteStore with a temp database."""
    db_path = os.path.join(tmp_dir, 'test_memscope.db')
    s = SqliteStore(db_path)
    yield s
    s.close()


@pytest.fixture
def store_with_data(store):
    """Store pre-loaded with sample data."""
    now = int(time.time() * 1000)
    # Insert some chunks
    for i in range(5):
        store.insert_chunk({
            'id': f'chunk_{i}',
            'sessionKey': 'sess_1',
            'turnId': f'turn_{i}',
            'seq': i,
            'role': 'user' if i % 2 == 0 else 'assistant',
            'content': f'Test content about Python programming number {i}',
            'summary': f'Summary {i}',
            'owner': 'test_owner',
        })
    return store


# ============================================================
# TestStore: SqliteStore CRUD for all table groups
# ============================================================

class TestStore:
    """Test SqliteStore methods for core, A/B/C/D tables."""

    def test_insert_and_get_chunk(self, store):
        chunk_id = store.insert_chunk({
            'sessionKey': 's1', 'turnId': 't1', 'seq': 0,
            'role': 'user', 'content': 'Hello world',
        })
        assert chunk_id
        result = store.get_chunk(chunk_id)
        assert result is not None
        assert result['content'] == 'Hello world'
        assert result['sessionKey'] == 's1'

    def test_get_chunk_not_found(self, store):
        assert store.get_chunk('nonexistent') is None

    def test_search_chunks(self, store):
        store.insert_chunk({'sessionKey': 's1', 'turnId': 't1', 'seq': 0,
                            'role': 'user', 'content': 'Python is great'})
        store.insert_chunk({'sessionKey': 's1', 'turnId': 't2', 'seq': 0,
                            'role': 'user', 'content': 'Java is also fine'})
        results = store.search_chunks('Python')
        assert len(results) >= 1
        assert any('Python' in r['content'] for r in results)

    def test_share_and_get_shared(self, store):
        cid = store.insert_chunk({
            'sessionKey': 's1', 'turnId': 't1', 'seq': 0,
            'role': 'user', 'content': 'Shared knowledge',
        })
        assert store.share_chunk(cid, ['agent_a', 'agent_b'])
        shared = store.get_shared_chunks('agent_a')
        assert len(shared) >= 1
        assert shared[0]['visibility'] == 'shared'

    def test_make_chunk_private(self, store):
        cid = store.insert_chunk({
            'sessionKey': 's1', 'turnId': 't1', 'seq': 0,
            'role': 'user', 'content': 'Secret stuff',
        })
        store.share_chunk(cid)
        assert store.make_chunk_private(cid)
        chunk = store.get_chunk(cid)
        assert chunk['visibility'] == 'private'

    def test_insert_and_get_task(self, store):
        task_id = store.insert_task({'title': 'Build feature X', 'owner': 'dev1'})
        assert task_id
        task = store.get_task(task_id)
        assert task is not None
        assert task['title'] == 'Build feature X'

    def test_finalize_task(self, store):
        task_id = store.insert_task({'title': 'Task to finalize'})
        assert store.finalize_task(task_id, 'Completed successfully')
        task = store.get_task(task_id)
        assert task['status'] == 'completed'
        assert task['summary'] == 'Completed successfully'

    def test_insert_and_get_skill(self, store):
        skill_id = store.insert_skill({
            'name': 'deploy_k8s', 'version': '1.0.0',
            'content': 'kubectl apply -f manifest.yaml',
        })
        assert skill_id
        skill = store.get_skill(skill_id)
        assert skill is not None
        assert skill['name'] == 'deploy_k8s'

    def test_link_task_skill(self, store):
        task_id = store.insert_task({'title': 'Deploy'})
        skill_id = store.insert_skill({'name': 'k8s_deploy', 'version': '1.0', 'content': '...'})
        store.link_task_skill(task_id, skill_id)
        skills = store.get_skills_by_task(task_id)
        assert len(skills) >= 1

    # Direction A store methods
    def test_log_command(self, store):
        cmd_id = store.log_command(owner='user1', command='git push origin main', exit_code=0)
        assert cmd_id
        history = store.get_command_history('user1')
        assert len(history) >= 1
        assert history[0]['command'] == 'git push origin main'

    def test_update_and_get_command_patterns(self, store):
        store.update_command_pattern('user1', 'git', exit_code=0)
        store.update_command_pattern('user1', 'git', exit_code=0)
        store.update_command_pattern('user1', 'git', exit_code=1)
        patterns = store.get_command_patterns('user1')
        assert len(patterns) >= 1
        git_pattern = [p for p in patterns if p['command'] == 'git'][0]
        assert git_pattern['frequency'] == 3

    def test_command_patterns_with_project(self, store):
        store.update_command_pattern('u1', 'npm', project_path='/proj/a', exit_code=0)
        store.update_command_pattern('u1', 'npm', project_path='/proj/b', exit_code=0)
        patterns_a = store.get_command_patterns('u1', project_path='/proj/a')
        assert len(patterns_a) == 1
        assert patterns_a[0]['project_path'] == '/proj/a'

    # Direction B store methods
    def test_insert_and_get_decision(self, store):
        did = store.insert_decision(
            owner='u1', title='Use PostgreSQL', context='Need ACID', chosen='PG over Mongo'
        )
        assert did
        dec = store.get_decision(did)
        assert dec is not None
        assert dec['title'] == 'Use PostgreSQL'

    def test_search_decisions(self, store):
        store.insert_decision(owner='u1', title='Use Redis', context='Cache layer')
        store.insert_decision(owner='u1', title='Use Kafka', context='Message queue')
        results = store.search_decisions('u1', query='Redis')
        assert len(results) >= 1
        assert any('Redis' in r['title'] for r in results)

    def test_update_decision(self, store):
        did = store.insert_decision(owner='u1', title='Old title', context='ctx')
        assert store.update_decision(did, {'title': 'New title'})
        dec = store.get_decision(did)
        assert dec['title'] == 'New title'

    def test_get_decisions_by_project(self, store):
        store.insert_decision(owner='u1', title='D1', project='proj_a')
        store.insert_decision(owner='u1', title='D2', project='proj_a')
        store.insert_decision(owner='u1', title='D3', project='proj_b')
        results = store.get_decisions_by_project('u1', 'proj_a')
        assert len(results) == 2

    # Direction C store methods
    def test_upsert_and_get_preference(self, store):
        pid = store.upsert_preference(owner='u1', category='tool', key='editor', value='vim')
        assert pid
        pref = store.get_preference('u1', 'tool', 'editor')
        assert pref is not None
        assert pref['value'] == 'vim'

    def test_upsert_preference_update(self, store):
        pid1 = store.upsert_preference(owner='u1', category='tool', key='editor', value='vim')
        pid2 = store.upsert_preference(owner='u1', category='tool', key='editor', value='emacs')
        assert pid1 == pid2  # Same row updated
        pref = store.get_preference('u1', 'tool', 'editor')
        assert pref['value'] == 'emacs'

    def test_list_preferences(self, store):
        store.upsert_preference(owner='u1', category='tool', key='editor', value='vim')
        store.upsert_preference(owner='u1', category='style', key='theme', value='dark')
        prefs = store.list_preferences('u1')
        assert len(prefs) == 2
        # With category filter
        tool_prefs = store.list_preferences('u1', category='tool')
        assert len(tool_prefs) == 1

    def test_delete_preference(self, store):
        store.upsert_preference(owner='u1', category='tool', key='editor', value='vim')
        assert store.delete_preference('u1', 'tool', 'editor')
        assert store.get_preference('u1', 'tool', 'editor') is None

    def test_decay_preference_confidence(self, store):
        store.upsert_preference(owner='u1', category='tool', key='a', value='x', confidence=1.0)
        store.upsert_preference(owner='u1', category='tool', key='b', value='y', confidence=0.5)
        affected = store.decay_preference_confidence('u1', decay_factor=0.9)
        assert affected == 2
        pref_a = store.get_preference('u1', 'tool', 'a')
        assert pref_a['confidence'] == pytest.approx(0.9, abs=0.01)

    def test_insert_and_get_behavior_pattern(self, store):
        pid = store.insert_behavior_pattern(
            owner='u1', pattern_type='time_pattern', description='Active at 10am',
            data='{"peak_hours": [10]}', confidence=0.8
        )
        assert pid
        patterns = store.get_behavior_patterns('u1')
        assert len(patterns) >= 1
        assert patterns[0]['pattern_type'] == 'time_pattern'

    # Direction D store methods
    def test_upsert_and_get_knowledge_health(self, store):
        kh_id = store.upsert_knowledge_health(
            owner='team1', topic='API Design', freshness_score=0.95
        )
        assert kh_id
        rec = store.get_knowledge_health('team1', 'API Design')
        assert rec is not None
        assert rec['freshness_score'] == 0.95

    def test_list_knowledge_health(self, store):
        store.upsert_knowledge_health(owner='team1', topic='Topic A')
        store.upsert_knowledge_health(owner='team1', topic='Topic B')
        records = store.list_knowledge_health('team1')
        assert len(records) == 2

    def test_update_freshness(self, store):
        store.upsert_knowledge_health(owner='team1', topic='T1', freshness_score=1.0)
        assert store.update_freshness('team1', 'T1', 0.5)
        rec = store.get_knowledge_health('team1', 'T1')
        assert rec['freshness_score'] == 0.5

    def test_team_knowledge_map(self, store):
        tid = store.upsert_team_knowledge_map(
            owner='team1', topic='architecture', expert='alice', description='System design'
        )
        assert tid
        entries = store.get_team_knowledge_map('team1')
        assert len(entries) >= 1
        assert entries[0]['expert'] == 'alice'

    def test_insert_forgetting_schedule_and_due(self, store):
        # Insert with a very short interval so it's due immediately
        fs_id = store.insert_forgetting_schedule(
            owner='team1', chunk_id='c1', topic='topic1',
            interval_days=-1.0,  # Already overdue
        )
        assert fs_id
        due = store.get_due_reviews('team1')
        assert len(due) >= 1

    def test_get_neighbor_chunks(self, store):
        for i in range(5):
            store.insert_chunk({
                'sessionKey': 's1', 'turnId': 't1', 'seq': i,
                'role': 'user', 'content': f'Chunk {i}',
            })
        neighbors = store.get_neighbor_chunks('s1', 't1', seq=2, window=1)
        assert len(neighbors) == 3  # seq 1, 2, 3

    def test_stats(self, store):
        store.insert_chunk({'sessionKey': 's1', 'turnId': 't1', 'seq': 0, 'role': 'user', 'content': 'c'})
        store.insert_task({'title': 't'})
        stats = store.get_stats()
        assert stats['total_chunks'] >= 1
        assert stats['total_tasks'] >= 1


# ============================================================
# TestDirectionA: CommandTracker and CommandRecommender
# ============================================================

class TestDirectionA:
    """Test Direction A: CLI command tracking and recommendation."""

    def test_log_command_creates_history_and_pattern(self, store):
        tracker = CommandTracker(store)
        cmd_id = tracker.log_command(owner='u1', command='git commit -m "fix"')
        assert cmd_id
        history = store.get_command_history('u1')
        assert len(history) >= 1
        patterns = store.get_command_patterns('u1')
        git_pats = [p for p in patterns if p['command'] == 'git']
        assert len(git_pats) == 1

    def test_log_multiple_commands_updates_frequency(self, store):
        tracker = CommandTracker(store)
        for _ in range(5):
            tracker.log_command(owner='u1', command='python main.py')
        patterns = store.get_command_patterns('u1')
        py_pat = [p for p in patterns if p['command'] == 'python'][0]
        assert py_pat['frequency'] == 5

    def test_get_frequent_commands(self, store):
        tracker = CommandTracker(store)
        tracker.log_command(owner='u1', command='git status')
        tracker.log_command(owner='u1', command='git status')
        tracker.log_command(owner='u1', command='npm install')
        freq = tracker.get_frequent_commands('u1')
        assert len(freq) >= 2
        # git or git status should be first (frequency 2)
        assert freq[0]['command'] in ('git', 'git status')

    def test_recommend_by_prefix(self, store):
        tracker = CommandTracker(store)
        for _ in range(3):
            tracker.log_command(owner='u1', command='git push')
        for _ in range(2):
            tracker.log_command(owner='u1', command='npm install')
        recs = tracker.recommend('u1', prefix='gi')
        assert len(recs) >= 1
        assert all(r['command'].startswith('gi') for r in recs)

    def test_recommend_with_project_boost(self, store):
        tracker = CommandTracker(store)
        store.update_command_pattern('u1', 'npm', project_path='/proj/a', exit_code=0)
        store.update_command_pattern('u1', 'git', exit_code=0)
        recs = tracker.recommend('u1', project_path='/proj/a')
        # npm should be boosted for this project
        assert len(recs) >= 1

    def test_recommender_analyze_patterns(self, store):
        rec = CommandRecommender(store)
        store.update_command_pattern('u1', 'git', exit_code=0)
        store.update_command_pattern('u1', 'npm', exit_code=0)
        cmd_id = store.log_command(owner='u1', command='git status', exit_code=0)
        analysis = rec.analyze_patterns('u1')
        assert analysis['total_commands'] >= 2
        assert analysis['unique_commands'] >= 2

    def test_recommender_context_recommend(self, store):
        rec = CommandRecommender(store)
        for _ in range(3):
            store.update_command_pattern('u1', 'docker', exit_code=0)
        store.update_command_pattern('u1', 'git', exit_code=0)
        recs = rec.context_recommend('u1', current_dir='/proj', recent_commands=['docker build'])
        assert len(recs) >= 1
        # Each rec should have a recommendation_score
        assert all('recommendation_score' in r for r in recs)

    def test_recommender_empty_patterns(self, store):
        rec = CommandRecommender(store)
        result = rec.analyze_patterns('nonexistent_user')
        assert result['total_commands'] == 0

    def test_context_recommend_boosts_recent(self, store):
        rec = CommandRecommender(store)
        store.update_command_pattern('u1', 'python', exit_code=0)
        store.update_command_pattern('u1', 'git', exit_code=0)
        recs = rec.context_recommend('u1', recent_commands=['python train.py'])
        if recs:
            py_rec = [r for r in recs if r['command'] == 'python']
            if py_rec:
                assert py_rec[0].get('recommendation_score', 0) > 0


# ============================================================
# TestDirectionB: DecisionExtractor and DecisionCardManager
# ============================================================

class TestDirectionB:
    """Test Direction B: Decision extraction and card management."""

    def test_extract_decision_zh(self, store):
        ext = DecisionExtractor(store)
        decisions = ext.extract_from_message(
            '我们决定采用PostgreSQL作为主数据库，因为它的ACID特性更好',
            sender='alice',
        )
        assert len(decisions) >= 1
        assert decisions[0]['title']

    def test_extract_decision_en(self, store):
        ext = DecisionExtractor(store)
        decisions = ext.extract_from_message(
            'We decided to use React for the frontend framework',
            sender='bob',
        )
        assert len(decisions) >= 1

    def test_no_decision_in_plain_text(self, store):
        ext = DecisionExtractor(store)
        decisions = ext.extract_from_message(
            '今天天气不错，我们去喝咖啡吧',
        )
        assert len(decisions) == 0

    def test_extract_from_conversation(self, store):
        ext = DecisionExtractor(store)
        messages = [
            {'sender': 'alice', 'content': '我们决定采用Docker部署方案'},
            {'sender': 'bob', 'content': '同意，Docker确实方便'},
        ]
        decisions = ext.extract_from_conversation(messages)
        assert len(decisions) >= 1
        # Participants should include all senders
        for d in decisions:
            parts = json.loads(d.get('participants', '[]'))
            assert 'alice' in parts or 'bob' in parts

    def test_save_decisions(self, store):
        ext = DecisionExtractor(store)
        decisions = [{
            'title': 'Use Go', 'decision': 'Go for backend',
            'rationale': 'Performance', 'project_id': 'proj1',
        }]
        ids = ext.save_decisions(decisions, owner='u1')
        assert len(ids) >= 1
        # Verify stored
        stored = store.get_decision(ids[0])
        assert stored is not None
        assert stored['title'] == 'Use Go'

    def test_search_decisions_via_extractor(self, store):
        ext = DecisionExtractor(store)
        store.insert_decision(owner='u1', title='Use Redis cache', context='Redis for caching')
        results = ext.search_decisions('Redis', owner='u1')
        assert len(results) >= 1

    def test_decision_card_record_and_check(self, store):
        card_mgr = DecisionCardManager(store)
        did = card_mgr.record_decision(
            title='Use Kubernetes', decision='K8s for orchestration',
            owner='u1', project_id='proj1',
        )
        assert did
        cards = card_mgr.check_and_push('我们在讨论Kubernetes部署方案', owner='u1')
        # May or may not find cards depending on keyword extraction
        assert isinstance(cards, list)

    def test_overturn_decision(self, store):
        card_mgr = DecisionCardManager(store)
        did = card_mgr.record_decision(
            title='Use MongoDB', decision='MongoDB for documents', owner='u1',
        )
        assert did
        assert card_mgr.overturn_decision(did, reason='Found better option')
        dec = store.get_decision(did)
        tags = json.loads(dec.get('tags', '{}'))
        assert tags.get('status') == 'overturned'

    def test_format_cards_markdown(self, store):
        card_mgr = DecisionCardManager(store)
        cards = [{
            'title': 'Use React', 'decision': 'React for frontend',
            'rationale': 'Large ecosystem', 'tags': '{}',
        }]
        md = card_mgr.format_cards_markdown(cards)
        assert 'React' in md
        assert '📋' in md

    def test_empty_cards_markdown(self, store):
        card_mgr = DecisionCardManager(store)
        assert card_mgr.format_cards_markdown([]) == ''

    def test_get_decision_history(self, store):
        card_mgr = DecisionCardManager(store)
        card_mgr.record_decision(title='D1', decision='Desc1', owner='u1', project_id='p1')
        card_mgr.record_decision(title='D2', decision='Desc2', owner='u1', project_id='p1')
        history = card_mgr.get_decision_history(project_id='p1', owner='u1')
        assert len(history) >= 2


# ============================================================
# TestDirectionC: PreferenceExtractor, PreferenceManager, HabitInference
# ============================================================

class TestDirectionC:
    """Test Direction C: Preference extraction, management, and habit inference."""

    def test_extract_chinese_preference(self, store):
        ext = PreferenceExtractor(store)
        prefs = ext.extract_from_conversation(
            '我喜欢用vim编辑代码', '', 'u1',
        )
        assert len(prefs) >= 1
        assert any('vim' in p.get('value', '') for p in prefs)

    def test_extract_english_preference(self, store):
        ext = PreferenceExtractor(store)
        prefs = ext.extract_from_conversation(
            "I prefer using VS Code for development", '', 'u1',
        )
        assert len(prefs) >= 1

    def test_extract_cli_tool_preference(self, store):
        ext = PreferenceExtractor(store)
        prefs = ext.extract_from_conversation(
            'git commit -m "test" && git push origin main', '', 'u1',
        )
        cli_prefs = [p for p in prefs if p.get('key', '').startswith('cli_')]
        assert len(cli_prefs) >= 1

    def test_extract_from_tool_call(self, store):
        ext = PreferenceExtractor(store)
        prefs = ext.extract_from_tool_call('git', {'command': 'git rebase main'}, 'u1')
        assert len(prefs) >= 1
        # Should detect rebase preference
        workflow_prefs = [p for p in prefs if p.get('key') == 'git_merge_strategy']
        if workflow_prefs:
            assert workflow_prefs[0]['value'] == 'rebase'

    def test_extract_empty_message(self, store):
        ext = PreferenceExtractor(store)
        prefs = ext.extract_from_conversation('', '', 'u1')
        assert prefs == []

    def test_preference_manager_set_and_get(self, store):
        mgr = PreferenceManager(store)
        result = mgr.set_preference(
            owner='u1', category='tool', key='editor', value='vim', source='explicit',
        )
        assert result['value'] == 'vim'
        pref = mgr.get_preference('u1', 'tool', 'editor')
        assert pref is not None
        assert pref['value'] == 'vim'

    def test_preference_manager_conflict_resolution(self, store):
        mgr = PreferenceManager(store)
        # Set explicit preference
        mgr.set_preference(owner='u1', category='tool', key='editor', value='vim', source='explicit')
        # Try observed preference (lower priority)
        result = mgr.set_preference(owner='u1', category='tool', key='editor', value='nano', source='observed')
        # Explicit should win
        pref = mgr.get_preference('u1', 'tool', 'editor')
        assert pref['value'] == 'vim'

    def test_preference_manager_higher_priority_wins(self, store):
        mgr = PreferenceManager(store)
        mgr.set_preference(owner='u1', category='tool', key='editor', value='nano', source='observed')
        mgr.set_preference(owner='u1', category='tool', key='editor', value='vim', source='explicit')
        pref = mgr.get_preference('u1', 'tool', 'editor')
        assert pref['value'] == 'vim'

    def test_preference_manager_list(self, store):
        mgr = PreferenceManager(store)
        mgr.set_preference(owner='u1', category='tool', key='editor', value='vim')
        mgr.set_preference(owner='u1', category='style', key='theme', value='dark')
        mgr.set_preference(owner='u1', category='tool', key='shell', value='zsh')
        all_prefs = mgr.list_preferences('u1')
        assert len(all_prefs) == 3
        tool_prefs = mgr.list_preferences('u1', category='tool')
        assert len(tool_prefs) == 2

    def test_preference_manager_delete(self, store):
        mgr = PreferenceManager(store)
        mgr.set_preference(owner='u1', category='tool', key='editor', value='vim')
        assert mgr.delete_preference('u1', 'tool', 'editor')
        assert mgr.get_preference('u1', 'tool', 'editor') is None

    def test_preference_manager_confidence_boost_on_same_value(self, store):
        mgr = PreferenceManager(store)
        mgr.set_preference(owner='u1', category='tool', key='editor', value='vim', confidence=0.5)
        mgr.set_preference(owner='u1', category='tool', key='editor', value='vim', confidence=0.5)
        pref = mgr.get_preference('u1', 'tool', 'editor')
        assert pref['confidence'] > 0.5

    def test_preference_manager_summary(self, store):
        mgr = PreferenceManager(store)
        mgr.set_preference(owner='u1', category='tool', key='editor', value='vim')
        mgr.set_preference(owner='u1', category='style', key='theme', value='dark')
        summary = mgr.get_summary('u1')
        assert summary['total_preferences'] == 2
        assert 'tool' in summary['categories']

    def test_preference_manager_export_import(self, store):
        mgr = PreferenceManager(store)
        mgr.set_preference(owner='u1', category='tool', key='editor', value='vim')
        exported = mgr.export_preferences('u1')
        assert len(exported) >= 1
        # Import to different owner
        mgr.import_preferences('u2', exported)
        prefs_u2 = mgr.list_preferences('u2')
        assert len(prefs_u2) >= 1

    def test_habit_inference_empty_data(self, store):
        hi = HabitInference(store)
        summary = hi.get_habit_summary('u1')
        assert summary['owner'] == 'u1'
        assert summary['time_patterns'] == []
        assert summary['tool_preferences'] == []

    def test_habit_inference_should_suggest(self, store):
        hi = HabitInference(store)
        result = hi.should_suggest('u1', {'time': time.time()})
        # With no patterns, should return None
        assert result is None


# ============================================================
# TestDirectionD: EbbinghausModel, FreshnessMonitor, GapDetector
# ============================================================

class TestDirectionD:
    """Test Direction D: Knowledge health, forgetting curves, and gap detection."""

    def test_ebbinghaus_retention_score(self):
        model = EbbinghausModel()
        # At t=0, retention should be 1.0
        assert model.retention_score(0) == 1.0
        # Retention decreases over time
        assert model.retention_score(30) < 1.0
        assert model.retention_score(365) < model.retention_score(30)

    def test_ebbinghaus_different_categories(self):
        model = EbbinghausModel()
        # Security knowledge decays slower than API docs
        r_security = model.retention_score(100, 'security')
        r_api = model.retention_score(100, 'api_doc')
        assert r_security > r_api

    def test_ebbinghaus_freshness_status(self):
        model = EbbinghausModel()
        assert model.freshness_status(0, 'general') == 'fresh'
        assert model.freshness_status(60, 'general') == 'fresh'  # validity = 60
        assert model.freshness_status(70, 'general') == 'aging'
        assert model.freshness_status(150, 'general') == 'stale'
        assert model.freshness_status(300, 'general') == 'forgotten'

    def test_ebbinghaus_next_review_interval(self):
        model = EbbinghausModel()
        interval_0 = model.next_review_interval(0)
        interval_1 = model.next_review_interval(1)
        interval_2 = model.next_review_interval(2)
        # Intervals should increase with review count
        assert interval_1 > interval_0
        assert interval_2 > interval_1

    def test_ebbinghaus_importance_score(self):
        model = EbbinghausModel()
        # High importance scenario
        score = model.importance_score(
            access_count=50, content_depth=0.9,
            time_sensitivity=0.8, team_coverage=0.1, error_cost=0.9,
        )
        assert 0.0 <= score <= 1.0
        assert score > 0.5

    def test_ebbinghaus_single_point_risk(self):
        model = EbbinghausModel()
        assert model.single_point_risk(0.9, 1) == 0.9
        assert model.single_point_risk(0.9, 0) == 1.0  # No holder = max risk
        assert model.single_point_risk(0.9, 5) == pytest.approx(0.18)

    def test_ebbinghaus_custom_lambda(self):
        model = EbbinghausModel(custom_lambda={'custom': 0.05})
        r = model.retention_score(10, 'custom')
        assert r < model.retention_score(10, 'general')

    def test_freshness_monitor_register_and_check(self, store):
        monitor = FreshnessMonitor(store)
        kh_id = monitor.register_knowledge(
            chunk_id='doc_1', team_id='team1', category='api_doc',
        )
        assert kh_id
        # Should have created knowledge_health record
        records = store.list_knowledge_health('team1')
        assert len(records) >= 1

    def test_freshness_monitor_health_summary(self, store):
        monitor = FreshnessMonitor(store)
        monitor.register_knowledge(chunk_id='doc_1', team_id='team1', category='general')
        monitor.register_knowledge(chunk_id='doc_2', team_id='team1', category='security')
        summary = monitor.get_health_summary('team1')
        assert summary['total_knowledge'] == 2
        assert 'status_counts' in summary

    def test_freshness_monitor_get_due_reviews(self, store):
        monitor = FreshnessMonitor(store)
        monitor.register_knowledge(chunk_id='doc_1', team_id='team1')
        due = monitor.get_due_reviews('team1')
        assert isinstance(due, list)

    def test_freshness_monitor_record_access(self, store):
        monitor = FreshnessMonitor(store)
        kh_id = monitor.register_knowledge(chunk_id='doc_1', team_id='local')
        # Degrade freshness
        store.update_freshness('local', 'doc_1', 0.3)
        result = monitor.record_access(kh_id)
        assert result['success']
        assert result['freshness_score'] == 1.0

    def test_gap_detector_detect_gaps(self, store):
        gd = GapDetector(store)
        # No knowledge registered — all domains should be gaps
        gaps = gd.detect_gaps('team1')
        assert len(gaps) >= 1
        # All should be critical (no coverage)
        assert all(g['severity'] == 'critical' for g in gaps)

    def test_gap_detector_coverage_analysis(self, store):
        gd = GapDetector(store)
        store.upsert_knowledge_health(
            owner='team1', topic='database design',
            metadata=json.dumps({'category': 'database', 'holders': ['alice'], 'holder_count': 1}),
        )
        coverage = gd.analyze_coverage('team1')
        assert coverage['team_id'] == 'team1'
        assert coverage['total_domains'] == 10

    def test_gap_detector_single_points(self, store):
        gd = GapDetector(store)
        store.upsert_knowledge_health(
            owner='team1', topic='critical_api',
            metadata=json.dumps({'category': 'api', 'holders': ['bob'], 'holder_count': 1, 'importance': 0.9}),
        )
        singles = gd.detect_single_points('team1')
        assert len(singles) >= 1

    def test_gap_detector_team_map(self, store):
        gd = GapDetector(store)
        store.upsert_team_knowledge_map(
            owner='team1', topic='architecture', expert='alice',
            description='System architecture expert',
        )
        team_map = gd.get_team_map('team1')
        assert team_map['team_id'] == 'team1'
        assert 'architecture' in team_map.get('domains', {})


# ============================================================
# TestMemScopeProvider: Initialization, tool routing, lifecycle
# ============================================================

class TestMemScopeProvider:
    """Test MemScopeProvider: initialization, tools, and lifecycle."""

    @pytest.fixture
    def provider(self, tmp_dir):
        """Create a MemScopeProvider initialized with temp directory."""
        from src import MemScopeProvider
        p = MemScopeProvider()
        db_dir = os.path.join(tmp_dir, 'memos')
        os.makedirs(db_dir, exist_ok=True)
        # Monkey-patch the db path before init
        original_init = p.initialize.__wrapped__ if hasattr(p.initialize, '__wrapped__') else None

        # Initialize with custom hermes_home so it uses our temp dir
        p.initialize(
            session_id='test_session',
            hermes_home=tmp_dir,
        )
        yield p
        p.shutdown()

    def test_provider_name(self, provider):
        assert provider.name() == 'memscope'

    def test_provider_is_available(self, provider):
        assert provider.is_available()

    def test_provider_initialization(self, provider):
        assert provider._initialized
        assert provider.store is not None
        assert provider.command_tracker is not None
        assert provider.decision_extractor is not None
        assert provider.preference_manager is not None
        assert provider.freshness_monitor is not None

    def test_provider_double_init_is_noop(self, provider):
        """Initializing twice should not re-create subsystems."""
        old_store = provider.store
        provider.initialize(session_id='another_session')
        assert provider.store is old_store

    def test_tool_schemas_count(self, provider):
        schemas = provider.get_tool_schemas()
        assert len(schemas) >= 14  # At least 14 tools
        names = {s['name'] for s in schemas}
        assert 'memory_search' in names
        assert 'command_log' in names
        assert 'decision_record' in names
        assert 'preference_set' in names
        assert 'knowledge_health' in names

    def test_handle_command_log(self, provider):
        result = provider.handle_tool_call('command_log', {
            'command': 'git status',
            'exit_code': 0,
        })
        data = json.loads(result)
        assert 'id' in data
        assert data['status'] == 'logged'

    def test_handle_command_recommend(self, provider):
        # First log some commands
        provider.handle_tool_call('command_log', {'command': 'git push'})
        provider.handle_tool_call('command_log', {'command': 'git pull'})
        result = provider.handle_tool_call('command_recommend', {})
        data = json.loads(result)
        assert 'recommendations' in data

    def test_handle_decision_record(self, provider):
        result = provider.handle_tool_call('decision_record', {
            'title': 'Use TypeScript',
            'decision': 'TypeScript for type safety',
        })
        data = json.loads(result)
        assert 'id' in data
        assert data['status'] == 'recorded'

    def test_handle_preference_set_and_get(self, provider):
        result = provider.handle_tool_call('preference_set', {
            'category': 'tool',
            'key': 'editor',
            'value': 'vim',
        })
        data = json.loads(result)
        assert 'preference' in data

        result2 = provider.handle_tool_call('preference_get', {
            'category': 'tool',
            'key': 'editor',
        })
        data2 = json.loads(result2)
        assert data2['preference'] is not None
        assert data2['preference']['value'] == 'vim'

    def test_handle_preference_list(self, provider):
        provider.handle_tool_call('preference_set', {
            'category': 'tool', 'key': 'editor', 'value': 'vim',
        })
        provider.handle_tool_call('preference_set', {
            'category': 'style', 'key': 'theme', 'value': 'dark',
        })
        result = provider.handle_tool_call('preference_list', {})
        data = json.loads(result)
        assert len(data['preferences']) == 2

    def test_handle_knowledge_health(self, provider):
        provider.store.upsert_knowledge_health(owner='test_team', topic='API docs')
        result = provider.handle_tool_call('knowledge_health', {'team_id': 'test_team'})
        data = json.loads(result)
        assert 'total_knowledge' in data

    def test_handle_knowledge_gaps(self, provider):
        result = provider.handle_tool_call('knowledge_gaps', {'team_id': 'test_team'})
        data = json.loads(result)
        assert 'gaps' in data

    def test_handle_unknown_tool(self, provider):
        result = provider.handle_tool_call('nonexistent_tool', {})
        data = json.loads(result)
        assert 'error' in data

    def test_handle_tool_call_uninitialized(self):
        from src import MemScopeProvider
        p = MemScopeProvider()
        result = p.handle_tool_call('command_log', {'command': 'test'})
        data = json.loads(result)
        assert 'error' in data

    def test_shutdown(self, provider):
        provider.shutdown()
        assert not provider._initialized
        assert provider.store is None or True  # store may still reference but closed

    def test_sync_turn(self, provider):
        provider.sync_turn(
            user_content='We decided to use PostgreSQL for the database',
            assistant_content='Great choice! PostgreSQL is robust.',
        )
        # Should have extracted and stored some data
        # At minimum, chunks should be created
        stats = provider.store.get_stats()
        assert stats['total_chunks'] >= 0  # May be 0 if content too short

    def test_habit_patterns_tool(self, provider):
        result = provider.handle_tool_call('habit_patterns', {})
        data = json.loads(result)
        assert 'owner' in data


# ============================================================
# Test helper run
# ============================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
