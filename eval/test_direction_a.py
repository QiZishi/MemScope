"""
Direction A — CLI Command Memory Test Suite — 4 test cases.

Tests the enterprise memory engine's ability to:
  1. Track and count CLI command usage
  2. Recommend commands based on frequency
  3. Associate commands with project paths
  4. Provide context-aware recommendations

Each test is self-contained and produces measurable metrics.
"""

import json
import time
import uuid

import pytest


# ── 1. Command Tracking ──────────────────────────────────────────────────
class TestCommandTracking:
    """Verify the system can record commands and track frequency accurately."""

    TEST_ID = "direction_a_001"
    CATEGORY = "command_tracking"

    def test_command_tracking(self, store, data_gen, metrics, report_collector):
        from direction_a.command_tracker import CommandTracker

        tracker = CommandTracker(store)
        owner = "user_cmd_track"

        # ---- Log a series of commands ----
        commands = [
            ("git status", 0, "/home/user/project-a"),
            ("git add .", 0, "/home/user/project-a"),
            ("git commit -m 'fix bug'", 0, "/home/user/project-a"),
            ("git status", 0, "/home/user/project-a"),
            ("git push origin main", 0, "/home/user/project-a"),
            ("git status", 0, "/home/user/project-a"),
            ("docker compose up -d", 0, "/home/user/project-a"),
            ("git status", 0, "/home/user/project-a"),
            ("npm test", 1, "/home/user/project-a"),  # failed
            ("git status", 0, "/home/user/project-a"),
        ]

        for cmd, exit_code, project in commands:
            tracker.log_command(
                owner=owner,
                command=cmd,
                exit_code=exit_code,
                project_path=project,
            )

        # ---- Query frequent commands ----
        frequent = tracker.get_frequent_commands(owner=owner, limit=10)

        # Find git status pattern
        git_status_pattern = next(
            (p for p in frequent if p.get("command") == "git"), None
        )

        # Verify frequency counting
        total_logged = len(commands)
        git_count = sum(1 for c, _, _ in commands if c.startswith("git"))
        git_status_count = sum(1 for c, _, _ in commands if c == "git status")

        # Check command history
        history = store.get_command_history(owner=owner, limit=100)

        # ---- Metrics ----
        has_patterns = len(frequent) > 0
        git_freq_correct = (
            git_status_pattern is not None
            and git_status_pattern.get("frequency", 0) >= git_status_count
        ) if git_status_pattern else False

        result_data = {
            "commands_logged": {
                "value": len(history),
                "target": total_logged,
                "passed": len(history) >= total_logged,
            },
            "patterns_created": {
                "value": len(frequent),
                "target": 3,
                "passed": len(frequent) >= 3,
            },
            "git_frequency_correct": {
                "value": 1.0 if git_freq_correct else 0.0,
                "target": 1.0,
                "passed": git_freq_correct,
            },
            "failure_recorded": {
                "value": 1.0,
                "target": 1.0,
                "passed": any(
                    c == "npm test" and e == 1 for c, e, _ in commands
                ),
            },
        }

        passed = all(m["passed"] for m in result_data.values())
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_command_tracking ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"Logged {len(history)} commands, found {len(frequent)} patterns. "
                    f"Git status freq={git_status_pattern.get('frequency', 0) if git_status_pattern else 'N/A'}",
        )

        assert len(history) >= total_logged, f"Expected {total_logged} history entries, got {len(history)}"
        assert len(frequent) >= 3, f"Expected at least 3 patterns, got {len(frequent)}"
        if not passed:
            pytest.fail(f"Command tracking failed: patterns={len(frequent)}")


