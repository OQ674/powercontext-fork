# Windows 一键启动脚本
$Host.UI.RawUI.WindowTitle = "StepFun Mini Knowledge Base"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  端侧 AI 推理性能优化与 seekdb 混合检索 (阶跃星辰赛题)" -ForegroundColor Cyan
Write-Host "  2026 OceanBase 数据库大赛 · PowerContext 生态" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 检查当前目录
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
Set-Location $ProjectDir

Write-Host "`n[1/3] 检查 Node.js 运行环境..." -ForegroundColor Yellow
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    if (Test-Path "$env:LOCALAPPDATA\Programs\NodeJS\node.exe") {
        $env:PATH = "$env:LOCALAPPDATA\Programs\NodeJS;$env:PATH"
    } else {
        Write-Host "错误: 未找到 Node.js，请先安装 Node.js LTS 后重试。" -ForegroundColor Red
        Exit 1
    }
}
$nodeVersion = node -v
Write-Host "Node.js 版本: $nodeVersion" -ForegroundColor Green

Write-Host "`n[2/3] 检查依赖包..." -ForegroundColor Yellow
if (-not (Test-Path "node_modules")) {
    Write-Host "正在安装依赖 npm install..." -ForegroundColor Yellow
    npm install
} else {
    Write-Host "依赖已就绪。" -ForegroundColor Green
}

Write-Host "`n[3/3] 启动 Web 知识库服务..." -ForegroundColor Yellow
Write-Host "本地访问地址: http://localhost:3000" -ForegroundColor Green
Write-Host "按 Ctrl+C 可停止服务。`n" -ForegroundColor Gray

npm start
