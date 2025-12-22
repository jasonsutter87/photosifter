"""Tests for PhotoSifter engine - source folder selection."""

import pytest
from pathlib import Path
import tempfile
import shutil
from PIL import Image

from photosift.engine import PhotoSifterEngine, ScanResult


@pytest.fixture
def engine():
    """Create a fresh engine for each test."""
    return PhotoSifterEngine()


@pytest.fixture
def temp_photos():
    """Create temporary directories with test photos."""
    base = Path(tempfile.mkdtemp())

    # Create two source folders
    folder1 = base / "photos1"
    folder2 = base / "photos2"
    folder1.mkdir()
    folder2.mkdir()

    # Create test images in folder1 (red-ish tones)
    for i in range(3):
        img = Image.new('RGB', (100, 100), color=(100 + i * 50, 0, 0))
        img.save(folder1 / f"photo_{i}.jpg")

    # Create test images in folder2 (blue-ish tones, distinct from folder1)
    for i in range(2):
        img = Image.new('RGB', (100, 100), color=(0, 0, 100 + i * 80))
        img.save(folder2 / f"image_{i}.jpg")

    yield {
        "base": base,
        "folder1": folder1,
        "folder2": folder2,
    }

    # Cleanup
    shutil.rmtree(base)


class TestSingleSourceFolder:
    """Tests for scanning a single source folder."""

    def test_scan_single_folder_returns_result(self, engine, temp_photos):
        """Scanning a single folder should return a ScanResult."""
        result = engine.scan_folders([temp_photos["folder1"]])

        assert isinstance(result, ScanResult)

    def test_scan_single_folder_finds_all_photos(self, engine, temp_photos):
        """Scanning a single folder should find all photos in it."""
        result = engine.scan_folders([temp_photos["folder1"]])

        assert result.total_files == 3

    def test_scan_single_folder_with_path_object(self, engine, temp_photos):
        """Should accept Path objects."""
        result = engine.scan_folders([temp_photos["folder1"]])

        assert result.total_files == 3

    def test_scan_single_folder_with_string_path(self, engine, temp_photos):
        """Should accept string paths."""
        result = engine.scan_folders([str(temp_photos["folder1"])])

        assert result.total_files == 3

    def test_scan_empty_folder_returns_zero(self, engine, temp_photos):
        """Scanning an empty folder should return 0 files."""
        empty_folder = temp_photos["base"] / "empty"
        empty_folder.mkdir()

        result = engine.scan_folders([empty_folder])

        assert result.total_files == 0

    def test_scan_nonexistent_folder_adds_error(self, engine, temp_photos):
        """Scanning a non-existent folder should add an error."""
        fake_folder = temp_photos["base"] / "does_not_exist"

        result = engine.scan_folders([fake_folder])

        assert len(result.errors) == 1
        assert "not found" in result.errors[0].lower()


class TestMultipleSourceFolders:
    """Tests for scanning multiple source folders."""

    def test_scan_multiple_folders_finds_all_photos(self, engine, temp_photos):
        """Scanning multiple folders should find photos from all of them."""
        result = engine.scan_folders([
            temp_photos["folder1"],
            temp_photos["folder2"]
        ])

        # folder1 has 3, folder2 has 2
        assert result.total_files == 5

    def test_scan_multiple_folders_returns_single_result(self, engine, temp_photos):
        """Multiple folders should return a single combined ScanResult."""
        result = engine.scan_folders([
            temp_photos["folder1"],
            temp_photos["folder2"]
        ])

        assert isinstance(result, ScanResult)

    def test_scan_multiple_folders_with_mixed_paths(self, engine, temp_photos):
        """Should handle mix of Path objects and strings."""
        result = engine.scan_folders([
            temp_photos["folder1"],  # Path object
            str(temp_photos["folder2"])  # string
        ])

        assert result.total_files == 5

    def test_scan_empty_list_returns_empty_result(self, engine):
        """Scanning with empty folder list should return empty result."""
        result = engine.scan_folders([])

        assert result.total_files == 0
        assert len(result.unique_files) == 0

    def test_scan_multiple_folders_one_missing(self, engine, temp_photos):
        """Should continue scanning valid folders if one is missing."""
        fake_folder = temp_photos["base"] / "missing"

        result = engine.scan_folders([
            temp_photos["folder1"],
            fake_folder,
            temp_photos["folder2"]
        ])

        # Should still find files from valid folders
        assert result.total_files == 5
        # Should record the error
        assert len(result.errors) == 1


class TestDuplicateDetection:
    """Tests for duplicate detection across source folders."""

    def test_detects_duplicate_in_same_folder(self, engine, temp_photos):
        """Should detect duplicates within a single folder."""
        folder = temp_photos["folder1"]

        # Copy a file to create a duplicate
        original = folder / "photo_0.jpg"
        duplicate = folder / "photo_0_copy.jpg"
        shutil.copy(original, duplicate)

        result = engine.scan_folders([folder])

        assert result.duplicate_count == 1

    def test_detects_duplicate_across_folders(self, engine, temp_photos):
        """Should detect duplicates across different source folders."""
        # Copy a file from folder1 to folder2
        original = temp_photos["folder1"] / "photo_0.jpg"
        duplicate = temp_photos["folder2"] / "photo_0_dupe.jpg"
        shutil.copy(original, duplicate)

        result = engine.scan_folders([
            temp_photos["folder1"],
            temp_photos["folder2"]
        ])

        assert result.duplicate_count == 1

    def test_unique_files_excludes_duplicates(self, engine, temp_photos):
        """Unique files list should not include duplicates."""
        folder = temp_photos["folder1"]

        # Create a duplicate
        original = folder / "photo_0.jpg"
        duplicate = folder / "photo_0_copy.jpg"
        shutil.copy(original, duplicate)

        result = engine.scan_folders([folder])

        # 3 original + 1 copy = 4 total, but only 3 unique
        assert result.total_files == 4
        assert len(result.unique_files) == 3
        assert result.duplicate_count == 1
