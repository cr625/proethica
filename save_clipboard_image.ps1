# PowerShell script to save clipboard image
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$clipboard = [System.Windows.Forms.Clipboard]::GetImage()
if ($clipboard -ne $null) {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $filename = "clipboard_image_$timestamp.png"
    $filepath = "C:\temp\$filename"
    
    # Create temp directory if it doesn't exist
    if (!(Test-Path "C:\temp")) {
        New-Item -ItemType Directory -Path "C:\temp"
    }
    
    $clipboard.Save($filepath, [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Output "Image saved to: $filepath"
    Write-Output "WSL path: /mnt/c/temp/$filename"
} else {
    Write-Output "No image found in clipboard"
}
