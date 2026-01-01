"""
GUI Application for Claude Conversation Manager.

A modern GUI built with CustomTkinter for managing Claude Code conversations.
"""

import customtkinter as ctk
from tkinter import messagebox
import threading
from pathlib import Path
from typing import Optional, Callable

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


# Configure appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class ConversationManagerApp(ctk.CTk):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        
        self.title("Claude Conversation Manager")
        self.geometry("1200x700")
        self.minsize(900, 500)
        
        # Data
        self.projects: list[ClaudeProject] = []
        self.selected_project: Optional[ClaudeProject] = None
        self.selected_conversation: Optional[Conversation] = None
        
        # Build UI
        self._create_layout()
        self._create_sidebar()
        self._create_main_panel()
        self._create_detail_panel()
        
        # Load data
        self.after(100, self._load_projects)
    
    def _create_layout(self):
        """Create the main layout grid."""
        self.grid_columnconfigure(0, weight=0)  # Sidebar - fixed
        self.grid_columnconfigure(1, weight=1)  # Main panel - expand
        self.grid_columnconfigure(2, weight=0)  # Detail panel - fixed
        self.grid_rowconfigure(0, weight=1)
    
    def _create_sidebar(self):
        """Create the left sidebar with project list."""
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(2, weight=1)
        self.sidebar.grid_propagate(False)
        
        # Header
        header = ctk.CTkLabel(
            self.sidebar, 
            text="Projects",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        
        # Refresh button
        refresh_btn = ctk.CTkButton(
            self.sidebar,
            text="↻ Refresh",
            width=80,
            command=self._load_projects
        )
        refresh_btn.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="w")
        
        # Project list (scrollable)
        self.project_list = ctk.CTkScrollableFrame(self.sidebar)
        self.project_list.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")
        self.project_list.grid_columnconfigure(0, weight=1)


    def _create_main_panel(self):
        """Create the center panel with conversation list."""
        self.main_panel = ctk.CTkFrame(self, corner_radius=0)
        self.main_panel.grid(row=0, column=1, sticky="nsew", padx=(1, 1))
        self.main_panel.grid_rowconfigure(2, weight=1)
        self.main_panel.grid_columnconfigure(0, weight=1)
        
        # Header with project name
        self.main_header = ctk.CTkLabel(
            self.main_panel,
            text="Select a project",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w"
        )
        self.main_header.grid(row=0, column=0, padx=20, pady=(20, 5), sticky="ew")
        
        # Stats bar
        self.stats_label = ctk.CTkLabel(
            self.main_panel,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="gray",
            anchor="w"
        )
        self.stats_label.grid(row=1, column=0, padx=20, pady=(0, 10), sticky="ew")
        
        # Conversation list (scrollable)
        self.conv_list = ctk.CTkScrollableFrame(self.main_panel)
        self.conv_list.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")
        self.conv_list.grid_columnconfigure(0, weight=1)
    
    def _create_detail_panel(self):
        """Create the right panel with conversation details."""
        self.detail_panel = ctk.CTkFrame(self, width=350, corner_radius=0)
        self.detail_panel.grid(row=0, column=2, sticky="nsew")
        self.detail_panel.grid_rowconfigure(4, weight=1)
        self.detail_panel.grid_propagate(False)
        
        # Header
        header = ctk.CTkLabel(
            self.detail_panel,
            text="Conversation Details",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        
        # Info frame
        self.info_frame = ctk.CTkFrame(self.detail_panel)
        self.info_frame.grid(row=1, column=0, padx=15, pady=10, sticky="ew")
        
        self.detail_name = ctk.CTkLabel(
            self.info_frame, text="No conversation selected",
            font=ctk.CTkFont(size=13), wraplength=300, anchor="w", justify="left"
        )
        self.detail_name.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        
        self.detail_stats = ctk.CTkLabel(
            self.info_frame, text="",
            font=ctk.CTkFont(size=11), text_color="gray", anchor="w"
        )
        self.detail_stats.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="w")
        
        # Rename section
        rename_label = ctk.CTkLabel(
            self.detail_panel, text="Rename Conversation",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        rename_label.grid(row=2, column=0, padx=20, pady=(20, 5), sticky="w")
        
        self.rename_entry = ctk.CTkEntry(
            self.detail_panel, placeholder_text="Enter new name...", width=310
        )
        self.rename_entry.grid(row=3, column=0, padx=20, pady=(5, 10), sticky="w")
        
        self.rename_btn = ctk.CTkButton(
            self.detail_panel, text="Rename All Branches",
            command=self._do_rename, state="disabled"
        )
        self.rename_btn.grid(row=4, column=0, padx=20, pady=(0, 10), sticky="nw")
        
        # Branches section
        branches_label = ctk.CTkLabel(
            self.detail_panel, text="Branches",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        branches_label.grid(row=5, column=0, padx=20, pady=(20, 5), sticky="w")
        
        self.branches_frame = ctk.CTkScrollableFrame(self.detail_panel, height=200)
        self.branches_frame.grid(row=6, column=0, padx=15, pady=10, sticky="nsew")
        self.branches_frame.grid_columnconfigure(0, weight=1)
        
        # Warning notice
        self.warning_frame = ctk.CTkFrame(self.detail_panel, fg_color="#4a3000")
        self.warning_frame.grid(row=7, column=0, padx=15, pady=15, sticky="sew")
        
        warning_text = ctk.CTkLabel(
            self.warning_frame,
            text="⚠ After renaming, restart VS Code\n(kill all Code.exe processes)",
            font=ctk.CTkFont(size=11),
            text_color="#ffcc00",
            justify="left"
        )
        warning_text.grid(row=0, column=0, padx=10, pady=10)


    # =========================================================================
    # Data Loading
    # =========================================================================
    
    def _load_projects(self):
        """Load all Claude projects."""
        # Clear existing items
        for widget in self.project_list.winfo_children():
            widget.destroy()
        
        # Show loading
        loading = ctk.CTkLabel(self.project_list, text="Loading projects...")
        loading.grid(row=0, column=0, pady=20)
        self.update()
        
        # Load in background
        def load():
            self.projects = list_projects()
            self.after(0, self._display_projects)
        
        threading.Thread(target=load, daemon=True).start()
    
    def _display_projects(self):
        """Display loaded projects in sidebar."""
        # Clear
        for widget in self.project_list.winfo_children():
            widget.destroy()
        
        if not self.projects:
            empty = ctk.CTkLabel(
                self.project_list, 
                text="No projects found",
                text_color="gray"
            )
            empty.grid(row=0, column=0, pady=20)
            return
        
        for i, project in enumerate(self.projects):
            self._create_project_button(project, i)
    
    def _create_project_button(self, project: ClaudeProject, row: int):
        """Create a button for a project."""
        # Format display name
        display = project.display_name
        if len(display) > 35:
            display = "..." + display[-32:]
        
        # Count conversations
        conv_count = len([
            f for f in project.path.iterdir()
            if f.suffix == '.jsonl' 
            and not f.name.startswith('agent-')
            and not f.name.endswith('.backup')
        ])
        
        frame = ctk.CTkFrame(self.project_list, fg_color="transparent")
        frame.grid(row=row, column=0, pady=2, sticky="ew")
        frame.grid_columnconfigure(0, weight=1)
        
        btn = ctk.CTkButton(
            frame,
            text=f"{display}\n{conv_count} conversations",
            anchor="w",
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            hover_color=("gray75", "gray25"),
            command=lambda p=project: self._select_project(p)
        )
        btn.grid(row=0, column=0, sticky="ew")
    
    def _select_project(self, project: ClaudeProject):
        """Handle project selection."""
        self.selected_project = project
        self.selected_conversation = None
        
        # Update header
        display = project.display_name
        if len(display) > 50:
            display = "..." + display[-47:]
        self.main_header.configure(text=display)
        
        # Clear conversation list and show loading
        for widget in self.conv_list.winfo_children():
            widget.destroy()
        loading = ctk.CTkLabel(self.conv_list, text="Loading conversations...")
        loading.grid(row=0, column=0, pady=20)
        self.update()
        
        # Load conversations in background
        def load():
            load_project_conversations(project)
            self.after(0, self._display_conversations)
        
        threading.Thread(target=load, daemon=True).start()


    def _display_conversations(self):
        """Display conversations in main panel."""
        if not self.selected_project:
            return
        
        # Clear
        for widget in self.conv_list.winfo_children():
            widget.destroy()
        
        convs = self.selected_project.conversations
        
        if not convs:
            empty = ctk.CTkLabel(
                self.conv_list,
                text="No conversations found",
                text_color="gray"
            )
            empty.grid(row=0, column=0, pady=20)
            return
        
        # Update stats
        unhealthy = sum(1 for c in convs if not c.is_healthy)
        self.stats_label.configure(
            text=f"{len(convs)} conversations • {unhealthy} need attention"
        )
        
        for i, conv in enumerate(convs):
            self._create_conversation_row(conv, i)
    
    def _create_conversation_row(self, conv: Conversation, row: int):
        """Create a row for a conversation."""
        frame = ctk.CTkFrame(self.conv_list, fg_color="transparent")
        frame.grid(row=row, column=0, pady=2, sticky="ew")
        frame.grid_columnconfigure(1, weight=1)
        
        # Status indicator
        if conv.is_healthy:
            status_color = "#2ecc71"  # Green
            status_text = "OK"
        else:
            status_color = "#e74c3c"  # Red
            status_text = f"!{conv.unnamed_branches}"
        
        status = ctk.CTkLabel(
            frame, text=status_text,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=status_color, width=30
        )
        status.grid(row=0, column=0, padx=(5, 10))
        
        # Name and date
        name = conv.display_name
        if len(name) > 50:
            name = name[:47] + "..."
        
        date_str = conv.modified.strftime("%Y-%m-%d")
        
        btn = ctk.CTkButton(
            frame,
            text=f"{name}\n{date_str} • {conv.branch_count} branches • {conv.total_messages} msgs",
            anchor="w",
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            hover_color=("gray75", "gray25"),
            height=50,
            command=lambda c=conv: self._select_conversation(c)
        )
        btn.grid(row=0, column=1, sticky="ew")
    
    def _select_conversation(self, conv: Conversation):
        """Handle conversation selection."""
        self.selected_conversation = conv
        
        # Update detail panel
        name = conv.display_name
        if len(name) > 45:
            name = name[:42] + "..."
        self.detail_name.configure(text=name)
        
        stats = (
            f"Branches: {conv.branch_count}\n"
            f"Messages: {conv.total_messages}\n"
            f"Size: {conv.file_size / 1024:.1f} KB\n"
            f"Modified: {conv.modified.strftime('%Y-%m-%d %H:%M')}\n"
            f"Health: {'OK' if conv.is_healthy else f'{conv.unnamed_branches} unnamed branches'}"
        )
        self.detail_stats.configure(text=stats)
        
        # Pre-fill rename entry with current name or suggested name
        self.rename_entry.delete(0, 'end')
        if conv.primary_summary:
            self.rename_entry.insert(0, conv.primary_summary)
        
        # Enable rename button
        self.rename_btn.configure(state="normal")
        
        # Display branches
        self._display_branches(conv)


    def _display_branches(self, conv: Conversation):
        """Display branch details."""
        # Clear
        for widget in self.branches_frame.winfo_children():
            widget.destroy()
        
        for i, branch in enumerate(conv.branches):
            frame = ctk.CTkFrame(self.branches_frame, fg_color=("gray85", "gray20"))
            frame.grid(row=i, column=0, pady=3, sticky="ew")
            frame.grid_columnconfigure(1, weight=1)
            
            # Status
            color = "#2ecc71" if branch.has_summary else "#e74c3c"
            status = ctk.CTkLabel(
                frame, text="●", text_color=color,
                font=ctk.CTkFont(size=14)
            )
            status.grid(row=0, column=0, padx=(10, 5), pady=8)
            
            # Info
            name = branch.display_name[:30] + "..." if len(branch.display_name) > 30 else branch.display_name
            ts = branch.timestamp[:10] if branch.timestamp else "Unknown"
            
            info = ctk.CTkLabel(
                frame,
                text=f"{name}\n{ts} • {branch.message_count} msgs",
                font=ctk.CTkFont(size=11),
                anchor="w",
                justify="left"
            )
            info.grid(row=0, column=1, padx=5, pady=5, sticky="w")
    
    # =========================================================================
    # Actions
    # =========================================================================
    
    def _do_rename(self):
        """Execute the rename operation."""
        if not self.selected_conversation:
            return
        
        new_name = self.rename_entry.get().strip()
        if not new_name:
            messagebox.showwarning("Warning", "Please enter a name")
            return
        
        # Disable button during operation
        self.rename_btn.configure(state="disabled", text="Renaming...")
        self.update()
        
        def rename():
            success, message = rename_conversation(
                self.selected_conversation.path, 
                new_name
            )
            self.after(0, lambda: self._rename_complete(success, message))
        
        threading.Thread(target=rename, daemon=True).start()
    
    def _rename_complete(self, success: bool, message: str):
        """Handle rename completion."""
        self.rename_btn.configure(state="normal", text="Rename All Branches")
        
        if success:
            messagebox.showinfo(
                "Success",
                f"{message}\n\nRemember to restart VS Code to see changes!"
            )
            # Refresh the conversation list
            if self.selected_project:
                self._select_project(self.selected_project)
        else:
            messagebox.showerror("Error", message)


def run_gui():
    """Entry point for GUI application."""
    app = ConversationManagerApp()
    app.mainloop()


if __name__ == "__main__":
    run_gui()
