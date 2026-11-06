# 启动公网隧道（cloudflared 快速隧道：免注册、免 token）并输出公网地址
# 前提：cloudflared.exe 已下载到 C:\Users\OQ\cloudflared.exe
# 注意：快速隧道地址每次重启会变化，变更后按 deploy-secret.md 更新 Sites Secret
$ErrorActionPreference = "Continue"
$exe = "C:\Users\OQ\cloudflared.exe"
if (-not (Test-Path $exe)) {
  curl.exe -sL -o $exe "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
}
if (-not (Test-Path $exe)) { Write-Host "cloudflared 下载失败"; exit 1 }

# 已在运行则跳过
$running = Get-Process cloudflared -ErrorAction SilentlyContinue
if (-not $running) {
  Start-Process -WindowStyle Hidden $exe -ArgumentList "tunnel","--url","http://localhost:8001"
  Start-Sleep -Seconds 10
} else {
  Write-Host "cloudflared 已在运行"
}

# 从日志/网络接口抓取 URL：通过本地元数据接口不可用，改为解析进程日志文件
$log = "$env:TEMP\cloudflared-tunnel.log"
if (Test-Path $log) {
  $url = (Select-String -Path $log -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" | Select -Last 1).Matches[0].Value
  if ($url) {
    Write-Host "公网地址: $url"
    Set-Clipboard $url
    Write-Host "(已复制到剪贴板) 下一步：按 scripts\deploy-secret.md 更新 SEEKLIT_BACKEND_URL"
  }
} else {
  Write-Host "请从 cloudflared 启动参数窗口查看 https://xxx.trycloudflare.com 地址"
}
