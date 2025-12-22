"""PhotoSifter GUI using CustomTkinter."""

import threading
from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk

from . import __version__, __app_name__
from .engine import PhotoSifterEngine, ScanResult, format_size
from .licensing import LicenseManager, FREE_TIER_LIMIT


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

        # Build UI
        self._create_ui()
        self._update_license_status()

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
            text="Smart photo deduplication and organization",
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
        self.tab_review = self.tabview.add("2. Review")
        self.tab_organize = self.tabview.add("3. Organize")

        self._create_scan_tab()
        self._create_review_tab()
        self._create_organize_tab()

    def _create_scan_tab(self):
        """Create the folder selection and scan tab."""
        tab = self.tab_scan
        tab.grid_columnconfigure(0, weight=1)

        # Source folders section
        source_frame = ctk.CTkFrame(tab)
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
        dest_frame = ctk.CTkFrame(tab)
        dest_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        dest_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            dest_frame,
            text="Organize photos to:",
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

        # Scan button
        self.scan_btn = ctk.CTkButton(
            tab,
            text="Scan for Duplicates",
            height=40,
            font=ctk.CTkFont(size=16, weight="bold"),
            command=self._start_scan
        )
        self.scan_btn.grid(row=2, column=0, pady=20)

    def _create_review_tab(self):
        """Create the review tab showing scan results."""
        tab = self.tab_review
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        # Summary frame
        self.summary_frame = ctk.CTkFrame(tab)
        self.summary_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.summary_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Stats labels (will be populated after scan)
        self.stat_labels = {}
        stats = [
            ("total", "Total Files", "0"),
            ("unique", "Unique", "0"),
            ("duplicates", "Duplicates", "0"),
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

        # Results list
        self.results_text = ctk.CTkTextbox(tab)
        self.results_text.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        self.results_text.configure(state="disabled")

        # Placeholder text
        self._update_results_text("Scan folders to see results here...")

    def _create_organize_tab(self):
        """Create the organize tab with options and action button."""
        tab = self.tab_organize
        tab.grid_columnconfigure(0, weight=1)

        # Options frame
        options_frame = ctk.CTkFrame(tab)
        options_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        ctk.CTkLabel(
            options_frame,
            text="Organization Options",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(15, 10))

        # Organize by date option
        self.organize_by_date_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            options_frame,
            text="Organize photos by date (YYYY/MM folders)",
            variable=self.organize_by_date_var
        ).grid(row=1, column=0, sticky="w", padx=20, pady=5)

        # Move vs copy option
        self.move_files_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            options_frame,
            text="Move files (uncheck to copy instead)",
            variable=self.move_files_var
        ).grid(row=2, column=0, sticky="w", padx=20, pady=(5, 15))

        # Action summary
        self.action_summary = ctk.CTkLabel(
            tab,
            text="Run a scan first to see what will happen.",
            font=ctk.CTkFont(size=14)
        )
        self.action_summary.grid(row=1, column=0, pady=20)

        # Organize button
        self.organize_btn = ctk.CTkButton(
            tab,
            text="Organize Photos",
            height=50,
            font=ctk.CTkFont(size=18, weight="bold"),
            command=self._start_organize,
            state="disabled"
        )
        self.organize_btn.grid(row=2, column=0, pady=20)

        # Progress bar (hidden initially)
        self.progress_bar = ctk.CTkProgressBar(tab, width=400)
        self.progress_bar.grid(row=3, column=0, pady=10)
        self.progress_bar.set(0)
        self.progress_bar.grid_remove()

        self.progress_label = ctk.CTkLabel(tab, text="")
        self.progress_label.grid(row=4, column=0)
        self.progress_label.grid_remove()

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
                    f"Found {result.total_files:,} photos, but you have {remaining:,} remaining in your free tier.\n\n"
                    f"Upgrade to process unlimited photos!"
                )

        # Update stats
        self.stat_labels["total"].configure(text=f"{result.total_files:,}")
        self.stat_labels["unique"].configure(text=f"{len(result.unique_files):,}")
        self.stat_labels["duplicates"].configure(text=f"{result.duplicate_count:,}")
        self.stat_labels["space"].configure(text=format_size(result.space_recoverable))

        # Update results text
        lines = [f"Scan complete!\n"]
        lines.append(f"Found {result.duplicate_count:,} duplicates ({format_size(result.space_recoverable)} recoverable)\n\n")

        if result.duplicates:
            lines.append("Duplicates found:\n")
            for dup in result.duplicates[:100]:  # Show first 100
                lines.append(f"  {dup.path.name}\n")
                lines.append(f"    -> duplicate of: {dup.duplicate_of.name}\n")

            if len(result.duplicates) > 100:
                lines.append(f"\n  ... and {len(result.duplicates) - 100} more\n")

        if result.errors:
            lines.append(f"\nErrors ({len(result.errors)}):\n")
            for err in result.errors[:10]:
                lines.append(f"  {err}\n")

        self._update_results_text("".join(lines))

        # Update organize tab
        action = "move" if self.move_files_var.get() else "copy"
        self.action_summary.configure(
            text=f"Ready to {action} {len(result.unique_files):,} unique files and "
                 f"move {result.duplicate_count:,} duplicates."
        )

        if result.total_files > 0:
            self.organize_btn.configure(state="normal")

        # Switch to review tab
        self.tabview.set("2. Review")
        self.status_label.configure(text=f"Scan complete: {result.total_files:,} files found")

    def _update_results_text(self, text: str):
        """Update the results textbox."""
        self.results_text.configure(state="normal")
        self.results_text.delete("1.0", "end")
        self.results_text.insert("1.0", text)
        self.results_text.configure(state="disabled")

    def _start_organize(self):
        """Start organizing files."""
        if not self.scan_result:
            messagebox.showwarning("No scan", "Please scan folders first.")
            return

        if not self.destination_folder:
            messagebox.showwarning("No destination", "Please select a destination folder.")
            return

        if not self.duplicates_folder:
            self.duplicates_folder = self.destination_folder / "Duplicates"

        # Check free tier
        to_process = len(self.scan_result.unique_files) + len(self.scan_result.duplicates)
        can_process, max_allowed = self.license_manager.can_process(to_process)

        if not can_process:
            if max_allowed == 0:
                self._show_upgrade_prompt()
                return
            else:
                result = messagebox.askyesno(
                    "Free Tier Limit",
                    f"You can only process {max_allowed:,} more photos in the free tier.\n\n"
                    f"Process {max_allowed:,} photos now?"
                )
                if not result:
                    return

        # Confirm action
        action = "Move" if self.move_files_var.get() else "Copy"
        result = messagebox.askyesno(
            "Confirm",
            f"{action} {len(self.scan_result.unique_files):,} photos to:\n{self.destination_folder}\n\n"
            f"Move {len(self.scan_result.duplicates):,} duplicates to:\n{self.duplicates_folder}\n\n"
            "Continue?"
        )

        if not result:
            return

        self.organize_btn.configure(state="disabled", text="Organizing...")
        self.progress_bar.grid()
        self.progress_label.grid()
        self.progress_bar.set(0)

        # Run in background
        thread = threading.Thread(target=self._run_organize, daemon=True)
        thread.start()

    def _run_organize(self):
        """Run organization in background thread."""
        total = len(self.scan_result.unique_files) + len(self.scan_result.duplicates)

        def progress(current, total, filename):
            pct = current / total if total > 0 else 0
            self.after(0, lambda: self._update_progress(pct, filename))

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
        self.after(0, lambda: self._organize_complete(organized, dupes_moved, errors))

    def _update_progress(self, pct: float, filename: str):
        """Update progress display."""
        self.progress_bar.set(pct)
        self.progress_label.configure(text=f"Processing: {filename[:60]}")

    def _organize_complete(self, organized: int, dupes_moved: int, errors: list):
        """Handle organization completion."""
        self.organize_btn.configure(state="normal", text="Organize Photos")
        self.progress_bar.grid_remove()
        self.progress_label.grid_remove()

        self._update_license_status()

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
                f"Successfully organized {organized:,} photos!\n"
                f"Moved {dupes_moved:,} duplicates to the duplicates folder."
            )

        self.status_label.configure(text=f"Done: {organized:,} organized, {dupes_moved:,} duplicates moved")

        # Reset for next run
        self.scan_result = None
        self.organize_btn.configure(state="disabled")

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
            f"You've processed {FREE_TIER_LIMIT:,} photos with the free version.\n\n"
            "Upgrade to PhotoSifter Pro for unlimited photo organization!\n\n"
            "Would you like to enter a license key?"
        )
        if result:
            self._show_license_dialog()


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
