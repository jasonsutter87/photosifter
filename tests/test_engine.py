"""Tests for PhotoSifter engine - source folder selection."""

import pytest
from pathlib import Path
import tempfile
import shutil
from PIL import Image

from photosift.engine import PhotoSifterEngine, ScanResult, DuplicateGroup, MediaFile


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
        """Unique files list should not include any files that have duplicates."""
        folder = temp_photos["folder1"]

        # Create a duplicate
        original = folder / "photo_0.jpg"
        duplicate = folder / "photo_0_copy.jpg"
        shutil.copy(original, duplicate)

        result = engine.scan_folders([folder])

        # 3 original + 1 copy = 4 total
        # photo_0 and photo_0_copy form a duplicate group
        # photo_1 and photo_2 are truly unique
        assert result.total_files == 4
        assert len(result.unique_files) == 2  # Only files with no duplicates
        assert result.duplicate_count == 1  # 1 file will be deleted from the group
        assert result.duplicate_group_count == 1  # 1 group of duplicates

    def test_duplicate_groups_contain_all_copies(self, engine, temp_photos):
        """Duplicate groups should contain all copies including the 'original'."""
        folder = temp_photos["folder1"]

        # Create a duplicate
        original = folder / "photo_0.jpg"
        duplicate = folder / "photo_0_copy.jpg"
        shutil.copy(original, duplicate)

        result = engine.scan_folders([folder])

        # Should have one duplicate group with 2 files
        assert len(result.duplicate_groups) == 1
        group = result.duplicate_groups[0]
        assert len(group.files) == 2

        # First file in the group should be selected to keep by default
        assert group.selected_to_keep is not None

    def test_can_select_different_file_to_keep(self, engine, temp_photos):
        """User should be able to select which file to keep in a duplicate group."""
        folder = temp_photos["folder1"]

        # Create a duplicate
        original = folder / "photo_0.jpg"
        duplicate = folder / "photo_0_copy.jpg"
        shutil.copy(original, duplicate)

        result = engine.scan_folders([folder])

        group = result.duplicate_groups[0]
        original_selection = group.selected_to_keep

        # Change selection to the other file
        other_file = [f for f in group.files if f.path != original_selection][0]
        group.selected_to_keep = other_file.path

        # Now files_to_delete should be the originally selected file
        assert len(group.files_to_delete) == 1
        assert group.files_to_delete[0].path == original_selection


