# ============================================================
# CHẠY SCRIPT NÀY MỘT LẦN ĐỂ SETUP GIT
# Mở PowerShell trong thư mục này và chạy: .\git-setup.ps1
# ============================================================

$folder = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $folder

Write-Host "=== Setup Git cho AI-Bridge-Design ===" -ForegroundColor Cyan

# Khởi tạo git nếu chưa có
if (-not (Test-Path ".git")) {
    git init
    git branch -m main
}

# Cấu hình user
git config user.name "Chuongdnd"
git config user.email "dinhchuong2806@gmail.com"

# Thêm remote origin
$remotes = git remote
if ($remotes -notcontains "origin") {
    git remote add origin https://github.com/Chuongdnd/AI-Bridge-Design.git
    Write-Host "Da them remote origin" -ForegroundColor Green
} else {
    git remote set-url origin https://github.com/Chuongdnd/AI-Bridge-Design.git
    Write-Host "Da cap nhat remote origin" -ForegroundColor Green
}

# Fetch từ GitHub
Write-Host "`nDang fetch tu GitHub..." -ForegroundColor Yellow
git fetch origin

# Kiểm tra branch main có tồn tại trên remote không
$remoteBranch = git ls-remote --heads origin main
if ($remoteBranch) {
    Write-Host "Da tim thay branch main tren GitHub, dang pull..." -ForegroundColor Yellow
    git pull origin main --allow-unrelated-histories
} else {
    Write-Host "Branch main chua co tren GitHub, se push khi commit dau tien." -ForegroundColor Yellow
}

Write-Host "`n=== Setup hoan tat! ===" -ForegroundColor Green
Write-Host "Remote: $(git remote get-url origin)" -ForegroundColor Cyan
Write-Host "Branch: $(git branch --show-current)" -ForegroundColor Cyan
Write-Host "`nDe push code, chay: .\git-push.ps1" -ForegroundColor White
