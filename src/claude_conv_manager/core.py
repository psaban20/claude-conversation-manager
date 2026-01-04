"""
Core logic for Claude Conversation Manager.

This module contains the data models and functions for analyzing and 
manipulating Claude Code conversation files.
"""

import os
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path


def get_relative_time(dt: datetime) -> str:
    """Convert datetime to VS Code style relative time (now, 14d, 1mo, etc.)."""
    now = datetime.now()
    diff = now - dt
    
    if diff < timedelta(minutes=5):
        return "now"
    elif diff < timedelta(hours=1):
        return f"{int(diff.seconds / 60)}m"
    elif diff < timedelta(days=1):
        return f"{int(diff.seconds / 3600)}h"
    elif diff < timedelta(days=30):
        return f"{diff.days}d"
    elif diff < timedelta(days=365):
        months = diff.days // 30
        return f"{months}mo"
    else:
        years = diff.days // 365
        return f"{years}y"


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
    
    @property
    def vscode_current_title(self) -> str:
        """What VS Code is currently showing for this conversation.
        
        VS Code picks the most recent non-sidechain branch, then shows either
        its summary (if exists) or its first non-meta user message.
        """
        if not self.branches:
            return "Unknown"
        
        # VS Code sorts by timestamp descending and picks the first one
        sorted_branches = sorted(self.branches, key=lambda b: b.timestamp, reverse=True)
        
        # Find the first branch - this is what VS Code would display
        if sorted_branches:
            branch = sorted_branches[0]
            if branch.has_summary:
                return branch.summary
            else:
                # Return the first user message (this is what VS Code shows)
                return branch.first_user_message
        
        return "Unknown"


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


def _get_first_user_message(transcript: list[dict], skip_meta: bool = True) -> str:
    """Extract the first meaningful user message from a transcript.
    
    VS Code's extension skips 'meta' messages when determining the display name.
    Meta messages include session continuations like "This session is being continued..."
    """
    for msg in transcript:
        if msg.get('type') != 'user':
            continue
        
        # Skip meta messages (VS Code does this via isMeta flag)
        if skip_meta and msg.get('isMeta'):
            continue
            
        content = msg.get('message', {}).get('content', [])
        
        if isinstance(content, str):
            # Skip session continuation messages
            if skip_meta and content.startswith('This session is being continued'):
                continue
            return content[:50] + '...' if len(content) > 50 else content
        
        if isinstance(content, list):
            # First pass: skip IDE system messages and session continuations
            for c in content:
                if isinstance(c, dict) and c.get('type') == 'text':
                    text = c.get('text', '')
                    if text.startswith('<ide_'):
                        continue
                    if skip_meta and text.startswith('This session is being continued'):
                        continue
                    return text[:50] + '...' if len(text) > 50 else text
            
            # Fallback: use any text content (even if meta)
            for c in content:
                if isinstance(c, dict) and c.get('type') == 'text':
                    text = c.get('text', '')
                    if not text.startswith('<ide_'):
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



def path_to_project_name(path: Path) -> str:
    """Convert a filesystem path to Claude project folder name.
    
    Example: C:/Users/me/projects/my-app 
         -> c--Users-me-projects-my-app
    """
    # Normalize the path
    path_str = str(path.resolve())
    
    # Handle Windows drive letter
    if len(path_str) >= 2 and path_str[1] == ':':
        drive = path_str[0].lower()
        rest = path_str[2:].replace('\\', '/').replace('/', '-')
        return f"{drive}-{rest}"
    else:
        # Unix-style path
        return path_str.replace('/', '-').lstrip('-')


def get_or_create_project(target_path: Path) -> tuple[Path, bool]:
    """Get or create a project folder for the given filesystem path.
    
    Args:
        target_path: The filesystem path to associate with a project
        
    Returns:
        tuple: (project_folder_path, was_created)
    """
    projects_dir = get_claude_projects_dir()
    project_name = path_to_project_name(target_path)
    project_path = projects_dir / project_name
    
    was_created = False
    if not project_path.exists():
        project_path.mkdir(parents=True)
        was_created = True
    
    return project_path, was_created


