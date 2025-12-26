"""PhotoSifter GUI using CustomTkinter."""

import threading
from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageTk

from . import __version__, __app_name__
from .engine import PhotoSifterEngine, ScanResult, DuplicateGroup, format_size, PHOTO_EXTS, VIDEO_EXTS
from .licensing import LicenseManager, FREE_TIER_LIMIT
from .updater import check_for_updates_async

# Thumbnail settings
THUMBNAIL_SIZE = (120, 120)


# Set appearance
ctk.set_appearance_mode("system")  # "light", "dark", or "system"
ctk.set_default_color_theme("blue")


class PhotoSifterApp(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        self.title(f"{__app_name__} v{__version__}")
        self.geometry("800x600")
        self.minsize(700, 500)

        # Initialize components
        self.engine = PhotoSifterEngine()
        self.license_manager = LicenseManager()
        self.scan_result: ScanResult | None = None
        self.source_folders: list[Path] = []
        self.destination_folder: Path | None = None
        self.duplicates_folder: Path | None = None

        # Smart mode state
        self.smart_mode_var = ctk.BooleanVar(value=True)  # Smart mode is default
        self.current_group_index = 0  # For navigating duplicate groups
        self.thumbnail_cache: dict[str, ImageTk.PhotoImage] = {}  # Cache thumbnails

        # Build UI
        self._create_ui()
        self._update_license_status()

        # Check for updates on startup (non-blocking)
        self.after(1000, self._check_for_updates)

    def _create_ui(self):
        """Create the main UI layout."""
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Header frame
        self._create_header()

        # Main content frame
        self._create_main_content()

        # Status bar
        self._create_status_bar()

    def _create_header(self):
        """Create header with title and license status."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        header.grid_columnconfigure(1, weight=1)

        # Title
        title = ctk.CTkLabel(
            header,
            text=__app_name__,
            font=ctk.CTkFont(size=28, weight="bold")
        )
        title.grid(row=0, column=0, sticky="w")

        # Subtitle
        subtitle = ctk.CTkLabel(
            header,
            text="Smart photo & video deduplication and organization",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        )
        subtitle.grid(row=1, column=0, sticky="w")

        # License button
        self.license_btn = ctk.CTkButton(
            header,
            text="Free Version",
            width=140,
            command=self._show_license_dialog
        )
        self.license_btn.grid(row=0, column=2, rowspan=2, padx=(10, 0))

    def _create_main_content(self):
        """Create main content area with tabs."""
        # Tabview
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        self.tabview.grid_rowconfigure(0, weight=1)

        # Add tabs
        self.tab_scan = self.tabview.add("1. Select Folders")
        self.tab_review = self.tabview.add("2. Review Duplicates")
        self.tab_organize = self.tabview.add("3. Process")
        self.tab_manage = self.tabview.add("4. Manage Review")

        self._create_scan_tab()
        self._create_review_tab()
        self._create_organize_tab()
        self._create_manage_tab()

    def _create_scan_tab(self):
        """Create the folder selection and scan tab."""
        tab = self.tab_scan
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        # Scrollable container for all content
        scroll_container = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll_container.grid(row=0, column=0, sticky="nsew")
        scroll_container.grid_columnconfigure(0, weight=1)

        # Source folders section
        source_frame = ctk.CTkFrame(scroll_container)
        source_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        source_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            source_frame,
            text="Folders to scan:",
            font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))

        self.source_list = ctk.CTkTextbox(source_frame, height=100)
        self.source_list.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.source_list.configure(state="disabled")

        btn_frame = ctk.CTkFrame(source_frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))

        ctk.CTkButton(
            btn_frame,
            text="Add Folder",
            command=self._add_source_folder
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_frame,
            text="Clear All",
            fg_color="gray",
            command=self._clear_source_folders
        ).pack(side="left")

        # Destination folder section
        dest_frame = ctk.CTkFrame(scroll_container)
        dest_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        dest_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            dest_frame,
            text="Organize files to:",
            font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 5))

        self.dest_entry = ctk.CTkEntry(dest_frame, placeholder_text="Select destination folder...")
        self.dest_entry.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 5))

        ctk.CTkButton(
            dest_frame,
            text="Browse",
            width=100,
            command=self._select_destination
        ).grid(row=2, column=0, sticky="w", padx=10, pady=(0, 10))

        # Duplicates folder
        ctk.CTkLabel(
            dest_frame,
            text="Move duplicates to:",
            font=ctk.CTkFont(weight="bold")
        ).grid(row=3, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 5))

        self.dupes_entry = ctk.CTkEntry(dest_frame, placeholder_text="Select duplicates folder...")
        self.dupes_entry.grid(row=4, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 5))

        ctk.CTkButton(
            dest_frame,
            text="Browse",
            width=100,
            command=self._select_duplicates_folder
        ).grid(row=5, column=0, sticky="w", padx=10, pady=(0, 10))

        # Mode selection frame
        mode_frame = ctk.CTkFrame(scroll_container)
        mode_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        ctk.CTkLabel(
            mode_frame,
            text="Scan Mode",
            font=ctk.CTkFont(weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))

        # Smart mode (default)
        smart_radio = ctk.CTkRadioButton(
            mode_frame,
            text="Smart Mode (recommended)",
            variable=self.smart_mode_var,
            value=True
        )
        smart_radio.grid(row=1, column=0, sticky="w", padx=20, pady=2)

        ctk.CTkLabel(
            mode_frame,
            text="Keep originals in place, move only duplicates to review folder",
            text_color="gray",
            font=ctk.CTkFont(size=11)
        ).grid(row=2, column=0, sticky="w", padx=40, pady=(0, 5))

        # Classic mode
        classic_radio = ctk.CTkRadioButton(
            mode_frame,
            text="Classic Mode",
            variable=self.smart_mode_var,
            value=False
        )
        classic_radio.grid(row=3, column=0, sticky="w", padx=20, pady=2)

        ctk.CTkLabel(
            mode_frame,
            text="Organize all files by date (YYYY/MM) and move duplicates",
            text_color="gray",
            font=ctk.CTkFont(size=11)
        ).grid(row=4, column=0, sticky="w", padx=40, pady=(0, 10))

        # Scan button
        self.scan_btn = ctk.CTkButton(
            scroll_container,
            text="Scan for Duplicates",
            height=40,
            font=ctk.CTkFont(size=16, weight="bold"),
            command=self._start_scan
        )
        self.scan_btn.grid(row=3, column=0, pady=20)

    def _create_review_tab(self):
        """Create the review tab with duplicate group viewer."""
        tab = self.tab_review
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(2, weight=1)

        # Summary frame
        self.summary_frame = ctk.CTkFrame(tab)
        self.summary_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.summary_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Stats labels (will be populated after scan)
        self.stat_labels = {}
        stats = [
            ("total", "Total Files", "0"),
            ("unique", "Unique", "0"),
            ("groups", "Duplicate Groups", "0"),
            ("space", "Space to Recover", "0 MB"),
        ]

        for i, (key, label, value) in enumerate(stats):
            frame = ctk.CTkFrame(self.summary_frame)
            frame.grid(row=0, column=i, padx=10, pady=10, sticky="ew")

            ctk.CTkLabel(
                frame,
                text=label,
                font=ctk.CTkFont(size=12),
                text_color="gray"
            ).pack(pady=(10, 0))

            self.stat_labels[key] = ctk.CTkLabel(
                frame,
                text=value,
                font=ctk.CTkFont(size=24, weight="bold")
            )
            self.stat_labels[key].pack(pady=(0, 10))

        # Navigation frame for duplicate groups
        nav_frame = ctk.CTkFrame(tab)
        nav_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        nav_frame.grid_columnconfigure(1, weight=1)

        self.prev_group_btn = ctk.CTkButton(
            nav_frame, text="< Previous", width=100,
            command=self._prev_group, state="disabled"
        )
        self.prev_group_btn.grid(row=0, column=0, padx=10, pady=10)

        self.group_label = ctk.CTkLabel(
            nav_frame,
            text="No duplicates found",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.group_label.grid(row=0, column=1, padx=10, pady=10)

        self.next_group_btn = ctk.CTkButton(
            nav_frame, text="Next >", width=100,
            command=self._next_group, state="disabled"
        )
        self.next_group_btn.grid(row=0, column=2, padx=10, pady=10)

        # Duplicate group viewer (scrollable frame for file cards)
        self.group_viewer_frame = ctk.CTkScrollableFrame(tab, orientation="horizontal", height=280)
        self.group_viewer_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 10))

        # Placeholder
        self.placeholder_label = ctk.CTkLabel(
            self.group_viewer_frame,
            text="Scan folders to see duplicate groups here...\n\nIn each group, select which file to KEEP.\nAll other files will be moved to the review folder.",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        )
        self.placeholder_label.pack(expand=True, pady=50)

    def _create_organize_tab(self):
        """Create the organize/process tab with options and action button."""
        tab = self.tab_organize
        tab.grid_columnconfigure(0, weight=1)

        # Smart mode info frame
        self.smart_mode_info = ctk.CTkFrame(tab)
        self.smart_mode_info.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        ctk.CTkLabel(
            self.smart_mode_info,
            text="Smart Mode",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(15, 5))

        ctk.CTkLabel(
            self.smart_mode_info,
            text="Files you marked as duplicates will be moved to the review folder.\n"
                 "Your original files will stay in place. You can review and delete\n"
                 "duplicates later from the 'Manage Review' tab.",
            font=ctk.CTkFont(size=12),
            text_color="gray",
            justify="left"
        ).grid(row=1, column=0, sticky="w", padx=20, pady=(0, 15))

        # Classic mode options frame (hidden by default)
        self.classic_options_frame = ctk.CTkFrame(tab)

        ctk.CTkLabel(
            self.classic_options_frame,
            text="Classic Mode Options",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(15, 10))

        # Organize by date option
        self.organize_by_date_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            self.classic_options_frame,
            text="Organize files by date (YYYY/MM folders)",
            variable=self.organize_by_date_var
        ).grid(row=1, column=0, sticky="w", padx=20, pady=5)

        # Move vs copy option
        self.move_files_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            self.classic_options_frame,
            text="Move files (uncheck to copy instead)",
            variable=self.move_files_var
        ).grid(row=2, column=0, sticky="w", padx=20, pady=(5, 15))

        # Action summary
        self.action_summary = ctk.CTkLabel(
            tab,
            text="Run a scan first to see what will happen.",
            font=ctk.CTkFont(size=14)
        )
        self.action_summary.grid(row=2, column=0, pady=20)

        # Process button
        self.organize_btn = ctk.CTkButton(
            tab,
            text="Move Duplicates to Review",
            height=50,
            font=ctk.CTkFont(size=18, weight="bold"),
            command=self._start_organize,
            state="disabled"
        )
        self.organize_btn.grid(row=3, column=0, pady=20)

        # Progress bar (hidden initially)
        self.progress_bar = ctk.CTkProgressBar(tab, width=400)
        self.progress_bar.grid(row=4, column=0, pady=10)
        self.progress_bar.set(0)
        self.progress_bar.grid_remove()

        self.progress_label = ctk.CTkLabel(tab, text="")
        self.progress_label.grid(row=5, column=0)
        self.progress_label.grid_remove()

    def _create_manage_tab(self):
        """Create the manage review folder tab."""
        tab = self.tab_manage
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        # Header
        header_frame = ctk.CTkFrame(tab)
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header_frame,
            text="Review Folder",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(15, 5))

        self.review_folder_label = ctk.CTkLabel(
            header_frame,
            text="No review folder selected",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.review_folder_label.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 10))

        ctk.CTkButton(
            header_frame,
            text="Refresh",
            width=100,
            command=self._refresh_review_folder
        ).grid(row=0, column=1, sticky="e", padx=20, pady=(15, 5))

        # File list
        self.review_list_frame = ctk.CTkScrollableFrame(tab)
        self.review_list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.review_list_frame.grid_columnconfigure(0, weight=1)

        self.review_placeholder = ctk.CTkLabel(
            self.review_list_frame,
            text="No files in review folder.\n\nAfter processing duplicates, they will appear here\nfor you to review, delete, or revert.",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        )
        self.review_placeholder.pack(expand=True, pady=50)

        # Action buttons
        btn_frame = ctk.CTkFrame(tab, fg_color="transparent")
        btn_frame.grid(row=2, column=0, pady=10)

        ctk.CTkButton(
            btn_frame,
            text="Delete All (to Trash)",
            fg_color="red",
            hover_color="darkred",
            command=self._delete_all_review
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            btn_frame,
            text="Revert All",
            fg_color="gray",
            command=self._revert_all_review
        ).pack(side="left", padx=10)

    def _create_status_bar(self):
        """Create status bar at bottom."""
        status_frame = ctk.CTkFrame(self, height=30, corner_radius=0)
        status_frame.grid(row=3, column=0, sticky="ew")
        status_frame.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            status_frame,
            text="Ready",
            font=ctk.CTkFont(size=12)
        )
        self.status_label.grid(row=0, column=0, sticky="w", padx=10, pady=5)

        self.license_status = ctk.CTkLabel(
            status_frame,
            text="",
            font=ctk.CTkFont(size=12)
        )
        self.license_status.grid(row=0, column=1, sticky="e", padx=10, pady=5)

    def _update_license_status(self):
        """Update license status display."""
        status = self.license_manager.get_status_text()
        self.license_status.configure(text=status)

        if self.license_manager.is_licensed:
            self.license_btn.configure(text="Licensed", fg_color="green")
        else:
            remaining = self.license_manager.photos_remaining
            if remaining < 100:
                self.license_btn.configure(fg_color="orange")
            else:
                self.license_btn.configure(fg_color=["#3B8ED0", "#1F6AA5"])

    def _add_source_folder(self):
        """Add a folder to scan."""
        folder = filedialog.askdirectory(title="Select folder to scan")
        if folder:
            path = Path(folder)
            if path not in self.source_folders:
                self.source_folders.append(path)
                self._update_source_list()

    def _clear_source_folders(self):
        """Clear all source folders."""
        self.source_folders = []
        self._update_source_list()

    def _update_source_list(self):
        """Update the source folders display."""
        self.source_list.configure(state="normal")
        self.source_list.delete("1.0", "end")
        for folder in self.source_folders:
            self.source_list.insert("end", f"{folder}\n")
        self.source_list.configure(state="disabled")

    def _select_destination(self):
        """Select destination folder."""
        folder = filedialog.askdirectory(title="Select destination folder")
        if folder:
            self.destination_folder = Path(folder)
            self.dest_entry.delete(0, "end")
            self.dest_entry.insert(0, str(folder))

            # Auto-set duplicates folder if not set
            if not self.duplicates_folder:
                self.duplicates_folder = self.destination_folder / "Duplicates"
                self.dupes_entry.delete(0, "end")
                self.dupes_entry.insert(0, str(self.duplicates_folder))

    def _select_duplicates_folder(self):
        """Select duplicates folder."""
        folder = filedialog.askdirectory(title="Select folder for duplicates")
        if folder:
            self.duplicates_folder = Path(folder)
            self.dupes_entry.delete(0, "end")
            self.dupes_entry.insert(0, str(folder))

    def _start_scan(self):
        """Start scanning folders."""
        if not self.source_folders:
            messagebox.showwarning("No folders", "Please add at least one folder to scan.")
            return

        # Check free tier limit
        can_process, max_allowed = self.license_manager.can_process(999999)
        if not can_process and max_allowed == 0:
            self._show_upgrade_prompt()
            return

        self.scan_btn.configure(state="disabled", text="Scanning...")
        self.status_label.configure(text="Scanning folders...")

        # Run scan in background thread
        thread = threading.Thread(target=self._run_scan, daemon=True)
        thread.start()

    def _run_scan(self):
        """Run the scan in a background thread."""
        def progress(current, total, filename):
            self.after(0, lambda: self.status_label.configure(
                text=f"Scanning: {current}/{total} - {filename[:50]}"
            ))

        self.scan_result = self.engine.scan_folders(
            self.source_folders,
            use_phash=True,
            progress_callback=progress
        )

        # Update UI on main thread
        self.after(0, self._scan_complete)

    def _scan_complete(self):
        """Handle scan completion."""
        self.scan_btn.configure(state="normal", text="Scan for Duplicates")

        if not self.scan_result:
            self.status_label.configure(text="Scan failed")
            return

        result = self.scan_result

        # Check free tier limit
        if not self.license_manager.is_licensed:
            if result.total_files > self.license_manager.photos_remaining:
                remaining = self.license_manager.photos_remaining
                messagebox.showinfo(
                    "Free Tier Limit",
                    f"Found {result.total_files:,} files, but you have {remaining:,} remaining in your free tier.\n\n"
                    f"Upgrade to process unlimited files!"
                )

        # Update stats
        self.stat_labels["total"].configure(text=f"{result.total_files:,}")
        self.stat_labels["unique"].configure(text=f"{len(result.unique_files):,}")
        self.stat_labels["groups"].configure(text=f"{result.duplicate_group_count:,}")
        self.stat_labels["space"].configure(text=format_size(result.space_recoverable))

        # Show duplicate groups viewer
        self.current_group_index = 0
        self.thumbnail_cache.clear()

        if result.duplicate_groups:
            # Enable navigation
            self._update_group_navigation()
            self._show_duplicate_group(0)
        else:
            self.group_label.configure(text="No duplicates found")
            self.prev_group_btn.configure(state="disabled")
            self.next_group_btn.configure(state="disabled")
            # Show placeholder
            for widget in self.group_viewer_frame.winfo_children():
                widget.destroy()
            ctk.CTkLabel(
                self.group_viewer_frame,
                text="No duplicates found in the scanned folders.",
                font=ctk.CTkFont(size=14),
                text_color="gray"
            ).pack(expand=True, pady=50)

        # Update organize tab based on mode
        if self.smart_mode_var.get():
            self.smart_mode_info.grid(row=0, column=0, sticky="ew", pady=(0, 10))
            self.classic_options_frame.grid_remove()
            self.organize_btn.configure(text="Move Duplicates to Review")
            self.action_summary.configure(
                text=f"Ready to move {result.duplicate_count:,} duplicates to review folder.\n"
                     f"Your {len(result.unique_files):,} unique files will stay in place."
            )
        else:
            self.smart_mode_info.grid_remove()
            self.classic_options_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
            self.organize_btn.configure(text="Organize Photos")
            action = "move" if self.move_files_var.get() else "copy"
            self.action_summary.configure(
                text=f"Ready to {action} {len(result.unique_files):,} unique files and "
                     f"move {result.duplicate_count:,} duplicates."
            )

        if result.duplicate_groups:
            self.organize_btn.configure(state="normal")

        # Switch to review tab
        self.tabview.set("2. Review Duplicates")
        self.status_label.configure(text=f"Scan complete: {result.total_files:,} files, {result.duplicate_group_count:,} duplicate groups")

    def _update_group_navigation(self):
        """Update the navigation buttons state."""
        if not self.scan_result or not self.scan_result.duplicate_groups:
            return

        total = len(self.scan_result.duplicate_groups)
        self.group_label.configure(text=f"Group {self.current_group_index + 1} of {total}")

        self.prev_group_btn.configure(
            state="normal" if self.current_group_index > 0 else "disabled"
        )
        self.next_group_btn.configure(
            state="normal" if self.current_group_index < total - 1 else "disabled"
        )

    def _prev_group(self):
        """Navigate to previous duplicate group."""
        if self.current_group_index > 0:
            self.current_group_index -= 1
            self._update_group_navigation()
            self._show_duplicate_group(self.current_group_index)

    def _next_group(self):
        """Navigate to next duplicate group."""
        if self.scan_result and self.current_group_index < len(self.scan_result.duplicate_groups) - 1:
            self.current_group_index += 1
            self._update_group_navigation()
            self._show_duplicate_group(self.current_group_index)

    def _show_duplicate_group(self, index: int):
        """Display a duplicate group with file cards."""
        if not self.scan_result or index >= len(self.scan_result.duplicate_groups):
            return

        group = self.scan_result.duplicate_groups[index]

        # Clear previous cards
        for widget in self.group_viewer_frame.winfo_children():
            widget.destroy()

        # Create radio button variable for this group
        self.current_selection_var = ctk.StringVar(value=str(group.selected_to_keep))

        # Create a card for each file
        for i, media_file in enumerate(group.files):
            self._create_file_card(group, media_file, i)

    def _create_file_card(self, group: DuplicateGroup, media_file, index: int):
        """Create a card widget for a file in a duplicate group."""
        is_selected = media_file.path == group.selected_to_keep

        # Highlight selected card with green border
        card = ctk.CTkFrame(
            self.group_viewer_frame,
            width=180,
            border_width=3 if is_selected else 1,
            border_color="green" if is_selected else "gray"
        )
        card.pack(side="left", padx=10, pady=10, fill="y")
        card.pack_propagate(False)

        # Status label at top
        status_label = ctk.CTkLabel(
            card,
            text="KEEPING" if is_selected else "Will be moved to review",
            font=ctk.CTkFont(size=11, weight="bold" if is_selected else "normal"),
            text_color="green" if is_selected else "gray"
        )
        status_label.pack(pady=(8, 2))

        # Thumbnail
        thumbnail_label = ctk.CTkLabel(card, text="", width=150, height=120)
        thumbnail_label.pack(pady=(5, 5))

        # Load thumbnail in background
        self._load_thumbnail(media_file.path, thumbnail_label)

        # Radio button to select - consistent label
        radio = ctk.CTkRadioButton(
            card,
            text="Keep this one",
            variable=self.current_selection_var,
            value=str(media_file.path),
            command=lambda g=group, f=media_file: self._select_file_to_keep(g, f)
        )
        radio.pack(pady=5)

        # File info
        path_text = str(media_file.path)
        if len(path_text) > 25:
            path_text = "..." + path_text[-22:]

        ctk.CTkLabel(
            card,
            text=path_text,
            font=ctk.CTkFont(size=10),
            text_color="gray",
            wraplength=160
        ).pack(pady=2)

        ctk.CTkLabel(
            card,
            text=format_size(media_file.size),
            font=ctk.CTkFont(size=11, weight="bold")
        ).pack(pady=2)

        if media_file.date_taken:
            ctk.CTkLabel(
                card,
                text=media_file.date_taken.strftime("%Y-%m-%d"),
                font=ctk.CTkFont(size=10),
                text_color="gray"
            ).pack(pady=2)

    def _load_thumbnail(self, file_path: Path, label: ctk.CTkLabel):
        """Load a thumbnail for display."""
        cache_key = str(file_path)

        if cache_key in self.thumbnail_cache:
            label.configure(image=self.thumbnail_cache[cache_key])
            return

        def load():
            try:
                if file_path.suffix.lower() in PHOTO_EXTS:
                    img = Image.open(file_path)
                    img.thumbnail(THUMBNAIL_SIZE)
                    photo = ImageTk.PhotoImage(img)
                    self.thumbnail_cache[cache_key] = photo
                    self.after(0, lambda: label.configure(image=photo))
                else:
                    # Video or unsupported - show file type
                    ext = file_path.suffix.upper()
                    self.after(0, lambda e=ext: label.configure(text=f"{e}\nVideo"))
            except Exception:
                self.after(0, lambda: label.configure(text="[Error]"))

        threading.Thread(target=load, daemon=True).start()

    def _select_file_to_keep(self, group: DuplicateGroup, media_file):
        """Handle selection of which file to keep in a duplicate group."""
        group.selected_to_keep = media_file.path

        # Refresh the display to update labels
        self._show_duplicate_group(self.current_group_index)

        # Update space recoverable display
        if self.scan_result:
            self.stat_labels["space"].configure(
                text=format_size(self.scan_result.space_recoverable)
            )

    def _refresh_review_folder(self):
        """Refresh the review folder file list."""
        if not self.duplicates_folder or not self.duplicates_folder.exists():
            self.review_folder_label.configure(text="No review folder selected")
            return

        self.review_folder_label.configure(text=str(self.duplicates_folder))

        # Clear previous items
        for widget in self.review_list_frame.winfo_children():
            widget.destroy()

        files = self.engine.get_review_folder_files(self.duplicates_folder)

        if not files:
            ctk.CTkLabel(
                self.review_list_frame,
                text="No files in review folder.",
                font=ctk.CTkFont(size=14),
                text_color="gray"
            ).pack(expand=True, pady=50)
            return

        # Create a row for each file
        for filename, original_path, size in files:
            row = ctk.CTkFrame(self.review_list_frame)
            row.pack(fill="x", pady=2, padx=5)
            row.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                row,
                text=filename,
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w"
            ).grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(5, 0))

            ctk.CTkLabel(
                row,
                text=f"Original: {original_path}",
                font=ctk.CTkFont(size=10),
                text_color="gray",
                anchor="w"
            ).grid(row=1, column=0, sticky="w", padx=10)

            ctk.CTkLabel(
                row,
                text=format_size(size),
                font=ctk.CTkFont(size=10)
            ).grid(row=1, column=1, sticky="e", padx=5)

            btn_frame = ctk.CTkFrame(row, fg_color="transparent")
            btn_frame.grid(row=0, column=3, rowspan=2, padx=5, pady=5)

            ctk.CTkButton(
                btn_frame,
                text="Revert",
                width=60,
                height=25,
                font=ctk.CTkFont(size=11),
                command=lambda f=filename: self._revert_single_file(f)
            ).pack(side="left", padx=2)

            ctk.CTkButton(
                btn_frame,
                text="Delete",
                width=60,
                height=25,
                font=ctk.CTkFont(size=11),
                fg_color="red",
                hover_color="darkred",
                command=lambda f=filename: self._delete_single_file(f)
            ).pack(side="left", padx=2)

    def _revert_single_file(self, filename: str):
        """Revert a single file to its original location."""
        if not self.duplicates_folder:
            return

        success, message = self.engine.revert_file(self.duplicates_folder, filename)
        if success:
            messagebox.showinfo("Reverted", message)
        else:
            messagebox.showerror("Error", message)
        self._refresh_review_folder()

    def _delete_single_file(self, filename: str):
        """Delete a single file from review folder."""
        if not self.duplicates_folder:
            return

        if messagebox.askyesno("Confirm Delete", f"Delete {filename}?\n\nThis will move the file to your system trash."):
            success, message = self.engine.delete_from_review(self.duplicates_folder, filename)
            if success:
                self.status_label.configure(text=message)
            else:
                messagebox.showerror("Error", message)
            self._refresh_review_folder()

    def _delete_all_review(self):
        """Delete all files from review folder."""
        if not self.duplicates_folder or not self.duplicates_folder.exists():
            messagebox.showwarning("No folder", "No review folder selected.")
            return

        files = self.engine.get_review_folder_files(self.duplicates_folder)
        if not files:
            messagebox.showinfo("Empty", "No files to delete.")
            return

        if messagebox.askyesno(
            "Confirm Delete All",
            f"Delete all {len(files)} files from review folder?\n\n"
            "Files will be moved to your system trash."
        ):
            deleted = 0
            for filename, _, _ in files:
                success, _ = self.engine.delete_from_review(self.duplicates_folder, filename)
                if success:
                    deleted += 1

            messagebox.showinfo("Complete", f"Deleted {deleted} files.")
            self._refresh_review_folder()

    def _revert_all_review(self):
        """Revert all files to their original locations."""
        if not self.duplicates_folder or not self.duplicates_folder.exists():
            messagebox.showwarning("No folder", "No review folder selected.")
            return

        files = self.engine.get_review_folder_files(self.duplicates_folder)
        if not files:
            messagebox.showinfo("Empty", "No files to revert.")
            return

        if messagebox.askyesno(
            "Confirm Revert All",
            f"Revert all {len(files)} files to their original locations?"
        ):
            reverted = 0
            for filename, _, _ in files:
                success, _ = self.engine.revert_file(self.duplicates_folder, filename)
                if success:
                    reverted += 1

            messagebox.showinfo("Complete", f"Reverted {reverted} files.")
            self._refresh_review_folder()

    def _start_organize(self):
        """Start organizing/processing files."""
        if not self.scan_result:
            messagebox.showwarning("No scan", "Please scan folders first.")
            return

        if not self.duplicates_folder:
            if self.destination_folder:
                self.duplicates_folder = self.destination_folder / "Duplicates"
            else:
                messagebox.showwarning("No folder", "Please select a duplicates/review folder.")
                return

        is_smart_mode = self.smart_mode_var.get()

        # For classic mode, destination is required
        if not is_smart_mode and not self.destination_folder:
            messagebox.showwarning("No destination", "Please select a destination folder.")
            return

        # Check free tier
        to_process = self.scan_result.duplicate_count
        if not is_smart_mode:
            to_process += len(self.scan_result.unique_files)

        can_process, max_allowed = self.license_manager.can_process(to_process)

        if not can_process:
            if max_allowed == 0:
                self._show_upgrade_prompt()
                return
            else:
                result = messagebox.askyesno(
                    "Free Tier Limit",
                    f"You can only process {max_allowed:,} more files in the free tier.\n\n"
                    f"Process {max_allowed:,} files now?"
                )
                if not result:
                    return

        # Confirm action
        if is_smart_mode:
            result = messagebox.askyesno(
                "Confirm",
                f"Move {self.scan_result.duplicate_count:,} duplicate files to:\n{self.duplicates_folder}\n\n"
                f"Your {len(self.scan_result.unique_files):,} original files will stay in place.\n\n"
                "Continue?"
            )
        else:
            action = "Move" if self.move_files_var.get() else "Copy"
            result = messagebox.askyesno(
                "Confirm",
                f"{action} {len(self.scan_result.unique_files):,} photos to:\n{self.destination_folder}\n\n"
                f"Move {self.scan_result.duplicate_count:,} duplicates to:\n{self.duplicates_folder}\n\n"
                "Continue?"
            )

        if not result:
            return

        btn_text = "Moving..." if is_smart_mode else "Organizing..."
        self.organize_btn.configure(state="disabled", text=btn_text)
        self.progress_bar.grid()
        self.progress_label.grid()
        self.progress_bar.set(0)

        # Run in background
        thread = threading.Thread(target=self._run_organize, daemon=True)
        thread.start()

    def _run_organize(self):
        """Run organization in background thread."""
        is_smart_mode = self.smart_mode_var.get()

        def progress(current, total, filename):
            pct = current / total if total > 0 else 0
            self.after(0, lambda: self._update_progress(pct, filename))

        if is_smart_mode:
            # Smart mode: only move duplicates to review folder
            dupes_moved, errors = self.engine.move_duplicates_to_review(
                result=self.scan_result,
                review_folder=self.duplicates_folder,
                progress_callback=progress
            )
            organized = 0
        else:
            # Classic mode: organize all files
            organized, dupes_moved, errors = self.engine.organize_files(
                destination=self.destination_folder,
                duplicates_folder=self.duplicates_folder,
                result=self.scan_result,
                organize_by_date=self.organize_by_date_var.get(),
                move_files=self.move_files_var.get(),
                progress_callback=progress
            )

        # Record usage for licensing
        self.license_manager.record_processed(organized + dupes_moved)

        # Update UI
        self.after(0, lambda: self._organize_complete(organized, dupes_moved, errors, is_smart_mode))

    def _update_progress(self, pct: float, filename: str):
        """Update progress display."""
        self.progress_bar.set(pct)
        self.progress_label.configure(text=f"Processing: {filename[:60]}")

    def _organize_complete(self, organized: int, dupes_moved: int, errors: list, is_smart_mode: bool = False):
        """Handle organization completion."""
        btn_text = "Move Duplicates to Review" if is_smart_mode else "Organize Photos"
        self.organize_btn.configure(state="normal", text=btn_text)
        self.progress_bar.grid_remove()
        self.progress_label.grid_remove()

        self._update_license_status()

        if is_smart_mode:
            if errors:
                messagebox.showwarning(
                    "Complete with errors",
                    f"Moved {dupes_moved:,} duplicates to review folder\n\n"
                    f"{len(errors)} errors occurred."
                )
            else:
                messagebox.showinfo(
                    "Complete!",
                    f"Moved {dupes_moved:,} duplicates to the review folder.\n\n"
                    f"Go to 'Manage Review' tab to delete or revert files."
                )
            self.status_label.configure(text=f"Done: {dupes_moved:,} duplicates moved to review")

            # Refresh review folder display
            self._refresh_review_folder()

            # Switch to manage tab
            self.tabview.set("4. Manage Review")
        else:
            if errors:
                messagebox.showwarning(
                    "Complete with errors",
                    f"Organized {organized:,} files\n"
                    f"Moved {dupes_moved:,} duplicates\n\n"
                    f"{len(errors)} errors occurred."
                )
            else:
                messagebox.showinfo(
                    "Complete!",
                    f"Successfully organized {organized:,} files!\n"
                    f"Moved {dupes_moved:,} duplicates to the duplicates folder."
                )
            self.status_label.configure(text=f"Done: {organized:,} organized, {dupes_moved:,} duplicates moved")

        # Reset for next run
        self.scan_result = None
        self.organize_btn.configure(state="disabled")
        self.current_group_index = 0
        self.thumbnail_cache.clear()

    def _show_license_dialog(self):
        """Show license activation dialog."""
        dialog = LicenseDialog(self, self.license_manager)
        dialog.grab_set()
        self.wait_window(dialog)
        self._update_license_status()

    def _show_upgrade_prompt(self):
        """Show upgrade prompt when free tier is exhausted."""
        result = messagebox.askyesno(
            "Free Tier Limit Reached",
            f"You've processed {FREE_TIER_LIMIT:,} files with the free version.\n\n"
            "Upgrade to PhotoSifter Pro for unlimited organization!\n\n"
            "Would you like to enter a license key?"
        )
        if result:
            self._show_license_dialog()

    def _check_for_updates(self):
        """Check for updates in background."""
        def on_update_check(version, url, notes):
            if version and url:
                self.after(0, lambda: self._show_update_dialog(version, url, notes))

        check_for_updates_async(on_update_check)

    def _show_update_dialog(self, version: str, url: str, notes: str):
        """Show update available dialog."""
        notes_preview = notes[:200] + "..." if len(notes) > 200 else notes

        result = messagebox.askyesno(
            "Update Available",
            f"A new version of PhotoSifter is available!\n\n"
            f"Current version: {__version__}\n"
            f"New version: {version}\n\n"
            f"{notes_preview}\n\n"
            "Would you like to download the update?"
        )

        if result:
            import webbrowser
            webbrowser.open(url)


class LicenseDialog(ctk.CTkToplevel):
    """License activation dialog."""

    def __init__(self, parent, license_manager: LicenseManager):
        super().__init__(parent)

        self.license_manager = license_manager

        self.title("License")
        self.geometry("400x250")
        self.resizable(False, False)

        # Center on parent
        self.transient(parent)

        self._create_ui()

    def _create_ui(self):
        self.grid_columnconfigure(0, weight=1)

        # Status
        status = "Licensed" if self.license_manager.is_licensed else "Free Version"
        ctk.CTkLabel(
            self,
            text=status,
            font=ctk.CTkFont(size=20, weight="bold")
        ).grid(row=0, column=0, pady=(20, 5))

        stats_text = (
            f"Photos processed: {self.license_manager.photos_processed:,}\n"
            f"Remaining: {self.license_manager.photos_remaining if not self.license_manager.is_licensed else 'Unlimited'}"
        )
        ctk.CTkLabel(self, text=stats_text).grid(row=1, column=0, pady=(0, 20))

        # License key entry
        ctk.CTkLabel(self, text="Enter license key:").grid(row=2, column=0, pady=(0, 5))

        self.key_entry = ctk.CTkEntry(self, width=350, placeholder_text="XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX")
        self.key_entry.grid(row=3, column=0, pady=(0, 10))

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=4, column=0, pady=20)

        ctk.CTkButton(
            btn_frame,
            text="Activate",
            command=self._activate
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="Close",
            fg_color="gray",
            command=self.destroy
        ).pack(side="left", padx=5)

        # Buy link
        ctk.CTkLabel(
            self,
            text="Get a license at photosifter.com",
            text_color="gray",
            font=ctk.CTkFont(size=12)
        ).grid(row=5, column=0, pady=(0, 10))

    def _activate(self):
        """Try to activate the license."""
        key = self.key_entry.get().strip().upper()

        if not key:
            messagebox.showwarning("No key", "Please enter a license key.")
            return

        success, message = self.license_manager.activate_license(key)

        if success:
            messagebox.showinfo("Success", message)
            self.destroy()
        else:
            messagebox.showerror("Invalid", message)


def run():
    """Run the PhotoSifter application."""
    app = PhotoSifterApp()
    app.mainloop()
