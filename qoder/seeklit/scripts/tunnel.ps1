# 启动公网隧道（cloudflared 快速隧道：免注册、免 token）并输出公网地址。
# 只使用本机现有 cloudflared，不自动下载或升级软件。
$ErrorActionPreference = "Stop"

$exe = (Get-Command cloudflared.exe -ErrorAction SilentlyContinue).Source
if (-not $exe) {
  $knownExe = Join-Path $env:USERPROFILE "cloudflared.exe"
  if (Test-Path -LiteralPath $knownExe) { $exe = $knownExe }
}
if (-not $exe) {
  throw "未找到 cloudflared.exe。请先按组织规则自行安装或放到 PATH；本脚本不会自动下载。"
}

$running = Get-Process cloudflared -ErrorAction SilentlyContinue
$log = Join-Path $env:TEMP "seeklit-cloudflared.log"
if (-not $running) {
  if (Test-Path -LiteralPath $log) { Clear-Content -LiteralPath $log }
  Start-Process -WindowStyle Hidden -FilePath $exe -ArgumentList @(
    "tunnel", "--url", "http://127.0.0.1:8001", "--logfile", $log
  )
  Write-Host "cloudflared starting; log: $log"
} else {
  Write-Host "cloudflared 已在运行；沿用现有进程"
}

$url = $null
for ($attempt = 0; $attempt -lt 15 -and -not $url; $attempt++) {
  Start-Sleep -Seconds 1
  if (Test-Path -LiteralPath $log) {
    $match = Select-String -Path $log -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" | Select-Object -Last 1
    if ($match) { $url = $match.Matches[0].Value }
  }
}
if (-not $url) {
  throw "15 秒内未从日志取得隧道地址，请检查：$log"
}

Write-Host "公网地址: $url"
Set-Clipboard $url
Write-Host "地址已复制到剪贴板；快速隧道重启后地址会变化。"
