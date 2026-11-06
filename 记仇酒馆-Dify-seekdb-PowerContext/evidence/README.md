# 运行证据（提交前请放入真实截图/录屏）

## 已采集：真实运行证据

| 路径 | 内容 |
| --- | --- |
| `screenshots/02-workflow-canvas.png` | Dify 1.19 画布：9 个节点全部就位，LLM 节点显示 `deepseek-flash` |
| `screenshots/05-preview-turn1.png` | 第 1 回合：老陈回复 + 记仇本面板（13/100 附近），节点执行路径高亮 |
| `screenshots/07-preview-cross-session-memory.png` | **新会话**：老陈主动提「你那副老花镜…」，证明 PowerContext 跨会话记忆 |
| `screenshots/01-after-login.png` `03b-chat.png` | 登录后工作台、Web App 入口（当前 Web App 未开放，用「预览」代替） |
| `logs/dify-run-sample1-3.json` | 3 回合真实 API 响应（含 conversation_id、每轮 answer） |
| `logs/dify-run-ending.json` `logs/dify-run-ending-final.json` | 连续恶作剧到 100 的完整响应，最后一轮输出结局 |
| `logs/seekdb-evidence.json` | `turn_log` 10 行 + `player_state{grudge:100,mood:0,ending:1}` + `scope_id` |
| `logs/verify-20261107-002853.log` | `scripts/verify.py`：14 PASS / 1 FAIL（Embedding 未配置） |

## 还需要补充的截图

按 `docs/03-验证样例.md` 的「证据采集清单」补齐：条件分支 `true` 的执行详情、PowerContext 写入返回、录屏。
