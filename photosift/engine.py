"""Core engine for photo deduplication and organization."""

import os
import hashlib
from datetime import datetime
from pathlib import Path
import json
import shutil
from dataclasses import dataclass, field
from typing import Callable, Optional
from PIL import Image
import imagehash


PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".tif", ".heic", ".heif"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".wmv", ".m4v", ".3gp"}
MEDIA_EXTS = PHOTO_EXTS | VIDEO_EXTS


@dataclass
class MediaFile:
    """Represents a media file with its metadata."""
    path: Path
    size: int
    sha256: str = ""
    phash: str = ""  # Perceptual hash for images
    date_taken: datetime | None = None
    is_duplicate: bool = False
    duplicate_of: Path | None = None
    original_path: Path | None = None  # For tracking original location when moved to review


@dataclass
class DuplicateGroup:
    """A group of files that are duplicates of each other."""
    sha256: str
    files: list[MediaFile] = field(default_factory=list)
    selected_to_keep: Path | None = None  # User's choice of which file to keep

    def __post_init__(self):
        # Default: keep the first file
        if self.files and self.selected_to_keep is None:
            self.selected_to_keep = self.files[0].path

    @property
    def files_to_delete(self) -> list[MediaFile]:
        """Return files that are marked for deletion (not selected to keep)."""
        return [f for f in self.files if f.path != self.selected_to_keep]

    @property
    def file_to_keep(self) -> Optional[MediaFile]:
        """Return the file selected to keep."""
        for f in self.files:
            if f.path == self.selected_to_keep:
                return f
        return self.files[0] if self.files else None

    @property
    def space_recoverable(self) -> int:
        """Total size of files that will be deleted."""
        return sum(f.size for f in self.files_to_delete)


@dataclass
class ScanResult:
    """Results from scanning folders."""
    total_files: int = 0
    total_size: int = 0
    duplicate_groups: list[DuplicateGroup] = field(default_factory=list)
    unique_files: list[MediaFile] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def duplicates(self) -> list[MediaFile]:
        """Return flat list of all duplicate files (for backward compatibility)."""
        all_dupes = []
        for group in self.duplicate_groups:
            all_dupes.extend(group.files_to_delete)
        return all_dupes

    @property
    def duplicate_count(self) -> int:
        """Total number of files that will be deleted."""
        return sum(len(g.files_to_delete) for g in self.duplicate_groups)

    @property
    def duplicate_group_count(self) -> int:
        """Number of duplicate groups found."""
        return len(self.duplicate_groups)

    @property
    def space_recoverable(self) -> int:
        """Total space that can be recovered by deleting duplicates."""
        return sum(g.space_recoverable for g in self.duplicate_groups)

    def get_all_files_to_delete(self) -> list[MediaFile]:
        """Get all files marked for deletion across all groups."""
        files = []
        for group in self.duplicate_groups:
            files.extend(group.files_to_delete)
        return files