class TestDuplicateGroupDataclass:
    """Tests for the DuplicateGroup dataclass."""

    def test_duplicate_group_creation(self):
        """Should create a DuplicateGroup with files."""
        file1 = MediaFile(path=Path("/test/photo1.jpg"), size=1000, sha256="abc123")
        file2 = MediaFile(path=Path("/test/photo2.jpg"), size=1000, sha256="abc123")

        group = DuplicateGroup(sha256="abc123", files=[file1, file2])

        assert group.sha256 == "abc123"
        assert len(group.files) == 2

    def test_duplicate_group_default_selection(self):
        """First file should be selected to keep by default."""
        file1 = MediaFile(path=Path("/test/photo1.jpg"), size=1000, sha256="abc123")
        file2 = MediaFile(path=Path("/test/photo2.jpg"), size=1000, sha256="abc123")

        group = DuplicateGroup(sha256="abc123", files=[file1, file2])

        assert group.selected_to_keep == file1.path

    def test_duplicate_group_files_to_delete(self):
        """files_to_delete should return all files except the selected one."""
        file1 = MediaFile(path=Path("/test/photo1.jpg"), size=1000, sha256="abc123")
        file2 = MediaFile(path=Path("/test/photo2.jpg"), size=1000, sha256="abc123")
        file3 = MediaFile(path=Path("/test/photo3.jpg"), size=1000, sha256="abc123")

        group = DuplicateGroup(sha256="abc123", files=[file1, file2, file3])

        assert len(group.files_to_delete) == 2
        paths = [f.path for f in group.files_to_delete]
        assert file1.path not in paths  # First file is kept
        assert file2.path in paths
        assert file3.path in paths

    def test_duplicate_group_file_to_keep(self):
        """file_to_keep should return the MediaFile object for the selected file."""
        file1 = MediaFile(path=Path("/test/photo1.jpg"), size=1000, sha256="abc123")
        file2 = MediaFile(path=Path("/test/photo2.jpg"), size=1000, sha256="abc123")

        group = DuplicateGroup(sha256="abc123", files=[file1, file2])

        assert group.file_to_keep == file1

    def test_duplicate_group_space_recoverable(self):
        """space_recoverable should sum sizes of files to delete."""
        file1 = MediaFile(path=Path("/test/photo1.jpg"), size=1000, sha256="abc123")
        file2 = MediaFile(path=Path("/test/photo2.jpg"), size=2000, sha256="abc123")
        file3 = MediaFile(path=Path("/test/photo3.jpg"), size=3000, sha256="abc123")

        group = DuplicateGroup(sha256="abc123", files=[file1, file2, file3])

        # file1 is kept, so recoverable = file2.size + file3.size
        assert group.space_recoverable == 5000

    def test_duplicate_group_change_selection(self):
        """Changing selected_to_keep should update files_to_delete."""
        file1 = MediaFile(path=Path("/test/photo1.jpg"), size=1000, sha256="abc123")
        file2 = MediaFile(path=Path("/test/photo2.jpg"), size=2000, sha256="abc123")

        group = DuplicateGroup(sha256="abc123", files=[file1, file2])

        # Initially file1 is kept
        assert group.selected_to_keep == file1.path
        assert len(group.files_to_delete) == 1
        assert group.files_to_delete[0].path == file2.path

        # Change to keep file2
        group.selected_to_keep = file2.path

        assert len(group.files_to_delete) == 1
        assert group.files_to_delete[0].path == file1.path

    def test_duplicate_group_space_changes_with_selection(self):
        """space_recoverable should change when selection changes."""
        file1 = MediaFile(path=Path("/test/photo1.jpg"), size=1000, sha256="abc123")
        file2 = MediaFile(path=Path("/test/photo2.jpg"), size=5000, sha256="abc123")

        group = DuplicateGroup(sha256="abc123", files=[file1, file2])

        # Keep file1 (small) -> recoverable is file2 (large)
        assert group.space_recoverable == 5000

        # Keep file2 (large) -> recoverable is file1 (small)
        group.selected_to_keep = file2.path
        assert group.space_recoverable == 1000

    def test_duplicate_group_empty_files_list(self):
        """Should handle empty files list gracefully."""
        group = DuplicateGroup(sha256="abc123", files=[])

        assert group.selected_to_keep is None
        assert group.file_to_keep is None
        assert len(group.files_to_delete) == 0
        assert group.space_recoverable == 0


