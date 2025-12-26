# How to Release a New Version of PhotoSifter

This guide is for publishing updates that users will be notified about automatically.

## Steps to Release

### 1. Update the Version Number

Edit `photosift/__init__.py` and bump the version:

```python
__version__ = "0.2.0"  # Change from "0.1.0" to your new version
```

Use [semantic versioning](https://semver.org/):
- **MAJOR** (1.0.0): Breaking changes
- **MINOR** (0.2.0): New features, backwards compatible
- **PATCH** (0.1.1): Bug fixes

### 2. Build the App

**macOS:**
```bash
source venv/bin/activate
pip install pyinstaller
pyinstaller photosift.spec
```

The built app will be in `dist/PhotoSifter`.

To create a `.dmg` (optional):
```bash
# Install create-dmg: brew install create-dmg
create-dmg \
  --volname "PhotoSifter" \
  --window-size 600 400 \
  --icon "PhotoSifter.app" 150 150 \
  --app-drop-link 450 150 \
  "PhotoSifter-0.2.0.dmg" \
  "dist/PhotoSifter.app"
```

**Windows:**
```bash
venv\Scripts\activate
pip install pyinstaller
pyinstaller photosift.spec
```

The built `.exe` will be in `dist/PhotoSifter.exe`.

### 3. Create a GitHub Release

1. Go to https://github.com/jasonsutter87/photosifter/releases
2. Click **"Draft a new release"**
3. Create a new tag: `v0.2.0` (must start with `v`)
4. Set the release title: `v0.2.0` or `v0.2.0 - Feature Name`
5. Write release notes describing what changed
6. Attach your built files:
   - `PhotoSifter-0.2.0.dmg` (macOS)
   - `PhotoSifter-0.2.0.exe` (Windows)
   - Or `.zip` files
7. Click **"Publish release"**

### 4. Users Get Notified

When users open PhotoSifter, the app automatically checks GitHub for new releases. If a newer version exists, they'll see a dialog prompting them to download it.

## How the Update Checker Works

- Location: `photosift/updater.py`
- Checks: `https://api.github.com/repos/jasonsutter87/photosifter/releases/latest`
- Compares the GitHub release tag (e.g., `v0.2.0`) against `__version__` in the app
- Shows a dialog if a newer version is available
- Opens the release page or direct download link when user clicks "Yes"

## Quick Release Checklist

- [ ] Update version in `photosift/__init__.py`
- [ ] Test the app locally
- [ ] Build with PyInstaller
- [ ] Create GitHub release with tag `vX.Y.Z`
- [ ] Attach built files to release
- [ ] Publish!
