"""端到端冒烟测试：不经过 Dify，直接验证 bridge + seekdb + PowerContext 的链路。

用法：
    python scripts/verify.py --base http://127.0.0.1:8099 --user verify-user

它会依次验证：
    1. /healthz 三件套（seekdb / PowerContext / Embedding 配置）
    2. reset 后初始状态干净（记仇 0，回合 0）
    3. seekdb 混合检索能召回「盐罐」「糖罐」
    4. 提交一回合后，seekdb 账本与 PowerContext 记忆都发生变化
    5. 下一次 prepare 能把上一回合的记忆召回
    6. 连续作恶到记仇 100，状态进入结局
    7. 再次 reset 后回到初始状态（可重复验证）

退出码 0 表示全部通过；1 表示有失败项。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

PASS: list[str] = []
FAIL: list[str] = []


def call(base: str, path: str, payload: dict | None = None) -> dict:
    url = base.rstrip("/") + path
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check(name: str, ok: bool, detail: str = "") -> None:
    line = f"{'[PASS]' if ok else '[FAIL]'} {name}"
    if detail:
        line += f"  —— {detail}"
    print(line)
    (PASS if ok else FAIL).append(name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8099")
    parser.add_argument("--user", default="verify-user")
    args = parser.parse_args()
    base, user = args.base, args.user

    try:
        health = call(base, "/healthz")
    except urllib.error.URLError as exc:
        print(f"[FAIL] bridge 未启动或不可达：{exc}")
        return 1

    check("seekdb 可连接", bool(health.get("seekdb", {}).get("ok")), str(health.get("seekdb")))
    check(
        "PowerContext 可连接",
        bool(health.get("powercontext", {}).get("ok")),
        "记忆功能依赖它；不可用时会降级但不阻塞游戏",
    )
    check(
        "Embedding 已配置",
        bool(health.get("embedding", {}).get("configured")),
        "未配置时检索降级为全文模式",
    )

    reset = call(base, "/v1/reset", {"user_id": user})
    state = reset["state"]
    check("reset 后记仇=0、回合=0", state["grudge"] == 0 and state["turn_no"] == 0, json.dumps(state))

    search = call(
        base,
        "/v1/props/search",
        {"user_id": user, "query": "我把吧台上的盐罐换成了糖罐", "limit": 6},
    )
    names = [item["name"] for item in search["props"]]
    check("检索命中了「盐罐」", "盐罐" in names, f"hits={names} mode={search['meta']['mode']}")
    check("检索命中了「糖罐」", "糖罐" in names, f"mode={search['meta']['mode']}")

    prep = call(base, "/v1/memory/prepare", {"user_id": user, "query": "盐罐 糖罐 恶作剧"})
    check("首次进入时记忆为空", prep["memory_hits"] == 0, f"context={prep['context'][:60]!r}")
    check("首次进入时记仇=0", prep["state"]["grudge"] == 0)

    commit = call(
        base,
        "/v1/memory/commit",
        {
            "user_id": user,
            "action": "我把吧台上的盐罐换成了糖罐",
            "reply": "老陈端起来喝了一口，眉毛动了一下，什么也没说。",
            "ledger": "把盐罐换成了糖罐",
            "prop_used": "盐罐",
            "grudge": 18,
            "mood": 52,
            "ending": "no",
        },
    )
    check("回合已记账", commit["turn_no"] == 1 and commit["grudge"] == 18, json.dumps(commit))
    check("记忆已写入 PowerContext", commit["memory_saved"], str(commit.get("warnings")))

    prep2 = call(base, "/v1/memory/prepare", {"user_id": user, "query": "盐罐 糖罐 恶作剧"})
    recalled = prep2["context"] or ""
    check(
        "下一回合召回了上一回合的记忆",
        prep2["memory_hits"] == 1 and ("盐罐" in recalled or "糖罐" in recalled),
        f"context={recalled[:80]!r}",
    )

    for step in range(5):
        grudge = min(100, 18 + 17 * (step + 1))
        commit = call(
            base,
            "/v1/memory/commit",
            {
                "user_id": user,
                "action": f"第 {step + 2} 次恶作剧：把老陈的东西藏起来",
                "reply": "老陈没说话，只是把抹布叠得更整齐了。",
                "ledger": "又藏了一次东西",
                "prop_used": "老花镜",
                "grudge": grudge,
                "mood": max(10, 52 - 6 * (step + 1)),
                "ending": "yes" if grudge >= 100 else "no",
            },
        )
    check("记仇值到 100 触发结局", commit["grudge"] == 100 and commit["ending"], json.dumps(commit))

    state = call(base, f"/v1/state/{user}")["state"]
    check("结局已写入 seekdb 状态", state["ending"] is True, json.dumps(state))

    turns = call(base, f"/v1/turns/{user}?limit=10")["turns"]
    check("回合流水可查询", len(turns) >= 5, f"turns={len(turns)}")

    reset2 = call(base, "/v1/reset", {"user_id": user})
    check(
        "reset 后可重新开始",
        reset2["state"]["grudge"] == 0 and reset2["state"]["turn_no"] == 0,
        json.dumps(reset2["state"]),
    )

    print(f"\n结果：{len(PASS)} 通过 / {len(FAIL)} 失败")
    if FAIL:
        print("失败项：" + "；".join(FAIL))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