class TestScanResultDuplicateGroups:
    """Tests for ScanResult with duplicate_groups."""

    def test_scan_result_duplicate_group_count(self, engine, temp_photos):
        """duplicate_group_count should return number of groups."""
        folder = temp_photos["folder1"]

        # Create two different duplicate pairs
        shutil.copy(folder / "photo_0.jpg", folder / "photo_0_copy.jpg")
        shutil.copy(folder / "photo_1.jpg", folder / "photo_1_copy.jpg")

        result = engine.scan_folders([folder])

        assert result.duplicate_group_count == 2

    def test_scan_result_duplicate_count(self, engine, temp_photos):
        """duplicate_count should return total files to delete across all groups."""
        folder = temp_photos["folder1"]

        # Create a file with 3 copies (1 original + 2 copies = 3 total, 2 to delete)
        shutil.copy(folder / "photo_0.jpg", folder / "photo_0_copy1.jpg")
        shutil.copy(folder / "photo_0.jpg", folder / "photo_0_copy2.jpg")

        result = engine.scan_folders([folder])

        assert result.duplicate_group_count == 1
        assert result.duplicate_count == 2  # 2 files will be deleted

    def test_scan_result_space_recoverable(self, engine, temp_photos):
        """space_recoverable should sum space from all groups."""
        folder = temp_photos["folder1"]

        shutil.copy(folder / "photo_0.jpg", folder / "photo_0_copy.jpg")
        shutil.copy(folder / "photo_1.jpg", folder / "photo_1_copy.jpg")

        result = engine.scan_folders([folder])

        # Each duplicate group has 1 file to delete
        # Space should be sum of those file sizes
        expected_space = sum(g.space_recoverable for g in result.duplicate_groups)
        assert result.space_recoverable == expected_space
        assert result.space_recoverable > 0

    def test_scan_result_get_all_files_to_delete(self, engine, temp_photos):
        """get_all_files_to_delete should return flat list of files."""
        folder = temp_photos["folder1"]

        shutil.copy(folder / "photo_0.jpg", folder / "photo_0_copy.jpg")
        shutil.copy(folder / "photo_1.jpg", folder / "photo_1_copy.jpg")

        result = engine.scan_folders([folder])

        files_to_delete = result.get_all_files_to_delete()

        assert len(files_to_delete) == 2
        assert all(isinstance(f, MediaFile) for f in files_to_delete)

    def test_scan_result_duplicates_backward_compat(self, engine, temp_photos):
        """duplicates property should work for backward compatibility."""
        folder = temp_photos["folder1"]

        shutil.copy(folder / "photo_0.jpg", folder / "photo_0_copy.jpg")

        result = engine.scan_folders([folder])

        # Old-style access should still work
        assert len(result.duplicates) == result.duplicate_count

    def test_scan_result_no_duplicates(self, engine, temp_photos):
        """Should handle case with no duplicates."""
        result = engine.scan_folders([temp_photos["folder1"]])

        assert result.duplicate_group_count == 0
        assert result.duplicate_count == 0
        assert result.space_recoverable == 0
        assert len(result.get_all_files_to_delete()) == 0


class TestMoveToReview:
    """Tests for move_duplicates_to_review functionality."""

    def test_move_creates_review_folder(self, engine, temp_photos):
        """Should create review folder if it doesn't exist."""
        folder = temp_photos["folder1"]
        review_folder = temp_photos["base"] / "review"

        shutil.copy(folder / "photo_0.jpg", folder / "photo_0_copy.jpg")
        result = engine.scan_folders([folder])

        assert not review_folder.exists()

        engine.move_duplicates_to_review(result, review_folder)

        assert review_folder.exists()

    def test_move_only_files_to_delete(self, engine, temp_photos):
        """Should only move files marked for deletion, not the kept file."""
        folder = temp_photos["folder1"]
        review_folder = temp_photos["base"] / "review"

        original = folder / "photo_0.jpg"
        duplicate = folder / "photo_0_copy.jpg"
        shutil.copy(original, duplicate)

        result = engine.scan_folders([folder])
        files_moved, errors = engine.move_duplicates_to_review(result, review_folder)

        assert files_moved == 1
        assert len(errors) == 0
        assert original.exists()  # Original kept in place
        assert not duplicate.exists()  # Duplicate moved

    def test_move_returns_count(self, engine, temp_photos):
        """Should return count of moved files."""
        folder = temp_photos["folder1"]
        review_folder = temp_photos["base"] / "review"

        shutil.copy(folder / "photo_0.jpg", folder / "photo_0_copy1.jpg")
        shutil.copy(folder / "photo_0.jpg", folder / "photo_0_copy2.jpg")

        result = engine.scan_folders([folder])
        files_moved, errors = engine.move_duplicates_to_review(result, review_folder)

        assert files_moved == 2

    def test_move_stores_original_path_metadata(self, engine, temp_photos):
        """Should store original path in metadata file."""
        folder = temp_photos["folder1"]
        review_folder = temp_photos["base"] / "review"

        duplicate = folder / "photo_0_copy.jpg"
        shutil.copy(folder / "photo_0.jpg", duplicate)
        original_path = str(duplicate.resolve())

        result = engine.scan_folders([folder])
        engine.move_duplicates_to_review(result, review_folder)

        metadata = engine._load_review_metadata(review_folder)
        assert len(metadata) == 1
        assert original_path in metadata.values()

    def test_move_handles_filename_conflict(self, engine, temp_photos):
        """Should handle case where file with same name exists in review folder."""
        folder = temp_photos["folder1"]
        review_folder = temp_photos["base"] / "review"
        review_folder.mkdir()

        # Create a file in review folder with same name
        duplicate = folder / "photo_0_copy.jpg"
        shutil.copy(folder / "photo_0.jpg", duplicate)
        existing = review_folder / "photo_0_copy.jpg"
        shutil.copy(folder / "photo_1.jpg", existing)

        result = engine.scan_folders([folder])
        files_moved, errors = engine.move_duplicates_to_review(result, review_folder)

        assert files_moved == 1
        # Should have created photo_0_copy_1.jpg or similar
        files_in_review = list(review_folder.glob("photo_0_copy*.jpg"))
        assert len(files_in_review) == 2

    def test_move_progress_callback(self, engine, temp_photos):
        """Should call progress callback during move."""
        folder = temp_photos["folder1"]
        review_folder = temp_photos["base"] / "review"

        shutil.copy(folder / "photo_0.jpg", folder / "photo_0_copy.jpg")

        result = engine.scan_folders([folder])

        progress_calls = []

        def callback(current, total, filename):
            progress_calls.append((current, total, filename))

        engine.move_duplicates_to_review(result, review_folder, progress_callback=callback)

        assert len(progress_calls) == 1
        assert progress_calls[0][0] == 1
        assert progress_calls[0][1] == 1

    def test_move_respects_user_selection(self, engine, temp_photos):
        """Should respect which file user selected to keep."""
        folder = temp_photos["folder1"]
        review_folder = temp_photos["base"] / "review"

        original = folder / "photo_0.jpg"
        duplicate = folder / "photo_0_copy.jpg"
        shutil.copy(original, duplicate)

        result = engine.scan_folders([folder])

        # Change selection to keep the copy instead
        group = result.duplicate_groups[0]
        group.selected_to_keep = duplicate

        engine.move_duplicates_to_review(result, review_folder)

        assert not original.exists()  # Original was moved (now marked for deletion)
        assert duplicate.exists()  # Copy was kept