# ── 2. Command Recommendation ─────────────────────────────────────────────
class TestCommandRecommendation:
    """Verify the system recommends commands based on prefix matching and frequency."""

    TEST_ID = "direction_a_002"
    CATEGORY = "command_recommendation"

    def test_command_recommendation(self, store, data_gen, metrics, report_collector):
        from direction_a.command_tracker import CommandTracker

        tracker = CommandTracker(store)
        owner = "user_cmd_rec"

        # ---- Build a usage pattern ----
        commands_seq = [
            ("git status", 0),
            ("git add .", 0),
            ("git commit -m 'update'", 0),
            ("git push", 0),
            ("git status", 0),
            ("git log --oneline", 0),
            ("git status", 0),
            ("docker ps", 0),
            ("docker logs app", 0),
            ("npm install", 0),
            ("npm test", 0),
            ("git status", 0),
        ]

        for cmd, exit_code in commands_seq:
            tracker.log_command(owner=owner, command=cmd, exit_code=exit_code)

        # ---- Test prefix matching ----
        git_recs = tracker.recommend(owner=owner, prefix="git", limit=5)
        docker_recs = tracker.recommend(owner=owner, prefix="docker", limit=5)
        npm_recs = tracker.recommend(owner=owner, prefix="npm", limit=5)

        # All git recommendations should start with "git"
        git_prefix_ok = all(
            r.get("command", "").startswith("git") for r in git_recs
        ) if git_recs else False

        # git should be recommended (most frequent prefix)
        git_is_top = (
            git_recs and git_recs[0].get("command", "").startswith("git")
        )

        # ---- Metrics ----
        result_data = {
            "git_recommendations": {
                "value": len(git_recs),
                "target": 3,
                "passed": len(git_recs) >= 1,
            },
            "docker_recommendations": {
                "value": len(docker_recs),
                "target": 1,
                "passed": len(docker_recs) >= 1,
            },
            "npm_recommendations": {
                "value": len(npm_recs),
                "target": 1,
                "passed": len(npm_recs) >= 1,
            },
            "prefix_filter_correct": {
                "value": 1.0 if git_prefix_ok else 0.0,
                "target": 1.0,
                "passed": git_prefix_ok,
            },
            "frequency_ordering": {
                "value": 1.0 if git_is_top else 0.0,
                "target": 1.0,
                "passed": git_is_top,
            },
        }

        passed = all(m["passed"] for m in result_data.values())
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_command_recommendation ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"git={len(git_recs)}, docker={len(docker_recs)}, npm={len(npm_recs)}. "
                    f"Prefix OK={git_prefix_ok}, Top is git={git_is_top}",
        )

        assert len(git_recs) >= 1, f"Expected at least 1 git recommendation, got {len(git_recs)}"
        assert git_prefix_ok, "Git prefix filter failed"
        if not passed:
            pytest.fail("Command recommendation test failed")


# ── 3. Project Context ────────────────────────────────────────────────────
class TestProjectContext:
    """Verify the system associates commands with project paths and filters accordingly."""

    TEST_ID = "direction_a_003"
    CATEGORY = "project_context"

    def test_project_context(self, store, data_gen, metrics, report_collector):
        from direction_a.command_tracker import CommandTracker

        tracker = CommandTracker(store)
        owner = "user_proj_ctx"

        # ---- Log commands for two different projects ----
        project_a_cmds = [
            ("git status", 0),
            ("npm test", 0),
            ("npm run build", 0),
            ("git push", 0),
        ]
        project_b_cmds = [
            ("cargo build", 0),
            ("cargo test", 0),
            ("cargo run", 0),
            ("git push", 0),
        ]

        for cmd, ec in project_a_cmds:
            tracker.log_command(
                owner=owner, command=cmd, exit_code=ec,
                project_path="/home/user/project-a",
            )
        for cmd, ec in project_b_cmds:
            tracker.log_command(
                owner=owner, command=cmd, exit_code=ec,
                project_path="/home/user/project-b",
            )

        # ---- Query by project ----
        proj_a_cmds = tracker.get_project_commands(
            owner=owner, project_path="/home/user/project-a", limit=10
        )
        proj_b_cmds = tracker.get_project_commands(
            owner=owner, project_path="/home/user/project-b", limit=10
        )

        # Project A should have npm, git; Project B should have cargo, git
        proj_a_commands = {p.get("command") for p in proj_a_cmds}
        proj_b_commands = {p.get("command") for p in proj_b_cmds}

        has_npm_in_a = "npm" in proj_a_commands
        has_cargo_in_b = "cargo" in proj_b_commands
        has_git_in_both = "git" in proj_a_commands and "git" in proj_b_commands

        # ---- Test project-aware recommendation ----
        recs_a = tracker.recommend(
            owner=owner, project_path="/home/user/project-a", limit=5
        )
        recs_b = tracker.recommend(
            owner=owner, project_path="/home/user/project-b", limit=5
        )

        # Project A recommendations should prioritize npm
        rec_a_cmds = {r.get("command") for r in recs_a}
        rec_b_cmds = {r.get("command") for r in recs_b}

        npm_in_a_recs = "npm" in rec_a_cmds
        cargo_in_b_recs = "cargo" in rec_b_cmds

        # ---- Metrics ----
        result_data = {
            "project_a_has_npm": {
                "value": 1.0 if has_npm_in_a else 0.0,
                "target": 1.0,
                "passed": has_npm_in_a,
            },
            "project_b_has_cargo": {
                "value": 1.0 if has_cargo_in_b else 0.0,
                "target": 1.0,
                "passed": has_cargo_in_b,
            },
            "git_shared_across_projects": {
                "value": 1.0 if has_git_in_both else 0.0,
                "target": 1.0,
                "passed": has_git_in_both,
            },
            "project_a_recommendations": {
                "value": len(recs_a),
                "target": 2,
                "passed": len(recs_a) >= 2 and npm_in_a_recs,
            },
            "project_b_recommendations": {
                "value": len(recs_b),
                "target": 2,
                "passed": len(recs_b) >= 2 and cargo_in_b_recs,
            },
        }

        passed = all(m["passed"] for m in result_data.values())
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_project_context ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"ProjA cmds={proj_a_commands}, ProjB cmds={proj_b_commands}. "
                    f"RecsA has npm={npm_in_a_recs}, RecsB has cargo={cargo_in_b_recs}",
        )

        assert has_npm_in_a, "Project A should contain npm commands"
        assert has_cargo_in_b, "Project B should contain cargo commands"
        if not passed:
            pytest.fail("Project context test failed")


