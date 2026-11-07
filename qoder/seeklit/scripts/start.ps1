param(
  [string]$Distro = "Ubuntu-24.04"
)

# SeekLit 一键启动：WSL seekdb 后端 + 本地 Deno Function + 静态前端。
# 只使用已安装的软件，不自动下载依赖，也不自动打开浏览器。
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backendWin = Join-Path $root "backend"

# 1) WSL 后端（FastAPI + pyseekdb, :8001）
$wsl = Join-Path $env:WINDIR "System32\wsl.exe"
if (-not (Test-Path -LiteralPath $wsl)) {
  $wsl = (Get-Command wsl.exe -ErrorAction Stop).Source
}
$backendWsl = (& $wsl -d $Distro -- wslpath -a $backendWin).Trim()
if ($LASTEXITCODE -ne 0 -or -not $backendWsl) {
  throw "无法把后端路径转换为 WSL 路径：$backendWin"
}
$backendWslQuoted = $backendWsl
if ($backendWslQuoted.Contains("'")) { throw "项目路径不能包含单引号：$backendWslQuoted" }
$backendCommand = "test -x /root/venvs/seeklit/bin/python && cd '$backendWslQuoted' && nohup /root/venvs/seeklit/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8001 >/root/seeklit.log 2>&1 </dev/null &"
& $wsl -d $Distro -u root --exec bash -lc $backendCommand
if ($LASTEXITCODE -ne 0) { throw "WSL seekdb 后端启动失败，请检查 /root/venvs/seeklit 与 ~/seeklit.log" }
Write-Host "backend starting on :8001 (WSL log: /root/seeklit.log)"

# 2) 本地 Deno Function 转发（:8000），可读取 dev/.env
$deno = (Get-Command deno.exe -ErrorAction SilentlyContinue).Source
if (-not $deno) {
  $knownDeno = Join-Path $env:USERPROFILE ".deno\bin\deno.exe"
  if (Test-Path -LiteralPath $knownDeno) { $deno = $knownDeno }
}
if (-not $deno) { throw "未找到已安装的 deno.exe" }
Start-Process -WindowStyle Hidden -FilePath $deno -ArgumentList @(
  "run", "--allow-net", "--allow-env", "--allow-read", (Join-Path $root "dev\function-local.ts")
)
Write-Host "deno function dev on http://127.0.0.1:8000"

# 3) 本地前端（静态 + 代理一体，:5173）
$pythonCandidates = @(
  (Get-Command python3.exe -ErrorAction SilentlyContinue).Source,
  "D:\Py\anaconda\python.exe",
  (Get-Command python.exe -ErrorAction SilentlyContinue).Source
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
$python = $pythonCandidates | Select-Object -First 1
if (-not $python) { throw "未找到可用的 Python；可单独用任意静态服务器打开 web/" }
Start-Process -WindowStyle Hidden -FilePath $python -ArgumentList @((Join-Path $root "dev\serve_local.py"))
Write-Host "frontend on http://127.0.0.1:5173"
Write-Host "已启动本地服务；脚本不会自动打开浏览器。"