class TestRevertFile:
    """Tests for revert_file functionality."""

    def test_revert_moves_file_back(self, engine, temp_photos):
        """Should move file back to original location."""
        folder = temp_photos["folder1"]
        review_folder = temp_photos["base"] / "review"

        duplicate = folder / "photo_0_copy.jpg"
        shutil.copy(folder / "photo_0.jpg", duplicate)

        result = engine.scan_folders([folder])
        engine.move_duplicates_to_review(result, review_folder)

        # File should be in review folder
        assert not duplicate.exists()
        review_file = list(review_folder.glob("photo_0_copy*.jpg"))[0]

        success, message = engine.revert_file(review_folder, review_file.name)

        assert success
        assert duplicate.exists()  # File is back
        assert not review_file.exists()  # Removed from review

    def test_revert_updates_metadata(self, engine, temp_photos):
        """Should remove entry from metadata after revert."""
        folder = temp_photos["folder1"]
        review_folder = temp_photos["base"] / "review"

        duplicate = folder / "photo_0_copy.jpg"
        shutil.copy(folder / "photo_0.jpg", duplicate)

        result = engine.scan_folders([folder])
        engine.move_duplicates_to_review(result, review_folder)

        review_file = list(review_folder.glob("photo_0_copy*.jpg"))[0]

        # Metadata should have entry
        metadata = engine._load_review_metadata(review_folder)
        assert review_file.name in metadata

        engine.revert_file(review_folder, review_file.name)

        # Metadata should be updated
        metadata = engine._load_review_metadata(review_folder)
        assert review_file.name not in metadata

    def test_revert_creates_parent_directory(self, engine, temp_photos):
        """Should create parent directory if it was deleted."""
        folder = temp_photos["folder1"]
        review_folder = temp_photos["base"] / "review"
        subfolder = folder / "subfolder"
        subfolder.mkdir()

        # Create duplicate in subfolder
        duplicate = subfolder / "photo_copy.jpg"
        shutil.copy(folder / "photo_0.jpg", duplicate)

        result = engine.scan_folders([folder])
        engine.move_duplicates_to_review(result, review_folder)

        # Delete the subfolder
        subfolder.rmdir()
        assert not subfolder.exists()

        review_file = list(review_folder.glob("photo_copy*.jpg"))[0]
        success, message = engine.revert_file(review_folder, review_file.name)

        assert success
        assert subfolder.exists()  # Parent recreated
        assert duplicate.exists()

    def test_revert_handles_filename_conflict(self, engine, temp_photos):
        """Should handle case where file already exists at original location."""
        folder = temp_photos["folder1"]
        review_folder = temp_photos["base"] / "review"

        duplicate = folder / "photo_0_copy.jpg"
        shutil.copy(folder / "photo_0.jpg", duplicate)

        result = engine.scan_folders([folder])
        engine.move_duplicates_to_review(result, review_folder)

        # Create a new file at original location
        shutil.copy(folder / "photo_1.jpg", duplicate)
        assert duplicate.exists()

        review_file = list(review_folder.glob("photo_0_copy*.jpg"))[0]
        success, message = engine.revert_file(review_folder, review_file.name)

        assert success
        # Should have created photo_0_copy_1.jpg or similar
        copies = list(folder.glob("photo_0_copy*.jpg"))
        assert len(copies) == 2

    def test_revert_file_not_found(self, engine, temp_photos):
        """Should return error if file doesn't exist."""
        review_folder = temp_photos["base"] / "review"
        review_folder.mkdir()

        success, message = engine.revert_file(review_folder, "nonexistent.jpg")

        assert not success
        assert "not found" in message.lower()

    def test_revert_no_metadata(self, engine, temp_photos):
        """Should return error if no metadata for file."""
        review_folder = temp_photos["base"] / "review"
        review_folder.mkdir()

        # Create file without metadata
        test_file = review_folder / "orphan.jpg"
        shutil.copy(temp_photos["folder1"] / "photo_0.jpg", test_file)

        success, message = engine.revert_file(review_folder, "orphan.jpg")

        assert not success
        assert "not found" in message.lower()


