# PowerContext 任务状态记录（状态保存与复用的证据）

- PowerContext 地址：`http://127.0.0.1:8000`
- Scope 标题：`sdd-context-module`
- Scope ID：`scp_7nd99vvkpwf1h06q9hgpaxg50e`
- 任务 ID：`TASK-ORD-003`
- 读取时间：2026-11-10T21:02:38

## 一、Scope 下的全部记忆条目（原始返回）

```json
[
  {
    "artifact": {
      "family": "atomic-memory",
      "artifact_id": "art_2aa71dd0f6c549ec9bb7f155d44c9c81",
      "revision": 1
    },
    "kind": "sdd-task-state",
    "state": "active",
    "text": "[TASK-ORD-003][done] 导入 5 条规格到 seekdb（规格 / 代码符号 / 测试用例）"
  },
  {
    "artifact": {
      "family": "atomic-memory",
      "artifact_id": "art_320ed70cb2eb45b782b88c5914bff0e7",
      "revision": 1
    },
    "kind": "sdd-task-state",
    "state": "active",
    "text": "[TASK-ORD-003][todo] 为金额区间筛选补充边界用例"
  },
  {
    "artifact": {
      "family": "atomic-memory",
      "artifact_id": "art_50b8ef992b324e65832d985f39c1ad3a",
      "revision": 1
    },
    "kind": "sdd-task-state",
    "state": "active",
    "text": "[TASK-ORD-003][done] 在 seekdb 中建立规格/代码/测试索引并完成三路召回"
  },
  {
    "artifact": {
      "family": "atomic-memory",
      "artifact_id": "art_512abd7e17a14fc49b531c80ec2f5b75",
      "revision": 1
    },
    "kind": "sdd-task-state",
    "state": "active",
    "text": "[TASK-ORD-003][verification] phase=after | command=python -m pytest -q tests | exit_code=0 | passed=37 | failed=0 | log=logs/pytest_after.log"
  },
  {
    "artifact": {
      "family": "atomic-memory",
      "artifact_id": "art_5c240acacfbb49f0a9cc25a3ecbe8f3b",
      "revision": 1
    },
    "kind": "sdd-task-state",
    "state": "active",
    "text": "[TASK-ORD-003][done] 完成 为订单查询增加金额区间筛选"
  },
  {
    "artifact": {
      "family": "atomic-memory",
      "artifact_id": "art_8976ab90355c4135a73a24cfcbe00ffd",
      "revision": 1
    },
    "kind": "sdd-task-state",
    "state": "active",
    "text": "[TASK-ORD-003][done] 由 MiniMax 生成补丁并应用到 filter_orders 与 HTTP 查询接口"
  },
  {
    "artifact": {
      "family": "atomic-memory",
      "artifact_id": "art_d84de225576e4f3e9f441667ff14624b",
      "revision": 1
    },
    "kind": "sdd-task-state",
    "state": "active",
    "text": "[TASK-ORD-003][note] 上下文选择方式：规格声明的关联代码/关联测试优先，关键词命中作为补充"
  }
]
```

## 二、按任务 ID 检索

```json
{
  "mode": "text",
  "hits": 7
}
```

## 三、模块解析出的任务状态

```json
{
  "task_id": "TASK-ORD-003",
  "title": "",
  "description": "",
  "status": "in_progress",
  "done": [
    "导入 5 条规格到 seekdb（规格 / 代码符号 / 测试用例）",
    "在 seekdb 中建立规格/代码/测试索引并完成三路召回",
    "完成 为订单查询增加金额区间筛选",
    "由 MiniMax 生成补丁并应用到 filter_orders 与 HTTP 查询接口"
  ],
  "todo": [
    "为金额区间筛选补充边界用例"
  ],
  "verifications": [
    {
      "raw": "phase=after | command=python -m pytest -q tests | exit_code=0 | passed=37 | failed=0 | log=logs/pytest_after.log",
      "phase": "after",
      "command": "python -m pytest -q tests",
      "exit_code": 0,
      "passed": 37,
      "failed": 0,
      "log": "logs/pytest_after.log"
    }
  ],
  "notes": [
    "上下文选择方式：规格声明的关联代码/关联测试优先，关键词命中作为补充"
  ],
  "origin": "powercontext:scp_7nd99vvkpwf1h06q9hgpaxg50e"
}
```

- 状态来源：`powercontext:scp_7nd99vvkpwf1h06q9hgpaxg50e`