class PhotoSifterEngine:
    """Core engine for scanning, deduplicating, and organizing photos."""

    def __init__(self):
        self.files: list[MediaFile] = []
        self.hash_index: dict[str, MediaFile] = {}  # sha256 -> first file with that hash
        self.phash_index: dict[str, MediaFile] = {}  # perceptual hash -> first file
        self._cancel_requested = False

    def cancel(self):
        """Request cancellation of current operation."""
        self._cancel_requested = True

    def _reset_cancel(self):
        self._cancel_requested = False

    def _compute_sha256(self, file_path: Path) -> str:
        """Compute SHA256 hash of a file."""
        hash_sha = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hash_sha.update(chunk)
        return hash_sha.hexdigest()

    def _compute_phash(self, file_path: Path) -> str:
        """Compute perceptual hash of an image."""
        try:
            img = Image.open(file_path)
            return str(imagehash.phash(img))
        except Exception:
            return ""

    def _get_date_taken(self, file_path: Path) -> datetime:
        """Extract date taken from EXIF or fall back to mtime."""
        ext = file_path.suffix.lower()

        if ext in PHOTO_EXTS:
            try:
                img = Image.open(file_path)
                exif = img._getexif()
                if exif:
                    # Try DateTimeOriginal (36867), then DateTimeDigitized (36868)
                    for tag in [36867, 36868]:
                        date_str = exif.get(tag)
                        if date_str:
                            return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
            except Exception:
                pass

        # Fall back to file modification time
        return datetime.fromtimestamp(file_path.stat().st_mtime)

    def scan_folders(
        self,
        folders: list[Path],
        use_phash: bool = True,
        progress_callback: Callable[[int, int, str], None] | None = None
    ) -> ScanResult:
        """
        Scan folders for media files and identify duplicates.

        Args:
            folders: List of folder paths to scan
            use_phash: Whether to use perceptual hashing for near-duplicate detection
            progress_callback: Optional callback(current, total, filename) for progress
        """
        self._reset_cancel()
        self.files = []
        self.hash_index = {}
        self.phash_index = {}
        result = ScanResult()

        # Track all files by hash for grouping
        hash_groups: dict[str, list[MediaFile]] = {}

        # First pass: collect all files
        all_files: list[Path] = []
        for folder in folders:
            folder = Path(folder)
            if not folder.exists():
                result.errors.append(f"Folder not found: {folder}")
                continue

            for file_path in folder.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in MEDIA_EXTS:
                    # Skip temp/hidden files
                    if file_path.name.startswith(".") or file_path.name.endswith(".tmp"):
                        continue
                    all_files.append(file_path)

        result.total_files = len(all_files)

        # Second pass: hash all files and group by hash
        for i, file_path in enumerate(all_files):
            if self._cancel_requested:
                break

            if progress_callback:
                progress_callback(i + 1, result.total_files, file_path.name)

            try:
                stat = file_path.stat()
                media_file = MediaFile(
                    path=file_path,
                    size=stat.st_size,
                )

                result.total_size += stat.st_size

                # Compute SHA256
                media_file.sha256 = self._compute_sha256(file_path)

                # Get date taken for organization
                media_file.date_taken = self._get_date_taken(file_path)

                # Compute perceptual hash for images (optional near-dupe detection)
                if use_phash and file_path.suffix.lower() in PHOTO_EXTS:
                    media_file.phash = self._compute_phash(file_path)
                    if media_file.phash:
                        self.phash_index[media_file.phash] = media_file

                # Add to hash group
                if media_file.sha256 not in hash_groups:
                    hash_groups[media_file.sha256] = []
                hash_groups[media_file.sha256].append(media_file)

                self.files.append(media_file)

            except Exception as e:
                result.errors.append(f"Error processing {file_path}: {e}")

        # Build duplicate groups and unique files list
        for sha256, files in hash_groups.items():
            if len(files) == 1:
                # Only one file with this hash - it's unique
                result.unique_files.append(files[0])
                self.hash_index[sha256] = files[0]
            else:
                # Multiple files with same hash - create a duplicate group
                # Mark all but first as duplicates (for backward compatibility)
                first_file = files[0]
                self.hash_index[sha256] = first_file
                for f in files[1:]:
                    f.is_duplicate = True
                    f.duplicate_of = first_file.path

                group = DuplicateGroup(
                    sha256=sha256,
                    files=files,
                    selected_to_keep=first_file.path
                )
                result.duplicate_groups.append(group)

        return result

    def organize_files(
        self,
        destination: Path,
        duplicates_folder: Path,
        result: ScanResult,
        organize_by_date: bool = True,
        move_files: bool = True,  # False = copy instead
        progress_callback: Callable[[int, int, str], None] | None = None
    ) -> tuple[int, int, list[str]]:
        """
        Organize files into destination folder and move duplicates.

        Returns: (files_organized, duplicates_moved, errors)
        """
        self._reset_cancel()
        errors: list[str] = []
        files_organized = 0
        duplicates_moved = 0

        destination = Path(destination)
        duplicates_folder = Path(duplicates_folder)

        # Create folders
        destination.mkdir(parents=True, exist_ok=True)
        duplicates_folder.mkdir(parents=True, exist_ok=True)

        total = len(result.unique_files) + len(result.duplicates)
        current = 0

        # Move duplicates first
        for media_file in result.duplicates:
            if self._cancel_requested:
                break

            current += 1
            if progress_callback:
                progress_callback(current, total, media_file.path.name)

            try:
                dest_path = duplicates_folder / media_file.path.name
                dest_path = self._get_unique_path(dest_path)

                if move_files:
                    media_file.path.rename(dest_path)
                else:
                    import shutil
                    shutil.copy2(media_file.path, dest_path)

                duplicates_moved += 1
            except Exception as e:
                errors.append(f"Error moving duplicate {media_file.path}: {e}")

        # Organize unique files
        for media_file in result.unique_files:
            if self._cancel_requested:
                break

            current += 1
            if progress_callback:
                progress_callback(current, total, media_file.path.name)

            try:
                if organize_by_date and media_file.date_taken:
                    year = str(media_file.date_taken.year)
                    month = f"{media_file.date_taken.month:02d}"
                    dest_folder = destination / year / month
                else:
                    dest_folder = destination

                dest_folder.mkdir(parents=True, exist_ok=True)
                dest_path = dest_folder / media_file.path.name
                dest_path = self._get_unique_path(dest_path)

                if move_files:
                    media_file.path.rename(dest_path)
                else:
                    import shutil
                    shutil.copy2(media_file.path, dest_path)

                files_organized += 1
            except Exception as e:
                errors.append(f"Error organizing {media_file.path}: {e}")

        return files_organized, duplicates_moved, errors

    def move_duplicates_to_review(
        self,
        result: ScanResult,
        review_folder: Path,
        progress_callback: Callable[[int, int, str], None] | None = None
    ) -> tuple[int, list[str]]:
        """
        Move only the files marked for deletion to review folder (Smart Mode).
        Keeps original files in place. Stores original paths for potential revert.

        Returns: (files_moved, errors)
        """
        self._reset_cancel()
        errors: list[str] = []
        files_moved = 0

        review_folder = Path(review_folder)
        review_folder.mkdir(parents=True, exist_ok=True)

        # Load or create metadata for tracking original paths
        metadata = self._load_review_metadata(review_folder)

        files_to_move = result.get_all_files_to_delete()
        total = len(files_to_move)

        for i, media_file in enumerate(files_to_move):
            if self._cancel_requested:
                break

            if progress_callback:
                progress_callback(i + 1, total, media_file.path.name)

            try:
                dest_path = review_folder / media_file.path.name
                dest_path = self._get_unique_path(dest_path)

                # Store original path before moving
                original_path = str(media_file.path.resolve())
                media_file.path.rename(dest_path)
                media_file.original_path = Path(original_path)

                # Save mapping in metadata
                metadata[dest_path.name] = original_path

                files_moved += 1
            except Exception as e:
                errors.append(f"Error moving {media_file.path}: {e}")

        # Save metadata
        self._save_review_metadata(review_folder, metadata)

        return files_moved, errors

    def _load_review_metadata(self, review_folder: Path) -> dict[str, str]:
        """Load metadata mapping review folder files to original paths."""
        metadata_file = review_folder / ".photosifter_metadata.json"
        if metadata_file.exists():
            try:
                with open(metadata_file, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_review_metadata(self, review_folder: Path, metadata: dict[str, str]):
        """Save metadata mapping review folder files to original paths."""
        metadata_file = review_folder / ".photosifter_metadata.json"
        try:
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)
        except Exception:
            pass

    def revert_file(self, review_folder: Path, filename: str) -> tuple[bool, str]:
        """
        Revert a file from review folder back to its original location.

        Returns: (success, message)
        """
        review_folder = Path(review_folder)
        file_path = review_folder / filename

        if not file_path.exists():
            return False, f"File not found: {filename}"

        metadata = self._load_review_metadata(review_folder)
        original_path_str = metadata.get(filename)

        if not original_path_str:
            return False, f"Original path not found for: {filename}"

        original_path = Path(original_path_str)

        try:
            # Ensure parent directory exists
            original_path.parent.mkdir(parents=True, exist_ok=True)

            # Handle if a file already exists at original location
            dest_path = self._get_unique_path(original_path)

            file_path.rename(dest_path)

            # Remove from metadata
            del metadata[filename]
            self._save_review_metadata(review_folder, metadata)

            return True, f"Reverted to: {dest_path}"
        except Exception as e:
            return False, f"Error reverting {filename}: {e}"

    def delete_from_review(self, review_folder: Path, filename: str, to_trash: bool = True) -> tuple[bool, str]:
        """
        Delete a file from the review folder.

        Args:
            review_folder: Path to review folder
            filename: Name of file to delete
            to_trash: If True, send to system trash. If False, permanently delete.

        Returns: (success, message)
        """
        review_folder = Path(review_folder)
        file_path = review_folder / filename

        if not file_path.exists():
            return False, f"File not found: {filename}"

        try:
            if to_trash:
                try:
                    from send2trash import send2trash
                    send2trash(str(file_path))
                except ImportError:
                    # Fallback to permanent delete if send2trash not available
                    file_path.unlink()
            else:
                file_path.unlink()

            # Remove from metadata
            metadata = self._load_review_metadata(review_folder)
            if filename in metadata:
                del metadata[filename]
                self._save_review_metadata(review_folder, metadata)

            return True, f"Deleted: {filename}"
        except Exception as e:
            return False, f"Error deleting {filename}: {e}"

    def get_review_folder_files(self, review_folder: Path) -> list[tuple[str, str, int]]:
        """
        Get list of files in review folder with their original paths.

        Returns: List of (filename, original_path, size)
        """
        review_folder = Path(review_folder)
        if not review_folder.exists():
            return []

        metadata = self._load_review_metadata(review_folder)
        files = []

        for file_path in review_folder.iterdir():
            if file_path.is_file() and not file_path.name.startswith("."):
                original_path = metadata.get(file_path.name, "Unknown")
                try:
                    size = file_path.stat().st_size
                except Exception:
                    size = 0
                files.append((file_path.name, original_path, size))

        return sorted(files, key=lambda x: x[0])

    def _get_unique_path(self, path: Path) -> Path:
        """Get a unique file path by appending a counter if needed."""
        if not path.exists():
            return path

        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        counter = 1

        while path.exists():
            path = parent / f"{stem}_{counter}{suffix}"
            counter += 1

        return path


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"
