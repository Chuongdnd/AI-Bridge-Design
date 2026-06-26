# ============================================================
# SCRIPT ĐẨY CODE LÊN GITHUB — CHỈ PUSH FILE ĐƯỢC CHỈ ĐỊNH
# Cách dùng:
#   .\git-push.ps1 file1.py                       (1 file, message mặc định)
#   .\git-push.ps1 file1.py,file2.py "Mô tả"      (nhiều file + message)
# KHÔNG dùng "git add ." — chỉ stage đúng file bạn liệt kê.
# ============================================================

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string[]]$Files,
    [Parameter(Position=1)]
    [string]$Message = ""
)

$folder = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $folder

Write-Host "=== Push file len GitHub (chi file duoc chi dinh) ===" -ForegroundColor Cyan

if (-not (Test-Path ".git")) {
    Write-Host "Git chua duoc setup! Chay git-setup.ps1 truoc." -ForegroundColor Red
    exit 1
}

# Kiem tra tung file ton tai
$missing = $Files | Where-Object { -not (Test-Path $_) }
if ($missing) {
    Write-Host "Khong tim thay file:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    exit 1
}

# CHI stage cac file duoc liet ke
git add -- $Files

Write-Host "`nFile se push:" -ForegroundColor Yellow
git status --short -- $Files

$staged = git diff --cached --name-only
if (-not $staged) {
    Write-Host "`nKhong co thay doi nao trong cac file da chon de push." -ForegroundColor Yellow
    exit 0
}

# Commit message
if (-not $Message) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"
    $Message = "Update: $timestamp"
}

git commit -m $Message

Write-Host "`nDang push len GitHub..." -ForegroundColor Yellow
$branch = git branch --show-current
git push origin $branch

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n=== Push thanh cong! ===" -ForegroundColor Green
    Write-Host "Xem tai: https://github.com/Chuongdnd/AI-Bridge-Design" -ForegroundColor Cyan
} else {
    Write-Host "`nPush that bai. Co the can dang nhap GitHub (username + Personal Access Token)." -ForegroundColor Red
}
