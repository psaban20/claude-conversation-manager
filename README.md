# Claude Conversation Manager

A tool for managing Claude Code VS Code extension conversations - rename, analyze, and fix conversation display names.

## The Problem

Claude Code stores conversations in `.jsonl` files with a complex branching structure. The VS Code extension can pick **any branch** to display in the "Past Conversations" dropdown, and if that branch doesn't have a summary record, it falls back to showing the first user message.

This means:
- Renaming a conversation requires updating **all branches**, not just one
- Many conversations show cryptic names like "i need t work on the..." instead of meaningful titles
- The extension's built-in rename (if any) doesn't handle this properly

## The Solution

This tool properly renames conversations by:
1. Analyzing the conversation structure to find **all branch endpoints (leaves)**
2. Adding summary records for **every leaf** so the name appears regardless of which branch the extension picks
3. Providing health checks to identify conversations needing attention

## Installation

```bash
# Clone the repository
git clone https://github.com/pablosaban/claude-conversation-manager.git
cd claude-conversation-manager

# Install in development mode
pip install -e .

# Or install with GUI support
pip install -e ".[gui]"
```

## Usage

### List Projects
```bash
# List all Claude Code projects
claude-conv-manager list

# List conversations in a specific project
claude-conv-manager list --project hjb-public-ui
```

### Analyze a Conversation
```bash
claude-conv-manager analyze "C:\Users\me\.claude\projects\my-project\abc123.jsonl"
```

Output:
```
Conversation Analysis
======================================================================
File: abc123.jsonl
Branches: 15
Health: ⚠ 14 unnamed

Branches (sorted by timestamp):
   1. [✓] 2025-12-19 16:26 |   30 msgs | My Custom Name
   2. [✗] 2025-12-18 17:21 |   72 msgs | This session is being continued...
   ...
```

### Rename a Conversation
```bash
claude-conv-manager rename "path/to/conversation.jsonl" --name "My New Name"
```

### Health Check
```bash
# Show conversations needing attention
claude-conv-manager health

# Show all conversations
claude-conv-manager health --all
```

## How It Works

### Conversation Structure

```
.jsonl File
├── summary records: {"type":"summary","summary":"Name","leafUuid":"..."}
├── queue-operations (ignored by extension)
└── messages with parent-child relationships
    ├── Branch 1: root → msg → msg → leaf₁
    ├── Branch 2: root → msg → fork → leaf₂  
    └── Branch 3: root → msg → fork → msg → leaf₃
```

### Extension Behavior
1. Parses all messages and builds a map of `leafUuid → summary`
2. Identifies all leaf nodes (messages with no children)
3. For each leaf, looks up `summaries.get(leaf.uuid)`
4. If found: use the summary
5. If not found: fall back to first user message text

### Why Simple Renaming Fails
If you only update ONE summary record, it only works if:
- That specific leaf happens to be the one the extension picks
- The extension consistently picks the same leaf (it doesn't!)

Our solution: Add summary records for ALL leaves.

## Important Notes

⚠️ **After renaming, you MUST restart VS Code:**
1. Close all VS Code windows
2. Kill all `Code.exe` processes (Task Manager → Details)
3. Reopen VS Code

The extension has an in-memory cache that doesn't refresh on file changes.

## Roadmap

- [x] Core library for analysis and renaming
- [x] CLI interface
- [ ] GUI application (CustomTkinter)
- [ ] Batch rename operations
- [ ] Conversation search
- [ ] Branch visualization
- [ ] Backup/restore functionality

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions welcome! Please open an issue to discuss changes before submitting PRs.