class TestDeleteFromReview:
    """Tests for delete_from_review functionality."""

    def test_delete_removes_file(self, engine, temp_photos):
        """Should delete file from review folder."""
        folder = temp_photos["folder1"]
        review_folder = temp_photos["base"] / "review"

        duplicate = folder / "photo_0_copy.jpg"
        shutil.copy(folder / "photo_0.jpg", duplicate)

        result = engine.scan_folders([folder])
        engine.move_duplicates_to_review(result, review_folder)

        review_file = list(review_folder.glob("photo_0_copy*.jpg"))[0]

        success, message = engine.delete_from_review(review_folder, review_file.name, to_trash=False)

        assert success
        assert not review_file.exists()

    def test_delete_updates_metadata(self, engine, temp_photos):
        """Should remove entry from metadata after delete."""
        folder = temp_photos["folder1"]
        review_folder = temp_photos["base"] / "review"

        duplicate = folder / "photo_0_copy.jpg"
        shutil.copy(folder / "photo_0.jpg", duplicate)

        result = engine.scan_folders([folder])
        engine.move_duplicates_to_review(result, review_folder)

        review_file = list(review_folder.glob("photo_0_copy*.jpg"))[0]

        engine.delete_from_review(review_folder, review_file.name, to_trash=False)

        metadata = engine._load_review_metadata(review_folder)
        assert review_file.name not in metadata

    def test_delete_file_not_found(self, engine, temp_photos):
        """Should return error if file doesn't exist."""
        review_folder = temp_photos["base"] / "review"
        review_folder.mkdir()

        success, message = engine.delete_from_review(review_folder, "nonexistent.jpg")

        assert not success
        assert "not found" in message.lower()


