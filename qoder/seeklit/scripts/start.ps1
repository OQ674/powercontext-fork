# SeekLit 一键启动：WSL 后端 + 本地 Deno Function + 静态前端
# 用法: powershell -ExecutionPolicy Bypass -File scripts\start.ps1
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot

# 1) WSL 后端（FastAPI + pyseekdb, :8001）
wsl -d Ubuntu-24.04 -u root --exec bash -c "cd '/mnt/d/文件/文档/Oceanbase大赛/速成/Qoder/seeklit/backend' && nohup /root/venvs/seeklit/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8001 >/root/seeklit.log 2>&1 &"
Write-Host "backend starting on :8001 (log: wsl ~/seeklit.log)"

# 2) 本地 Deno Function 转发（:8000），读取 functions/.env
$deno = "C:\Users\OQ\.deno\bin\deno.exe"
if (-not (Test-Path $deno)) { $deno = (Get-Command deno -ErrorAction SilentlyContinue).Source }
Start-Process -WindowStyle Hidden -FilePath $deno -ArgumentList "run","--allow-net","--allow-env","--allow-read","$root\dev\function-local.ts"
Write-Host "deno function dev on :8000"

# 3) 本地前端（静态 + 代理一体，:5173）
$py = "D:\Py\anaconda\python.exe"
if (-not (Test-Path $py)) { $py = (Get-Command python -ErrorAction SilentlyContinue).Source }
Start-Process -WindowStyle Hidden -FilePath $py -ArgumentList "$root\dev\serve_local.py"
Write-Host "frontend on http://localhost:5173"
Start-Sleep -Seconds 4
Start-Process "http://localhost:5173"
