"""
Tests for core functionality.
"""

import json
import tempfile
from pathlib import Path

import pytest

from claude_conv_manager.core import (
    Branch,
    Conversation,
    ClaudeProject,
    analyze_conversation,
    rename_conversation,
)


class TestBranch:
    def test_display_name_with_summary(self):
        branch = Branch(
            leaf_uuid="abc123",
            message_count=10,
            timestamp="2025-01-01T00:00:00Z",
            first_user_message="Original message",
            has_summary=True,
            summary="Custom Name"
        )
        assert branch.display_name == "Custom Name"
    
    def test_display_name_without_summary(self):
        branch = Branch(
            leaf_uuid="abc123",
            message_count=10,
            timestamp="2025-01-01T00:00:00Z",
            first_user_message="Original message",
            has_summary=False,
            summary=None
        )
        assert branch.display_name == "Original message"


class TestConversation:
    def test_is_healthy_all_named(self):
        conv = Conversation(
            path=Path("test.jsonl"),
            session_id="test",
            file_size=1000,
            modified=None,
            total_messages=10,
            branches=[
                Branch("a", 5, "", "msg", True, "Name1"),
                Branch("b", 5, "", "msg", True, "Name2"),
            ]
        )
        assert conv.is_healthy is True
    
    def test_is_healthy_some_unnamed(self):
        conv = Conversation(
            path=Path("test.jsonl"),
            session_id="test",
            file_size=1000,
            modified=None,
            total_messages=10,
            branches=[
                Branch("a", 5, "", "msg", True, "Name1"),
                Branch("b", 5, "", "msg", False, None),
            ]
        )
        assert conv.is_healthy is False
        assert conv.unnamed_branches == 1


class TestAnalyzeConversation:
    def test_analyze_simple_conversation(self, tmp_path):
        """Test analyzing a simple single-branch conversation."""
        jsonl_file = tmp_path / "test.jsonl"
        
        messages = [
            {"type": "summary", "summary": "Test Conv", "leafUuid": "msg2"},
            {"type": "user", "uuid": "msg1", "parentUuid": None, "isSidechain": False,
             "message": {"content": [{"type": "text", "text": "Hello"}]},
             "timestamp": "2025-01-01T00:00:00Z"},
            {"type": "assistant", "uuid": "msg2", "parentUuid": "msg1", "isSidechain": False,
             "message": {"content": [{"type": "text", "text": "Hi there"}]},
             "timestamp": "2025-01-01T00:01:00Z"},
        ]
        
        with open(jsonl_file, 'w') as f:
            for msg in messages:
                f.write(json.dumps(msg) + '\n')
        
        conv = analyze_conversation(jsonl_file)
        
        assert conv is not None
        assert conv.branch_count == 1
        assert conv.is_healthy is True
        assert conv.branches[0].summary == "Test Conv"


class TestRenameConversation:
    def test_rename_adds_summaries_for_all_leaves(self, tmp_path):
        """Test that rename adds summary records for all branch leaves."""
        jsonl_file = tmp_path / "test.jsonl"
        
        # Create a conversation with 2 branches (fork at msg1)
        messages = [
            {"type": "user", "uuid": "root", "parentUuid": None, "isSidechain": False,
             "message": {"content": [{"type": "text", "text": "Start"}]},
             "timestamp": "2025-01-01T00:00:00Z"},
            {"type": "assistant", "uuid": "leaf1", "parentUuid": "root", "isSidechain": False,
             "message": {"content": []},
             "timestamp": "2025-01-01T00:01:00Z"},
            {"type": "assistant", "uuid": "leaf2", "parentUuid": "root", "isSidechain": False,
             "message": {"content": []},
             "timestamp": "2025-01-01T00:02:00Z"},
        ]
        
        with open(jsonl_file, 'w') as f:
            for msg in messages:
                f.write(json.dumps(msg) + '\n')
        
        success, message = rename_conversation(jsonl_file, "New Name")
        
        assert success is True
        assert "2 branches" in message
        
        # Verify summaries were added
        with open(jsonl_file, 'r') as f:
            lines = f.readlines()
        
        summary_count = sum(1 for line in lines if '"type":"summary"' in line)
        assert summary_count == 2  # One for each leaf
