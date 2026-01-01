"""
GUI Application for Claude Conversation Manager.

A modern GUI built with CustomTkinter for managing Claude Code conversations.
Features resizable panes for flexible layout.
"""

import customtkinter as ctk
from tkinter import messagebox, PanedWindow, HORIZONTAL, Toplevel, StringVar
import threading
import os
from pathlib import Path
from typing import Optional

from .core import (
    ClaudeProject,
    Conversation,
    Branch,
    get_claude_projects_dir,
    list_projects,
    load_project_conversations,
    analyze_conversation,
    rename_conversation,
    move_conversation,
    path_to_project_name,
    get_or_create_project,
)


# Configure appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class ConversationManagerApp(ctk.CTk):
    """Main application window with resizable panes."""
    
    def __init__(self):
        super().__init__()
        
        self.title("Claude Conversation Manager")
        self.geometry("1400x750")
        self.minsize(1000, 600)
        
        # Data
        self.projects: list[ClaudeProject] = []
        self.selected_project: Optional[ClaudeProject] = None
        self.selected_conversation: Optional[Conversation] = None
        
        # Build UI with resizable panes
        self._create_resizable_layout()
        
        # Load data
        self.after(100, self._load_projects)
    
    def _create_resizable_layout(self):
        """Create resizable three-pane layout."""
        # Main container
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Use tkinter PanedWindow for resizable panes
        self.paned = PanedWindow(
            self, orient=HORIZONTAL, 
            sashwidth=6, sashrelief="raised",
            bg="#2b2b2b"
        )
        self.paned.grid(row=0, column=0, sticky="nsew")
        
        # Create the three panes
        self._create_sidebar()
        self._create_main_panel()
        self._create_detail_panel()
        
        # Add panes to PanedWindow
        self.paned.add(self.sidebar, minsize=250, width=350)
        self.paned.add(self.main_panel, minsize=300, width=450)
        self.paned.add(self.detail_panel, minsize=300, width=400)
    
    def _create_sidebar(self):
        """Create the left sidebar with project list."""
        self.sidebar = ctk.CTkFrame(self.paned, corner_radius=0)
        self.sidebar.grid_rowconfigure(2, weight=1)
        self.sidebar.grid_columnconfigure(0, weight=1)
        
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
            text="Refresh",
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
        self.main_panel = ctk.CTkFrame(self.paned, corner_radius=0)
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
        self.detail_panel = ctk.CTkFrame(self.paned, corner_radius=0)
        self.detail_panel.grid_rowconfigure(6, weight=1)
        self.detail_panel.grid_columnconfigure(0, weight=1)
        
        # Header
        header = ctk.CTkLabel(
            self.detail_panel,
            text="Conversation Details",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        
        # Info frame - VS Code current title
        self.info_frame = ctk.CTkFrame(self.detail_panel)
        self.info_frame.grid(row=1, column=0, padx=15, pady=10, sticky="ew")
        self.info_frame.grid_columnconfigure(0, weight=1)
        
        vscode_label = ctk.CTkLabel(
            self.info_frame, text="VS Code Shows:",
            font=ctk.CTkFont(size=11, weight="bold"), text_color="#888"
        )
        vscode_label.grid(row=0, column=0, padx=10, pady=(10, 2), sticky="w")
        
        self.detail_vscode_title = ctk.CTkLabel(
            self.info_frame, text="",
            font=ctk.CTkFont(size=12), wraplength=350, anchor="w", justify="left",
            text_color="#ffcc00"
        )
        self.detail_vscode_title.grid(row=1, column=0, padx=10, pady=(0, 5), sticky="w")
        
        self.detail_stats = ctk.CTkLabel(
            self.info_frame, text="No conversation selected",
            font=ctk.CTkFont(size=11), text_color="gray", anchor="w", justify="left"
        )
        self.detail_stats.grid(row=2, column=0, padx=10, pady=(5, 10), sticky="w")
        
        # Rename section
        rename_label = ctk.CTkLabel(
            self.detail_panel, text="Rename Conversation",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        rename_label.grid(row=2, column=0, padx=20, pady=(15, 5), sticky="w")
        
        self.rename_entry = ctk.CTkEntry(
            self.detail_panel, placeholder_text="Enter new name...", width=350
        )
        self.rename_entry.grid(row=3, column=0, padx=20, pady=(5, 10), sticky="ew")
        
        # Button frame for rename, delete, move
        btn_frame = ctk.CTkFrame(self.detail_panel, fg_color="transparent")
        btn_frame.grid(row=4, column=0, padx=20, pady=(0, 10), sticky="w")
        
        self.rename_btn = ctk.CTkButton(
            btn_frame, text="Rename All Branches",
            command=self._do_rename, state="disabled", width=140
        )
        self.rename_btn.grid(row=0, column=0, padx=(0, 5))
        
        self.delete_btn = ctk.CTkButton(
            btn_frame, text="Delete",
            command=self._do_delete, state="disabled", width=80,
            fg_color="#8B0000", hover_color="#A00000"
        )
        self.delete_btn.grid(row=0, column=1, padx=(0, 5))
        
        self.move_btn = ctk.CTkButton(
            btn_frame, text="Move to Project...",
            command=self._show_move_dialog, state="disabled", width=120,
            fg_color="#1a5f2a", hover_color="#228B22"
        )
        self.move_btn.grid(row=0, column=2)
        
        # Branches section
        branches_label = ctk.CTkLabel(
            self.detail_panel, text="Branches",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        branches_label.grid(row=5, column=0, padx=20, pady=(15, 5), sticky="w")
        
        self.branches_frame = ctk.CTkScrollableFrame(self.detail_panel, height=180)
        self.branches_frame.grid(row=6, column=0, padx=15, pady=10, sticky="nsew")
        self.branches_frame.grid_columnconfigure(0, weight=1)
        
        # Warning notice
        self.warning_frame = ctk.CTkFrame(self.detail_panel, fg_color="#4a3000")
        self.warning_frame.grid(row=7, column=0, padx=15, pady=15, sticky="sew")
        
        warning_text = ctk.CTkLabel(
            self.warning_frame,
            text="After renaming/deleting, restart VS Code\n(kill all Code.exe processes)",
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
        for widget in self.project_list.winfo_children():
            widget.destroy()
        
        loading = ctk.CTkLabel(self.project_list, text="Loading projects...")
        loading.grid(row=0, column=0, pady=20)
        self.update()
        
        def load():
            self.projects = list_projects()
            self.after(0, self._display_projects)
        
        threading.Thread(target=load, daemon=True).start()
    
    def _display_projects(self):
        """Display loaded projects in sidebar."""
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
        # Show full path - sidebar is now resizable
        display = project.display_name
        
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
            font=ctk.CTkFont(size=11),
            fg_color="transparent",
            hover_color=("gray75", "gray25"),
            height=45,
            command=lambda p=project: self._select_project(p)
        )
        btn.grid(row=0, column=0, sticky="ew")
    
    def _select_project(self, project: ClaudeProject):
        """Handle project selection."""
        self.selected_project = project
        self.selected_conversation = None
        
        self.main_header.configure(text=project.display_name)
        
        for widget in self.conv_list.winfo_children():
            widget.destroy()
        loading = ctk.CTkLabel(self.conv_list, text="Loading conversations...")
        loading.grid(row=0, column=0, pady=20)
        self.update()
        
        def load():
            load_project_conversations(project)
            self.after(0, self._display_conversations)
        
        threading.Thread(target=load, daemon=True).start()


    def _display_conversations(self):
        """Display conversations in main panel."""
        if not self.selected_project:
            return
        
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
        
        unhealthy = sum(1 for c in convs if not c.is_healthy)
        self.stats_label.configure(
            text=f"{len(convs)} conversations - {unhealthy} need attention"
        )
        
        for i, conv in enumerate(convs):
            self._create_conversation_row(conv, i)
    
    def _create_conversation_row(self, conv: Conversation, row: int):
        """Create a row for a conversation - showing VS Code title."""
        frame = ctk.CTkFrame(self.conv_list, fg_color="transparent")
        frame.grid(row=row, column=0, pady=2, sticky="ew")
        frame.grid_columnconfigure(1, weight=1)
        
        # Status indicator
        if conv.is_healthy:
            status_color = "#2ecc71"
            status_text = "OK"
        else:
            status_color = "#e74c3c"
            status_text = f"!{conv.unnamed_branches}"
        
        status = ctk.CTkLabel(
            frame, text=status_text,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=status_color, width=35
        )
        status.grid(row=0, column=0, padx=(5, 10))
        
        # Always show VS Code title to help identify conversations
        vscode_title = conv.vscode_current_title
        if len(vscode_title) > 55:
            vscode_title = vscode_title[:52] + "..."
        
        if conv.is_healthy:
            subtitle = f"{conv.modified.strftime('%Y-%m-%d')} - {conv.branch_count} branches - {conv.total_messages} msgs"
        else:
            subtitle = f"{conv.modified.strftime('%Y-%m-%d')} - {conv.branch_count} branches - {conv.unnamed_branches} need names"
        
        btn = ctk.CTkButton(
            frame,
            text=f"{vscode_title}\n{subtitle}",
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
        
        # Show VS Code current title prominently
        vscode_title = conv.vscode_current_title
        self.detail_vscode_title.configure(text=vscode_title)
        
        stats = (
            f"Branches: {conv.branch_count} ({conv.unnamed_branches} unnamed)\n"
            f"Messages: {conv.total_messages}\n"
            f"Size: {conv.file_size / 1024:.1f} KB\n"
            f"Modified: {conv.modified.strftime('%Y-%m-%d %H:%M')}\n"
            f"File: {conv.filename}"
        )
        self.detail_stats.configure(text=stats)
        
        # Pre-fill rename entry
        self.rename_entry.delete(0, 'end')
        if conv.primary_summary:
            self.rename_entry.insert(0, conv.primary_summary)
        
        # Enable buttons
        self.rename_btn.configure(state="normal")
        self.delete_btn.configure(state="normal")
        self.move_btn.configure(state="normal")
        
        self._display_branches(conv)


    def _display_branches(self, conv: Conversation):
        """Display branch details."""
        for widget in self.branches_frame.winfo_children():
            widget.destroy()
        
        for i, branch in enumerate(conv.branches):
            frame = ctk.CTkFrame(self.branches_frame, fg_color=("gray85", "gray20"))
            frame.grid(row=i, column=0, pady=3, sticky="ew")
            frame.grid_columnconfigure(1, weight=1)
            
            color = "#2ecc71" if branch.has_summary else "#e74c3c"
            status = ctk.CTkLabel(
                frame, text="*", text_color=color,
                font=ctk.CTkFont(size=14, weight="bold")
            )
            status.grid(row=0, column=0, padx=(10, 5), pady=8)
            
            # Show the actual first user message for this branch
            name = branch.first_user_message
            if len(name) > 40:
                name = name[:37] + "..."
            ts = branch.timestamp[:10] if branch.timestamp else "Unknown"
            
            info = ctk.CTkLabel(
                frame,
                text=f"{name}\n{ts} - {branch.message_count} msgs",
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
            if self.selected_project:
                self._select_project(self.selected_project)
        else:
            messagebox.showerror("Error", message)
    
    def _do_delete(self):
        """Delete the selected conversation and all related files."""
        if not self.selected_conversation:
            return
        
        conv = self.selected_conversation
        vscode_title = conv.vscode_current_title
        if len(vscode_title) > 60:
            vscode_title = vscode_title[:57] + "..."
        
        # Confirmation dialog
        result = messagebox.askyesno(
            "Confirm Delete",
            f"Delete this conversation?\n\n"
            f"VS Code shows: {vscode_title}\n"
            f"Branches: {conv.branch_count}\n"
            f"Messages: {conv.total_messages}\n\n"
            f"This will delete:\n"
            f"  - {conv.filename}\n"
            f"  - {conv.filename}.backup (if exists)\n\n"
            f"This cannot be undone!",
            icon="warning"
        )
        
        if not result:
            return
        
        self.delete_btn.configure(state="disabled", text="Deleting...")
        self.update()
        
        def delete():
            try:
                if conv.path.exists():
                    os.remove(conv.path)
                
                backup_path = conv.path.with_suffix('.jsonl.backup')
                if backup_path.exists():
                    os.remove(backup_path)
                
                self.after(0, lambda: self._delete_complete(True, "Conversation deleted"))
            except Exception as e:
                self.after(0, lambda: self._delete_complete(False, str(e)))
        
        threading.Thread(target=delete, daemon=True).start()
    
    def _delete_complete(self, success: bool, message: str):
        """Handle delete completion."""
        self.delete_btn.configure(state="normal", text="Delete")
        
        if success:
            messagebox.showinfo(
                "Deleted",
                f"{message}\n\nRemember to restart VS Code to see changes!"
            )
            self.selected_conversation = None
            self.detail_vscode_title.configure(text="")
            self.detail_stats.configure(text="No conversation selected")
            self.rename_entry.delete(0, 'end')
            self.rename_btn.configure(state="disabled")
            self.delete_btn.configure(state="disabled")
            self.move_btn.configure(state="disabled")
            
            for widget in self.branches_frame.winfo_children():
                widget.destroy()
            
            if self.selected_project:
                self._select_project(self.selected_project)
        else:
            messagebox.showerror("Error", f"Failed to delete: {message}")
    
    # =========================================================================
    # Move to Project
    # =========================================================================
    
    def _show_move_dialog(self):
        """Show dialog to select target project for moving conversation."""
        if not self.selected_conversation:
            return
        
        # Create dialog window
        dialog = ctk.CTkToplevel(self)
        dialog.title("Move to Project")
        dialog.geometry("600x500")
        dialog.transient(self)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() - 600) // 2
        y = self.winfo_y() + (self.winfo_height() - 500) // 2
        dialog.geometry(f"+{x}+{y}")
        
        # Current location info
        info_frame = ctk.CTkFrame(dialog)
        info_frame.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(
            info_frame, text="Moving conversation:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))
        
        vscode_title = self.selected_conversation.vscode_current_title
        if len(vscode_title) > 60:
            vscode_title = vscode_title[:57] + "..."
        ctk.CTkLabel(
            info_frame, text=vscode_title,
            font=ctk.CTkFont(size=11), text_color="#ffcc00"
        ).pack(anchor="w", padx=10, pady=(0, 5))
        
        ctk.CTkLabel(
            info_frame, text=f"From: {self.selected_project.display_name}",
            font=ctk.CTkFont(size=11), text_color="gray"
        ).pack(anchor="w", padx=10, pady=(0, 10))
        
        # Target selection
        ctk.CTkLabel(
            dialog, text="Select target project:",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=20, pady=(10, 5))
        
        # Existing projects list
        projects_frame = ctk.CTkScrollableFrame(dialog, height=200)
        projects_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        selected_target = StringVar(value="")
        
        for project in self.projects:
            # Skip current project
            if project.path == self.selected_project.path:
                continue
            
            rb = ctk.CTkRadioButton(
                projects_frame,
                text=project.display_name,
                variable=selected_target,
                value=str(project.path),
                font=ctk.CTkFont(size=11)
            )
            rb.pack(anchor="w", pady=3)
        
        # New project section
        ctk.CTkLabel(
            dialog, text="Or create new project from path:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", padx=20, pady=(10, 5))
        
        new_path_entry = ctk.CTkEntry(
            dialog, 
            placeholder_text="e.g., C:\\dropboxfolders\\pablosaban\\Dropbox\\HJB\\GitHub",
            width=540
        )
        new_path_entry.pack(padx=20, pady=(0, 10))
        
        # Buttons
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=15)
        
        def do_move():
            # Check if new path entered
            new_path = new_path_entry.get().strip()
            if new_path:
                target_path = Path(new_path)
                if not target_path.exists():
                    messagebox.showerror("Error", f"Path does not exist: {new_path}")
                    return
                # Create or get project folder
                project_folder, was_created = get_or_create_project(target_path)
                target = project_folder
            elif selected_target.get():
                target = Path(selected_target.get())
            else:
                messagebox.showwarning("Warning", "Please select a target project or enter a new path")
                return
            
            dialog.destroy()
            self._do_move(target)
        
        ctk.CTkButton(
            btn_frame, text="Move", command=do_move, width=100
        ).pack(side="left", padx=(0, 10))
        
        ctk.CTkButton(
            btn_frame, text="Cancel", command=dialog.destroy, width=100,
            fg_color="gray40", hover_color="gray50"
        ).pack(side="left")
    
    def _do_move(self, target_project_path: Path):
        """Execute the move operation."""
        if not self.selected_conversation:
            return
        
        self.move_btn.configure(state="disabled", text="Moving...")
        self.update()
        
        def move():
            success, message = move_conversation(
                self.selected_conversation.path,
                target_project_path
            )
            self.after(0, lambda: self._move_complete(success, message))
        
        threading.Thread(target=move, daemon=True).start()
    
    def _move_complete(self, success: bool, message: str):
        """Handle move completion."""
        self.move_btn.configure(state="normal", text="Move to Project...")
        
        if success:
            messagebox.showinfo(
                "Moved",
                f"{message}\n\nRemember to restart VS Code to see changes!"
            )
            # Clear selection and refresh
            self.selected_conversation = None
            self.detail_vscode_title.configure(text="")
            self.detail_stats.configure(text="No conversation selected")
            self.rename_entry.delete(0, 'end')
            self.rename_btn.configure(state="disabled")
            self.delete_btn.configure(state="disabled")
            self.move_btn.configure(state="disabled")
            
            for widget in self.branches_frame.winfo_children():
                widget.destroy()
            
            # Refresh projects list and current project
            self._load_projects()
            if self.selected_project:
                self.after(500, lambda: self._select_project(self.selected_project))
        else:
            messagebox.showerror("Error", f"Failed to move: {message}")


def run_gui():
    """Entry point for GUI application."""
    app = ConversationManagerApp()
    app.mainloop()


if __name__ == "__main__":
    run_gui()
