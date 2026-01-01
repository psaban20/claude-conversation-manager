"""
Claude Conversation Manager
===========================

A tool for managing Claude Code VS Code extension conversations.

Key insight: The extension stores conversations in .jsonl files with multiple 
branches. Each branch has a "leaf" node, and the extension picks one branch 
to display. To properly rename a conversation, you must add summary records 
for ALL leaf nodes.
"""

__version__ = "0.1.0"
__author__ = "Pablo Saban"

from .core import (
    ClaudeProject,
    Conversation,
    Branch,
    get_claude_projects_dir,
    list_projects,
    load_project_conversations,
    analyze_conversation,
    rename_conversation,
)

__all__ = [
    "ClaudeProject",
    "Conversation", 
    "Branch",
    "get_claude_projects_dir",
    "list_projects",
    "load_project_conversations",
    "analyze_conversation",
    "rename_conversation",
]
