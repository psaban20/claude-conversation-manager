"""
Command-line interface for Claude Conversation Manager.
"""

import argparse
import sys
import io
from pathlib import Path

# Fix Unicode output on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from . import __version__
from .core import (
    get_claude_projects_dir,
    list_projects,
    load_project_conversations,
    analyze_conversation,
    rename_conversation,
)


def cmd_list(args):
    """List all projects or conversations in a project."""
    projects = list_projects()
    
    if not projects:
        print("No Claude projects found.")
        return 1
    
    if args.project:
        # Find the specified project
        project = None
        for p in projects:
            if args.project in p.name or args.project in p.display_name:
                project = p
                break
        
        if not project:
            print(f"Project not found: {args.project}")
            return 1
        
        load_project_conversations(project)
        print(f"\nProject: {project.display_name}")
        print(f"Path: {project.path}")
        print(f"Conversations: {project.conversation_count}")
        print("-" * 70)
        
        for conv in project.conversations:
            status = "[OK]" if conv.is_healthy else f"[!] {conv.unnamed_branches}/{conv.branch_count}"
            date_str = conv.modified.strftime("%Y-%m-%d %H:%M")
            name = conv.display_name[:45] + "..." if len(conv.display_name) > 45 else conv.display_name
            print(f"  {status:>10} {date_str} | {name}")
        
        return 0
    
    # List all projects
    print(f"\nClaude Projects ({len(projects)} found)")
    print("=" * 70)
    
    for i, project in enumerate(projects, 1):
        # Count conversations
        conv_count = len([
            f for f in project.path.iterdir()
            if f.suffix == '.jsonl' 
            and not f.name.startswith('agent-')
            and not f.name.endswith('.backup')
        ])
        
        display = project.display_name
        if len(display) > 55:
            display = "..." + display[-52:]
        
        print(f"  {i:2}. {display}")
        print(f"      {conv_count} conversations")
    
    return 0



def cmd_analyze(args):
    """Analyze a specific conversation file."""
    path = Path(args.file)
    
    if not path.exists():
        print(f"File not found: {path}")
        return 1
    
    conv = analyze_conversation(path)
    
    if not conv:
        print(f"Could not analyze: {path}")
        return 1
    
    print(f"\nConversation Analysis")
    print("=" * 70)
    print(f"File: {conv.filename}")
    print(f"Session ID: {conv.session_id}")
    print(f"Size: {conv.file_size / 1024:.1f} KB")
    print(f"Modified: {conv.modified.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total messages: {conv.total_messages}")
    print(f"Branches: {conv.branch_count}")
    print(f"Health: {'OK - All branches named' if conv.is_healthy else f'WARNING - {conv.unnamed_branches} unnamed'}")
    print(f"Display name: {conv.display_name}")
    
    print(f"\nBranches (sorted by timestamp):")
    print("-" * 70)
    
    for i, branch in enumerate(conv.branches, 1):
        status = "[OK]" if branch.has_summary else "[--]"
        ts = branch.timestamp[:19] if branch.timestamp else "Unknown"
        name = branch.display_name[:40] + "..." if len(branch.display_name) > 40 else branch.display_name
        print(f"  {i:2}. {status} {ts} | {branch.message_count:4} msgs | {name}")
    
    return 0


def cmd_rename(args):
    """Rename a conversation."""
    path = Path(args.file)
    
    if not path.exists():
        print(f"File not found: {path}")
        return 1
    
    # Show current state
    conv = analyze_conversation(path)
    if conv:
        print(f"Current name: {conv.display_name}")
        print(f"Branches: {conv.branch_count}")
    
    if not args.name:
        print("No new name provided. Use --name 'New Name'")
        return 1
    
    success, message = rename_conversation(path, args.name)
    
    if success:
        print(f"[OK] {message}")
        print("\n** IMPORTANT: Kill all Code.exe processes and restart VS Code to see changes!")
        return 0
    else:
        print(f"[FAILED] {message}")
        return 1


def cmd_health(args):
    """Show health status of all conversations."""
    projects = list_projects()
    
    if not projects:
        print("No Claude projects found.")
        return 1
    
    print(f"\nConversation Health Report")
    print("=" * 70)
    
    total_convs = 0
    unhealthy_convs = 0
    
    for project in projects:
        load_project_conversations(project)
        
        if not project.conversations:
            continue
        
        project_unhealthy = [c for c in project.conversations if not c.is_healthy]
        
        if project_unhealthy or args.all:
            display = project.display_name
            if len(display) > 60:
                display = "..." + display[-57:]
            print(f"\n{display}")
            print("-" * 70)
            
            for conv in (project.conversations if args.all else project_unhealthy):
                status = "[OK]" if conv.is_healthy else f"[!] {conv.unnamed_branches}/{conv.branch_count} unnamed"
                name = conv.display_name[:40] + "..." if len(conv.display_name) > 40 else conv.display_name
                print(f"  {status:>20} {name}")
        
        total_convs += len(project.conversations)
        unhealthy_convs += len(project_unhealthy)
    
    print(f"\n{'=' * 70}")
    print(f"Total: {total_convs} conversations, {unhealthy_convs} need attention")
    
    return 0



def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        prog='claude-conv-manager',
        description='Manage Claude Code VS Code extension conversations'
    )
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List projects or conversations')
    list_parser.add_argument('--project', '-p', help='Show conversations in specific project')
    
    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze a conversation file')
    analyze_parser.add_argument('file', help='Path to .jsonl file')
    
    # Rename command
    rename_parser = subparsers.add_parser('rename', help='Rename a conversation')
    rename_parser.add_argument('file', help='Path to .jsonl file')
    rename_parser.add_argument('--name', '-n', required=True, help='New name for conversation')
    
    # Health command
    health_parser = subparsers.add_parser('health', help='Check conversation health')
    health_parser.add_argument('--all', '-a', action='store_true', help='Show all conversations')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    commands = {
        'list': cmd_list,
        'analyze': cmd_analyze,
        'rename': cmd_rename,
        'health': cmd_health,
    }
    
    return commands[args.command](args)


if __name__ == '__main__':
    sys.exit(main())