def move_conversation(conv_path: Path, target_project_path: Path) -> tuple[bool, str]:
    """Move a conversation file to a different project folder.
    
    Args:
        conv_path: Path to the conversation .jsonl file
        target_project_path: Path to the target project folder
        
    Returns:
        tuple: (success: bool, message: str)
    """
    import shutil
    
    try:
        if not conv_path.exists():
            return False, f"Source file not found: {conv_path}"
        
        if not target_project_path.exists():
            return False, f"Target project not found: {target_project_path}"
        
        # Check if file already exists in target
        target_file = target_project_path / conv_path.name
        if target_file.exists():
            return False, f"File already exists in target project: {conv_path.name}"
        
        # Move the main file
        shutil.move(str(conv_path), str(target_file))
        
        # Also move backup if exists
        backup_path = conv_path.with_suffix('.jsonl.backup')
        if backup_path.exists():
            target_backup = target_project_path / backup_path.name
            shutil.move(str(backup_path), str(target_backup))
        
        return True, f"Moved to {target_project_path.name}"
        
    except Exception as e:
        return False, f"Error moving file: {str(e)}"



def archive_conversation(conv_path: Path) -> tuple[bool, str]:
    """Archive a conversation by moving it to an archive subfolder.
    
    The archive folder is created within the same project directory.
    Archived conversations won't appear in Claude Code's Past Conversations.
    
    Args:
        conv_path: Path to the conversation .jsonl file
        
    Returns:
        tuple: (success: bool, message: str)
    """
    import shutil
    
    try:
        if not conv_path.exists():
            return False, f"File not found: {conv_path}"
        
        # Create archive folder in the same project
        project_dir = conv_path.parent
        archive_dir = project_dir / "archive"
        archive_dir.mkdir(exist_ok=True)
        
        # Check if already archived
        target_file = archive_dir / conv_path.name
        if target_file.exists():
            return False, f"File already exists in archive: {conv_path.name}"
        
        # Move the main file
        shutil.move(str(conv_path), str(target_file))
        
        # Also move backup if exists
        backup_path = conv_path.with_suffix('.jsonl.backup')
        if backup_path.exists():
            target_backup = archive_dir / backup_path.name
            shutil.move(str(backup_path), str(target_backup))
        
        return True, "Conversation archived"
        
    except Exception as e:
        return False, f"Error archiving: {str(e)}"


def restore_conversation(archived_path: Path) -> tuple[bool, str]:
    """Restore an archived conversation back to the project root.
    
    Args:
        archived_path: Path to the archived .jsonl file
        
    Returns:
        tuple: (success: bool, message: str)
    """
    import shutil
    
    try:
        if not archived_path.exists():
            return False, f"File not found: {archived_path}"
        
        # Get the project root (parent of archive folder)
        archive_dir = archived_path.parent
        project_dir = archive_dir.parent
        
        # Check if file exists in project root
        target_file = project_dir / archived_path.name
        if target_file.exists():
            return False, f"File already exists in project: {archived_path.name}"
        
        # Move the main file
        shutil.move(str(archived_path), str(target_file))
        
        # Also move backup if exists
        backup_path = archived_path.with_suffix('.jsonl.backup')
        if backup_path.exists():
            target_backup = project_dir / backup_path.name
            shutil.move(str(backup_path), str(target_backup))
        
        return True, "Conversation restored"
        
    except Exception as e:
        return False, f"Error restoring: {str(e)}"