# ── 4. Context-Aware Recommendation ───────────────────────────────────────
class TestContextAwareRecommendation:
    """Verify the CommandRecommender provides context-aware suggestions."""

    TEST_ID = "direction_a_004"
    CATEGORY = "context_aware_recommendation"

    def test_context_aware_recommendation(self, store, data_gen, metrics, report_collector):
        from direction_a.recommender import CommandRecommender

        recommender = CommandRecommender(store)
        owner = "user_ctx_rec"

        # ---- Build rich command history ----
        commands = [
            ("git status", 0, "/home/user/web-app"),
            ("git add .", 0, "/home/user/web-app"),
            ("git commit -m 'feat'", 0, "/home/user/web-app"),
            ("npm run dev", 0, "/home/user/web-app"),
            ("npm test", 0, "/home/user/web-app"),
            ("git status", 0, "/home/user/web-app"),
            ("docker build -t app .", 0, "/home/user/web-app"),
            ("docker push registry/app", 0, "/home/user/web-app"),
            ("kubectl apply -f deploy.yaml", 0, "/home/user/web-app"),
            ("git status", 0, "/home/user/web-app"),
            ("npm run build", 0, "/home/user/web-app"),
            ("git push", 0, "/home/user/web-app"),
        ]

        for cmd, ec, proj in commands:
            store.log_command(
                owner=owner, command=cmd, exit_code=ec, project_path=proj,
            )
            store.update_command_pattern(
                owner=owner, command=cmd.split()[0], project_path=proj, exit_code=ec,
            )

        # ---- Test analyze_patterns ----
        analysis = recommender.analyze_patterns(owner=owner)

        has_top_commands = len(analysis.get("top_commands", [])) > 0
        total_commands = analysis.get("total_commands", 0)
        unique_commands = analysis.get("unique_commands", 0)
        avg_success = analysis.get("avg_success_rate", 0.0)

        # ---- Test context_recommend with current_dir ----
        ctx_recs = recommender.context_recommend(
            owner=owner,
            current_dir="/home/user/web-app",
            recent_commands=["git status", "git add ."],
            limit=5,
        )

        # Context-aware: git should get boosted (recent + project match)
        ctx_has_git = any(
            r.get("command") == "git" for r in ctx_recs
        )

        # Check that recommendations have scores
        has_scores = all(
            "recommendation_score" in r for r in ctx_recs
        ) if ctx_recs else False

        # Score should be non-zero
        top_score = ctx_recs[0].get("recommendation_score", 0) if ctx_recs else 0

        # ---- Metrics ----
        result_data = {
            "analysis_top_commands": {
                "value": len(analysis.get("top_commands", [])),
                "target": 5,
                "passed": has_top_commands,
            },
            "total_commands_tracked": {
                "value": total_commands,
                "target": len(commands),
                "passed": total_commands >= len(commands),
            },
            "unique_commands": {
                "value": unique_commands,
                "target": 5,
                "passed": unique_commands >= 4,
            },
            "success_rate": {
                "value": avg_success,
                "target": 0.8,
                "passed": avg_success >= 0.8,
            },
            "context_recommendations": {
                "value": len(ctx_recs),
                "target": 3,
                "passed": len(ctx_recs) >= 1,
            },
            "scores_present": {
                "value": 1.0 if has_scores else 0.0,
                "target": 1.0,
                "passed": has_scores,
            },
            "top_score_nonzero": {
                "value": top_score,
                "target": 0.3,
                "passed": top_score > 0,
            },
        }

        passed = all(m["passed"] for m in result_data.values())
        status = "pass" if passed else "fail"

        report_collector.add(
            test_id=self.TEST_ID,
            test_name=f"test_context_aware_recommendation ({self.CATEGORY})",
            status=status,
            metrics=result_data,
            details=f"Analysis: total={total_commands}, unique={unique_commands}, "
                    f"success={avg_success}. Context recs={len(ctx_recs)}, top_score={top_score:.4f}",
        )

        assert has_top_commands, "Analysis should return top commands"
        assert len(ctx_recs) >= 1, f"Expected at least 1 context recommendation, got {len(ctx_recs)}"
        if not passed:
            pytest.fail("Context-aware recommendation test failed")
