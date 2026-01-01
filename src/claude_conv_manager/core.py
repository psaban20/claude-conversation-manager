"""
Core logic for Claude Conversation Manager.

This module contains the data models and functions for analyzing and 
manipulating Claude Code conversation files.
"""

import os
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from pathlib import Path


def get_claude_projects_dir() -> Path:
    """Get the Claude projects directory for the current OS."""
    if sys.platform == 'win32':
        base = os.environ.get('USERPROFILE', '')
    else:
        base = os.path.expanduser('~')
    return Path(base) / '.claude' / 'projects'


@dataclass
class Branch:
    """Represents a conversation branch (path from root to leaf)."""
    leaf_uuid: str
    message_count: int
    timestamp: str
    first_user_message: str
    has_summary: bool
    summary: Optional[str] = None
    
    @property
    def display_name(self) -> str:
        """What name would be shown for this branch."""
        return self.summary if self.has_summary else self.first_user_message


@dataclass 
class Conversation:
    """Represents a Claude Code conversation file."""
    path: Path
    session_id: str
    file_size: int
    modified: datetime
    total_messages: int
    branches: list[Branch] = field(default_factory=list)
    
    @property
    def filename(self) -> str:
        return self.path.name
    
    @property
    def branch_count(self) -> int:
        return len(self.branches)
    
    @property
    def unnamed_branches(self) -> int:
        return sum(1 for b in self.branches if not b.has_summary)
    
    @property
    def is_healthy(self) -> bool:
        """All branches have summaries."""
        return all(b.has_summary for b in self.branches)
    
    @property
    def display_name(self) -> str:
        """The name that would likely be shown in the UI."""
        if not self.branches:
            return "Unknown"
        # Extension sorts by timestamp desc, picks first
        sorted_branches = sorted(self.branches, key=lambda b: b.timestamp, reverse=True)
        return sorted_branches[0].display_name
    
    @property
    def primary_summary(self) -> Optional[str]:
        """Get the summary if any branch has one."""
        for b in self.branches:
            if b.has_summary:
                return b.summary
        return None


@dataclass
class ClaudeProject:
    """Represents a Claude Code project directory."""
    path: Path
    name: str
    conversations: list[Conversation] = field(default_factory=list)
    
    @property
    def display_name(self) -> str:
        """Human-readable project name from directory."""
        # Convert c--dropboxfolders-pablosaban-... to C:/dropboxfolders/pablosaban/...
        name = self.name
        if name.startswith('c--'):
            name = 'C:/' + name[3:].replace('-', '/')
        return name
    
    @property
    def conversation_count(self) -> int:
        return len(self.conversations)
    
    @property
    def unhealthy_count(self) -> int:
        return sum(1 for c in self.conversations if not c.is_healthy)



# =============================================================================
# Analysis Functions
# =============================================================================

def _parse_jsonl_file(path: Path) -> tuple[list[dict], dict[str, str]]:
    """
    Parse a .jsonl conversation file.
    
    Returns:
        tuple: (list of message records, dict mapping leafUuid -> summary)
    """
    messages = {}
    summaries = {}
    
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line.strip())
                msg_type = data.get('type')
                
                if msg_type in ['user', 'assistant', 'attachment', 'system']:
                    if data.get('uuid'):
                        messages[data['uuid']] = data
                elif msg_type == 'summary' and data.get('leafUuid'):
                    summaries[data['leafUuid']] = data.get('summary', '')
            except json.JSONDecodeError:
                continue
    
    return messages, summaries


def _find_leaf_nodes(messages: dict) -> set[str]:
    """Find all leaf UUIDs (messages with no children)."""
    all_uuids = set(messages.keys())
    parent_uuids = {m.get('parentUuid') for m in messages.values() if m.get('parentUuid')}
    return all_uuids - parent_uuids


def _get_transcript(messages: dict, leaf_uuid: str) -> list[dict]:
    """Walk from leaf to root and return the message chain."""
    chain = []
    current = messages.get(leaf_uuid)
    while current:
        chain.append(current)
        parent = current.get('parentUuid')
        current = messages.get(parent) if parent else None
    return list(reversed(chain))


def _get_first_user_message(transcript: list[dict]) -> str:
    """Extract the first meaningful user message from a transcript."""
    for msg in transcript:
        if msg.get('type') != 'user':
            continue
        content = msg.get('message', {}).get('content', [])
        
        if isinstance(content, str):
            return content[:50] + '...' if len(content) > 50 else content
        
        if isinstance(content, list):
            # First pass: skip IDE system messages
            for c in content:
                if isinstance(c, dict) and c.get('type') == 'text':
                    text = c.get('text', '')
                    if not text.startswith('<ide_'):
                        return text[:50] + '...' if len(text) > 50 else text
            
            # Fallback: use any text content
            for c in content:
                if isinstance(c, dict) and c.get('type') == 'text':
                    text = c.get('text', '')
                    return text[:50] + '...' if len(text) > 50 else text
    
    return 'No prompt'