def get_conversation_summary(path: Path, max_words: int = 500) -> str:
    """Generate a summary of a conversation's content.
    
    Extracts key user messages and topics discussed to create
    a readable overview of what the conversation covered.
    
    Args:
        path: Path to the .jsonl file
        max_words: Maximum words in summary (default 500)
        
    Returns:
        Summary string
    """
    try:
        messages, summaries = _parse_jsonl_file(path)
        
        if not messages:
            return "Empty conversation"
        
        # Collect user messages (skip meta/system messages)
        user_messages = []
        assistant_snippets = []
        
        for msg in messages.values():
            msg_type = msg.get('type')
            
            if msg_type == 'user':
                # Skip meta messages
                if msg.get('isMeta'):
                    continue
                    
                content = msg.get('message', {}).get('content', [])
                text = _extract_text_from_content(content)
                
                # Skip session continuation messages
                if text and not text.startswith('This session is being continued'):
                    # Skip IDE system messages
                    if not text.startswith('<ide_'):
                        user_messages.append(text)
            
            elif msg_type == 'assistant':
                content = msg.get('message', {}).get('content', [])
                text = _extract_text_from_content(content)
                if text and len(text) > 50:
                    # Get first 200 chars of substantial responses
                    assistant_snippets.append(text[:200])
        
        # Build summary
        lines = []
        
        # Header with stats
        lines.append(f"## Conversation Overview")
        lines.append(f"**Messages:** {len(messages)} total ({len(user_messages)} user prompts)")
        lines.append("")
        
        # Main topics (from user messages)
        lines.append("## Key Topics & Requests")
        lines.append("")
        
        # Deduplicate and limit user messages
        seen = set()
        unique_messages = []
        for msg in user_messages:
            # Normalize for dedup
            normalized = msg[:100].lower().strip()
            if normalized not in seen:
                seen.add(normalized)
                unique_messages.append(msg)
        
        # Show top messages (limit based on word count)
        word_count = 0
        for i, msg in enumerate(unique_messages[:20], 1):
            # Truncate long messages
            if len(msg) > 200:
                msg = msg[:200] + "..."
            
            lines.append(f"{i}. {msg}")
            lines.append("")
            
            word_count += len(msg.split())
            if word_count > max_words * 0.7:  # Leave room for header
                if i < len(unique_messages):
                    lines.append(f"*...and {len(unique_messages) - i} more prompts*")
                break
        
        return "\n".join(lines)
        
    except Exception as e:
        return f"Error generating summary: {str(e)}"


def _extract_text_from_content(content) -> str:
    """Extract plain text from message content."""
    if isinstance(content, str):
        return content
    
    if isinstance(content, list):
        texts = []
        for c in content:
            if isinstance(c, dict) and c.get('type') == 'text':
                texts.append(c.get('text', ''))
        return ' '.join(texts)
    
    return ''



def get_branch_summary(path: Path, leaf_uuid: str, max_words: int = 500) -> str:
    """Generate a summary of a specific branch's content.
    
    Traces from the leaf node back to root and summarizes only
    the messages in that conversation path.
    
    Args:
        path: Path to the .jsonl file
        leaf_uuid: UUID of the branch's leaf node
        max_words: Maximum words in summary (default 500)
        
    Returns:
        Summary string
    """
    try:
        messages, summaries = _parse_jsonl_file(path)
        
        if not messages:
            return "Empty conversation"
        
        # Get the transcript for this specific branch
        transcript = _get_transcript(messages, leaf_uuid)
        
        if not transcript:
            return "Could not trace branch history"
        
        # Collect user and assistant messages from this branch
        user_messages = []
        assistant_messages = []
        
        for msg in transcript:
            msg_type = msg.get('type')
            
            if msg_type == 'user':
                # Skip meta messages
                if msg.get('isMeta'):
                    continue
                    
                content = msg.get('message', {}).get('content', [])
                text = _extract_text_from_content(content)
                
                # Skip session continuation and IDE messages
                if text and not text.startswith('This session is being continued'):
                    if not text.startswith('<ide_'):
                        user_messages.append(text)
            
            elif msg_type == 'assistant':
                content = msg.get('message', {}).get('content', [])
                text = _extract_text_from_content(content)
                if text and len(text) > 30:
                    assistant_messages.append(text)
        
        # Build summary
        lines = []
        
        # Header with stats
        lines.append(f"## Branch Summary")
        lines.append(f"**Messages in branch:** {len(transcript)} ({len(user_messages)} user, {len(assistant_messages)} assistant)")
        lines.append("")
        
        # User prompts section
        lines.append("## User Prompts")
        lines.append("")
        
        word_count = 0
        for i, msg in enumerate(user_messages[:15], 1):
            # Truncate long messages
            if len(msg) > 300:
                msg = msg[:300] + "..."
            
            lines.append(f"{i}. {msg}")
            lines.append("")
            
            word_count += len(msg.split())
            if word_count > max_words * 0.5:
                if i < len(user_messages):
                    lines.append(f"*...and {len(user_messages) - i} more prompts*")
                break
        
        # Assistant highlights (brief)
        if assistant_messages and word_count < max_words * 0.8:
            lines.append("")
            lines.append("## Key Assistant Responses")
            lines.append("")
            
            for i, msg in enumerate(assistant_messages[:5], 1):
                # Show first 150 chars
                snippet = msg[:150] + "..." if len(msg) > 150 else msg
                lines.append(f"- {snippet}")
                
                word_count += len(snippet.split())
                if word_count > max_words:
                    break
        
        return "\n".join(lines)
        
    except Exception as e:
        return f"Error generating branch summary: {str(e)}"