class TestGetReviewFolderFiles:
    """Tests for get_review_folder_files functionality."""

    def test_returns_files_with_original_paths(self, engine, temp_photos):
        """Should return list of files with their original paths."""
        folder = temp_photos["folder1"]
        review_folder = temp_photos["base"] / "review"

        duplicate = folder / "photo_0_copy.jpg"
        shutil.copy(folder / "photo_0.jpg", duplicate)

        result = engine.scan_folders([folder])
        engine.move_duplicates_to_review(result, review_folder)

        files = engine.get_review_folder_files(review_folder)

        assert len(files) == 1
        filename, original_path, size = files[0]
        assert "photo_0_copy" in filename
        assert str(folder) in original_path
        assert size > 0

    def test_handles_missing_folder(self, engine, temp_photos):
        """Should return empty list if folder doesn't exist."""
        nonexistent = temp_photos["base"] / "nonexistent"

        files = engine.get_review_folder_files(nonexistent)

        assert files == []

    def test_handles_empty_folder(self, engine, temp_photos):
        """Should return empty list if folder is empty."""
        review_folder = temp_photos["base"] / "review"
        review_folder.mkdir()

        files = engine.get_review_folder_files(review_folder)

        assert files == []

    def test_excludes_hidden_files(self, engine, temp_photos):
        """Should not include hidden files like metadata."""
        folder = temp_photos["folder1"]
        review_folder = temp_photos["base"] / "review"

        duplicate = folder / "photo_0_copy.jpg"
        shutil.copy(folder / "photo_0.jpg", duplicate)

        result = engine.scan_folders([folder])
        engine.move_duplicates_to_review(result, review_folder)

        files = engine.get_review_folder_files(review_folder)

        # Should not include .photosifter_metadata.json
        filenames = [f[0] for f in files]
        assert not any(f.startswith(".") for f in filenames)

    def test_returns_unknown_for_orphan_files(self, engine, temp_photos):
        """Should return 'Unknown' for files without metadata."""
        review_folder = temp_photos["base"] / "review"
        review_folder.mkdir()

        orphan = review_folder / "orphan.jpg"
        shutil.copy(temp_photos["folder1"] / "photo_0.jpg", orphan)

        files = engine.get_review_folder_files(review_folder)

        assert len(files) == 1
        filename, original_path, size = files[0]
        assert filename == "orphan.jpg"
        assert original_path == "Unknown"


class TestMetadataHandling:
    """Tests for metadata persistence."""

    def test_metadata_persists_across_engine_instances(self, temp_photos):
        """Metadata should persist when using different engine instances."""
        folder = temp_photos["folder1"]
        review_folder = temp_photos["base"] / "review"

        duplicate = folder / "photo_0_copy.jpg"
        shutil.copy(folder / "photo_0.jpg", duplicate)
        original_path = str(duplicate.resolve())

        # First engine: move files
        engine1 = PhotoSifterEngine()
        result = engine1.scan_folders([folder])
        engine1.move_duplicates_to_review(result, review_folder)

        # Second engine: should be able to revert
        engine2 = PhotoSifterEngine()
        review_file = list(review_folder.glob("photo_0_copy*.jpg"))[0]
        success, _ = engine2.revert_file(review_folder, review_file.name)

        assert success
        assert duplicate.exists()

    def test_metadata_handles_multiple_files(self, engine, temp_photos):
        """Metadata should track multiple files correctly."""
        folder = temp_photos["folder1"]
        review_folder = temp_photos["base"] / "review"

        # Create multiple duplicates
        shutil.copy(folder / "photo_0.jpg", folder / "photo_0_copy.jpg")
        shutil.copy(folder / "photo_1.jpg", folder / "photo_1_copy.jpg")
        shutil.copy(folder / "photo_2.jpg", folder / "photo_2_copy.jpg")

        result = engine.scan_folders([folder])
        engine.move_duplicates_to_review(result, review_folder)

        metadata = engine._load_review_metadata(review_folder)

        assert len(metadata) == 3

    def test_metadata_survives_partial_operations(self, engine, temp_photos):
        """Metadata should remain consistent after partial reverts."""
        folder = temp_photos["folder1"]
        review_folder = temp_photos["base"] / "review"

        shutil.copy(folder / "photo_0.jpg", folder / "photo_0_copy.jpg")
        shutil.copy(folder / "photo_1.jpg", folder / "photo_1_copy.jpg")

        result = engine.scan_folders([folder])
        engine.move_duplicates_to_review(result, review_folder)

        # Revert only one file
        files = list(review_folder.glob("*.jpg"))
        engine.revert_file(review_folder, files[0].name)

        metadata = engine._load_review_metadata(review_folder)

        assert len(metadata) == 1
        assert files[0].name not in metadata


