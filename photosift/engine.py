"""Core engine for photo deduplication and organization."""

import os
import hashlib
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable
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


@dataclass
class ScanResult:
    """Results from scanning folders."""
    total_files: int = 0
    total_size: int = 0
    duplicates: list[MediaFile] = field(default_factory=list)
    unique_files: list[MediaFile] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def duplicate_count(self) -> int:
        return len(self.duplicates)

    @property
    def space_recoverable(self) -> int:
        return sum(f.size for f in self.duplicates)


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

        # Second pass: hash and identify duplicates
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

                # Check for exact duplicate
                if media_file.sha256 in self.hash_index:
                    media_file.is_duplicate = True
                    media_file.duplicate_of = self.hash_index[media_file.sha256].path
                    result.duplicates.append(media_file)
                    self.files.append(media_file)
                    continue

                self.hash_index[media_file.sha256] = media_file

                # Compute perceptual hash for images (optional near-dupe detection)
                if use_phash and file_path.suffix.lower() in PHOTO_EXTS:
                    media_file.phash = self._compute_phash(file_path)

                    if media_file.phash and media_file.phash in self.phash_index:
                        # Found a perceptual duplicate (not exact, but visually similar)
                        # For now, we only flag exact duplicates
                        # Could add near-dupe detection as a premium feature
                        pass
                    elif media_file.phash:
                        self.phash_index[media_file.phash] = media_file

                # Get date taken for organization
                media_file.date_taken = self._get_date_taken(file_path)

                result.unique_files.append(media_file)
                self.files.append(media_file)

            except Exception as e:
                result.errors.append(f"Error processing {file_path}: {e}")

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