@dataclass
class SearchResult:
    """A search result with context."""
    conversation: Conversation
    matches: list[dict]  # List of {type, text, context} dicts
    score: int  # Number of matches


def search_conversations(project: ClaudeProject, query: str) -> list[SearchResult]:
    """
    Search all conversations in a project for a query string.
    
    Searches:
    - Branch/conversation names (summaries)
    - User prompts
    
    Returns results sorted by relevance (match count).
    """
    if not query or len(query) < 2:
        return []
    
    query_lower = query.lower()
    results = []
    
    for conv in project.conversations:
        matches = []
        
        # Search branch names
        for branch in conv.branches:
            if branch.summary and query_lower in branch.summary.lower():
                matches.append({
                    'type': 'branch_name',
                    'text': branch.summary,
                    'context': f"Branch: {branch.summary}"
                })
        
        # Search user prompts in the conversation file
        try:
            messages, _ = _parse_jsonl_file(conv.path)
            
            for msg_uuid, msg_data in messages.items():
                if msg_data.get('type') != 'user':
                    continue
                
                # Content can be in different places depending on message format
                # Format 1: data['content'] = [{'type': 'text', 'text': '...'}]
                # Format 2: data['message']['content'] = '...' (string)
                # Format 3: data['message']['content'] = [{'type': 'text', 'text': '...'}]
                
                texts_to_search = []
                
                # Try data['content'] (list format)
                content = msg_data.get('content', [])
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get('type') == 'text':
                            texts_to_search.append(c.get('text', ''))
                
                # Try data['message']['content']
                message = msg_data.get('message', {})
                if isinstance(message, dict):
                    msg_content = message.get('content')
                    if isinstance(msg_content, str):
                        texts_to_search.append(msg_content)
                    elif isinstance(msg_content, list):
                        for c in msg_content:
                            if isinstance(c, dict):
                                if c.get('type') == 'text':
                                    texts_to_search.append(c.get('text', ''))
                                elif c.get('type') == 'tool_result':
                                    # Tool results can contain search-worthy content
                                    texts_to_search.append(c.get('content', ''))
                
                for text in texts_to_search:
                    if not text:
                        continue
                        
                    # Skip meta messages
                    if text.startswith('<ide_') or text.startswith('This session is being continued'):
                        continue
                    
                    if query_lower in text.lower():
                        # Create snippet with context around match
                        idx = text.lower().find(query_lower)
                        start = max(0, idx - 40)
                        end = min(len(text), idx + len(query) + 40)
                        
                        snippet = text[start:end]
                        if start > 0:
                            snippet = "..." + snippet
                        if end < len(text):
                            snippet = snippet + "..."
                        
                        matches.append({
                            'type': 'user_prompt',
                            'text': text[:100] + "..." if len(text) > 100 else text,
                            'context': snippet
                        })
                        
                        # Limit matches per conversation
                        if len([m for m in matches if m['type'] == 'user_prompt']) >= 5:
                            break
                
                # Check if we've hit the limit
                if len([m for m in matches if m['type'] == 'user_prompt']) >= 5:
                    break
                    
        except Exception:
            pass
        
        if matches:
            results.append(SearchResult(
                conversation=conv,
                matches=matches,
                score=len(matches)
            ))
    
    # Sort by score descending
    results.sort(key=lambda r: r.score, reverse=True)
    
    return results
