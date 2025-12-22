#!/bin/bash
# Build PhotoSift for distribution

set -e

echo "Installing dependencies..."
pip install -r requirements.txt
pip install pyinstaller

echo "Building executable..."
pyinstaller photosift.spec --clean

echo "Done! Executable is in dist/PhotoSift"