class TestSmartModeIntegration:
    """Integration tests for Smart Mode workflow."""

    def test_full_smart_mode_workflow(self, engine, temp_photos):
        """Test complete Smart Mode: scan -> select -> move -> revert."""
        folder = temp_photos["folder1"]
        review_folder = temp_photos["base"] / "review"

        # Setup: create duplicates
        original = folder / "photo_0.jpg"
        duplicate = folder / "photo_0_copy.jpg"
        shutil.copy(original, duplicate)

        # Step 1: Scan
        result = engine.scan_folders([folder])
        assert result.duplicate_group_count == 1

        # Step 2: User changes selection (keep copy, delete original)
        group = result.duplicate_groups[0]
        group.selected_to_keep = duplicate

        # Step 3: Move to review
        files_moved, errors = engine.move_duplicates_to_review(result, review_folder)
        assert files_moved == 1
        assert len(errors) == 0
        assert duplicate.exists()  # Copy kept
        assert not original.exists()  # Original moved to review

        # Step 4: Revert (user changes mind)
        review_file = list(review_folder.glob("*.jpg"))[0]
        success, _ = engine.revert_file(review_folder, review_file.name)
        assert success
        assert original.exists()  # Original is back

    def test_smart_mode_preserves_folder_structure(self, engine, temp_photos):
        """Smart Mode should keep files in their original locations."""
        folder = temp_photos["folder1"]
        review_folder = temp_photos["base"] / "review"

        # Create subfolder structure
        subfolder = folder / "vacation" / "2024"
        subfolder.mkdir(parents=True)
        original = subfolder / "beach.jpg"
        shutil.copy(folder / "photo_0.jpg", original)

        # Create duplicate at root
        duplicate = folder / "beach_copy.jpg"
        shutil.copy(original, duplicate)

        result = engine.scan_folders([folder])

        # Keep the one in subfolder
        group = result.duplicate_groups[0]
        for f in group.files:
            if "vacation" in str(f.path):
                group.selected_to_keep = f.path
                break

        engine.move_duplicates_to_review(result, review_folder)

        # Original in subfolder should still be there
        assert original.exists()
        # Duplicate at root should be moved
        assert not duplicate.exists()

    def test_smart_mode_with_multiple_groups(self, engine, temp_photos):
        """Should handle multiple duplicate groups correctly."""
        folder = temp_photos["folder1"]
        review_folder = temp_photos["base"] / "review"

        # Create two independent duplicate pairs
        shutil.copy(folder / "photo_0.jpg", folder / "photo_0_copy.jpg")
        shutil.copy(folder / "photo_1.jpg", folder / "photo_1_copy.jpg")

        result = engine.scan_folders([folder])
        assert result.duplicate_group_count == 2

        files_moved, errors = engine.move_duplicates_to_review(result, review_folder)

        assert files_moved == 2
        assert len(list(review_folder.glob("*.jpg"))) == 2

    def test_smart_mode_keeps_unrelated_files(self, engine, temp_photos):
        """Unique files should remain untouched."""
        folder = temp_photos["folder1"]
        review_folder = temp_photos["base"] / "review"

        # Only create one duplicate pair
        shutil.copy(folder / "photo_0.jpg", folder / "photo_0_copy.jpg")

        result = engine.scan_folders([folder])
        engine.move_duplicates_to_review(result, review_folder)

        # Unique files should still exist
        assert (folder / "photo_0.jpg").exists()  # Original kept
        assert (folder / "photo_1.jpg").exists()  # Unrelated
        assert (folder / "photo_2.jpg").exists()  # Unrelated
