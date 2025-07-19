#!/bin/bash
# Helper script to save Windows clipboard image to WSL filesystem

echo "Saving clipboard image..."
powershell.exe -ExecutionPolicy Bypass -File ./save_clipboard_image.ps1

# List saved images
echo "Available images in /mnt/c/temp/:"
ls -la /mnt/c/temp/clipboard_image_* 2>/dev/null || echo "No images found"
