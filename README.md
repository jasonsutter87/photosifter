# PhotoSifter

Smart photo deduplication and organization.

## Features

- Scan folders for duplicate photos and videos
- Identify exact duplicates using SHA256 hashing
- Organize photos by date (YYYY/MM folder structure)
- Move duplicates to a separate folder for review
- Freemium model: 150 photos free, then requires license

## Setup (Development)

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run
python main.py
```

## Build Executable

```bash
# Windows
build.bat

# Linux/Mac
chmod +x build.sh
./build.sh
```

The executable will be in `dist/PhotoSifter.exe` (Windows) or `dist/PhotoSifter` (Linux/Mac).

## License Key Format

`XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX` (provided by LemonSqueezy after purchase)

## Project Structure

```
photosift/
├── __init__.py      # Package info
├── engine.py        # Core deduplication logic
├── gui.py           # CustomTkinter UI
└── licensing.py     # Freemium/license management

main.py              # Entry point
photosift.spec       # PyInstaller config
```
