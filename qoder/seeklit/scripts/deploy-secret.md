# 隧道地址变更后更新 Sites Secret（约 60 秒，即时生效，无需重新发布）

当前隧道方案：cloudflared 快速隧道（免注册免 token，但地址每次重启变化）。

1. 运行 `scripts\tunnel.ps1`，或查看 cloudflared 输出中的公网地址，形如 `https://xxxx.trycloudflare.com`（不带末尾斜杠）。
2. 打开 Qoder Sites 管理界面 → Settings → Secrets。
3. 更新 `SEEKLIT_BACKEND_URL` 为新地址。
4. 确认同步成功后访问线上站点验证：搜索「分布式事务」应正常返回。

保持隧道长期稳定（可选升级）：
- 注册 Cloudflare 账号后 `cloudflared tunnel login` + 命名隧道可绑定固定域名，地址不再变化；
- 或改用 ngrok 免费版（提供 1 个静态域名）。