def _is_branch_sidechain(messages: dict, leaf_uuid: str) -> bool:
    """Check if a branch is a sidechain by examining its root."""
    current = messages.get(leaf_uuid)
    while current:
        parent = current.get('parentUuid')
        if not parent:
            return current.get('isSidechain', False)
        current = messages.get(parent)
    return False


def analyze_conversation(path: Path) -> Optional[Conversation]:
    """
    Analyze a conversation file and return detailed information.
    
    Args:
        path: Path to the .jsonl file
        
    Returns:
        Conversation object with branch details, or None if invalid
    """
    if not path.exists() or not path.suffix == '.jsonl':
        return None
    
    try:
        messages, summaries = _parse_jsonl_file(path)
        
        if not messages:
            return None
        
        leaf_uuids = _find_leaf_nodes(messages)
        
        # Build branches (non-sidechain only)
        branches = []
        for leaf in leaf_uuids:
            if _is_branch_sidechain(messages, leaf):
                continue
            
            transcript = _get_transcript(messages, leaf)
            if not transcript:
                continue
            
            last_msg = transcript[-1]
            first_user_msg = _get_first_user_message(transcript)
            has_summary = last_msg['uuid'] in summaries
            
            branch = Branch(
                leaf_uuid=leaf,
                message_count=len(transcript),
                timestamp=last_msg.get('timestamp', ''),
                first_user_message=first_user_msg,
                has_summary=has_summary,
                summary=summaries.get(last_msg['uuid'])
            )
            branches.append(branch)
        
        # Sort by timestamp descending
        branches.sort(key=lambda b: b.timestamp, reverse=True)
        
        stat = path.stat()
        session_id = path.stem  # filename without extension
        
        return Conversation(
            path=path,
            session_id=session_id,
            file_size=stat.st_size,
            modified=datetime.fromtimestamp(stat.st_mtime),
            total_messages=len(messages),
            branches=branches
        )
        
    except Exception as e:
        print(f"Error analyzing {path}: {e}")
        return None



def rename_conversation(path: Path, new_name: str) -> tuple[bool, str]:
    """
    Rename a conversation by adding summary records for ALL branches.
    
    This ensures the name is shown regardless of which branch the 
    extension picks to display.
    
    Args:
        path: Path to the .jsonl file
        new_name: New name for the conversation
        
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if not lines:
            return False, "File is empty"
        
        # Parse to find all leaf nodes
        messages, _ = _parse_jsonl_file(path)
        leaf_uuids = _find_leaf_nodes(messages)
        
        # Get non-sidechain leaves
        target_leaves = []
        for leaf in leaf_uuids:
            if not _is_branch_sidechain(messages, leaf):
                target_leaves.append(leaf)
        
        if not target_leaves:
            return False, "No valid branches found"
        
        # Remove existing summary records
        new_lines = []
        for line in lines:
            try:
                data = json.loads(line.strip())
                if data.get('type') != 'summary':
                    new_lines.append(line)
            except json.JSONDecodeError:
                new_lines.append(line)
        
        # Create summary records for ALL leaves
        summary_records = []
        for leaf in target_leaves:
            record = {
                "type": "summary",
                "summary": new_name,
                "leafUuid": leaf
            }
            summary_records.append(json.dumps(record, separators=(',', ':')) + '\n')
        
        # Insert summaries at the beginning
        final_lines = summary_records + new_lines
        
        # Write back
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(final_lines)
        
        return True, f"Renamed to '{new_name}' ({len(target_leaves)} branches updated)"
        
    except Exception as e:
        return False, f"Error: {str(e)}"


def list_projects(projects_dir: Optional[Path] = None) -> list[ClaudeProject]:
    """
    List all Claude Code projects.
    
    Args:
        projects_dir: Override the default projects directory
        
    Returns:
        List of ClaudeProject objects
    """
    if projects_dir is None:
        projects_dir = get_claude_projects_dir()
    
    if not projects_dir.exists():
        return []
    
    projects = []
    
    for item in projects_dir.iterdir():
        if not item.is_dir():
            continue
        
        # Count conversation files (exclude agent-* and backups)
        conv_files = [
            f for f in item.iterdir()
            if f.suffix == '.jsonl' 
            and not f.name.startswith('agent-')
            and not f.name.endswith('.backup')
        ]
        
        if not conv_files:
            continue
        
        project = ClaudeProject(
            path=item,
            name=item.name,
            conversations=[]  # Lazy load
        )
        projects.append(project)
    
    return projects


def load_project_conversations(project: ClaudeProject) -> None:
    """
    Load all conversations for a project.
    
    Args:
        project: The project to load conversations for
    """
    project.conversations = []
    
    for item in project.path.iterdir():
        if not item.suffix == '.jsonl':
            continue
        if item.name.startswith('agent-'):
            continue
        if item.name.endswith('.backup'):
            continue
        
        conv = analyze_conversation(item)
        if conv:
            project.conversations.append(conv)
    
    # Sort by modified date descending
    project.conversations.sort(key=lambda c: c.modified, reverse=True)

