# install_ffmpeg.ps1
# Cross-platform PowerShell script to install FFmpeg

function Install-FFmpeg {
    Write-Host "Checking for FFmpeg..." -ForegroundColor Cyan
    if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
        Write-Host "✓ FFmpeg is already installed." -ForegroundColor Green
        ffmpeg -version | Select-Object -First 1
        return
    }

    if ($IsWindows) {
        Write-Host "→ Detected Windows. Installing FFmpeg via winget..." -ForegroundColor Cyan
        winget install Gyan.FFmpeg
    }
    elseif ($IsMacOS) {
        Write-Host "→ Detected macOS. Installing FFmpeg via Homebrew..." -ForegroundColor Cyan
        if (-not (Get-Command brew -ErrorAction SilentlyContinue)) {
            Write-Host "✗ Homebrew is not installed. Please install it first from https://brew.sh/" -ForegroundColor Red
            return
        }
        brew install ffmpeg
    }
    elseif ($IsLinux) {
        Write-Host "→ Detected Linux. Installing FFmpeg via apt-get..." -ForegroundColor Cyan
        # Check if apt-get exists (Debian/Ubuntu)
        if (Get-Command apt-get -ErrorAction SilentlyContinue) {
            sudo apt-get update
            sudo apt-get install -y ffmpeg
        } else {
            Write-Host "✗ apt-get not found. Please install FFmpeg using your distribution's package manager." -ForegroundColor Red
        }
    }
    else {
        Write-Host "✗ Unsupported operating system for automatic installation." -ForegroundColor Red
        Write-Host "Please install FFmpeg manually from https://ffmpeg.org/download.html"
    }

    # Final check
    if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
        Write-Host "✓ FFmpeg installation successful!" -ForegroundColor Green
    } else {
        Write-Host "✗ FFmpeg installation failed or requires a terminal restart." -ForegroundColor Yellow
    }
}

Install-FFmpeg
