# PowerContext 任务状态记录（状态保存与复用的证据）

- PowerContext 地址：`http://127.0.0.1:8000`
- Scope 标题：`sdd-context-module`
- Scope ID：`scp_4zzjwe6r0f22fb9yywq0390ykf`
- 任务 ID：`TASK-ORD-003`
- 读取时间：2026-11-10T20:56:40

## 一、Scope 下的全部记忆条目（原始返回）

```json
[
  {
    "artifact": {
      "family": "atomic-memory",
      "artifact_id": "art_3db5dfecf1474169bfd18103703c807a",
      "revision": 1
    },
    "kind": "sdd-task-state",
    "state": "active",
    "text": "[TASK-ORD-003][done] 由 MiniMax 生成补丁并应用到 filter_orders 与 HTTP 查询接口"
  },
  {
    "artifact": {
      "family": "atomic-memory",
      "artifact_id": "art_73f970c6885b4de485fb40d444ac60b3",
      "revision": 1
    },
    "kind": "sdd-task-state",
    "state": "active",
    "text": "[TASK-ORD-003][done] 在 seekdb 中建立规格/代码/测试索引并完成三路召回"
  },
  {
    "artifact": {
      "family": "atomic-memory",
      "artifact_id": "art_7445e879c51c4a28b2b502eb0fea04b4",
      "revision": 1
    },
    "kind": "sdd-task-state",
    "state": "active",
    "text": "[TASK-ORD-003][note] 上下文选择方式：规格声明的关联代码/关联测试优先，关键词命中作为补充"
  },
  {
    "artifact": {
      "family": "atomic-memory",
      "artifact_id": "art_cf83fa8f5c6e44818d47399767b8a40f",
      "revision": 1
    },
    "kind": "sdd-task-state",
    "state": "active",
    "text": "[TASK-ORD-003][done] 导入 5 条规格到 seekdb（规格 / 代码符号 / 测试用例）"
  },
  {
    "artifact": {
      "family": "atomic-memory",
      "artifact_id": "art_d662d1cd71774fe9bd249ba76a463eb3",
      "revision": 1
    },
    "kind": "sdd-task-state",
    "state": "active",
    "text": "[TASK-ORD-003][verification] phase=after | command=python -m pytest -q tests | exit_code=0 | passed=37 | failed=0 | log=logs/pytest_after.log"
  },
  {
    "artifact": {
      "family": "atomic-memory",
      "artifact_id": "art_df807a1a996644b2bc73db0472153a4f",
      "revision": 1
    },
    "kind": "sdd-task-state",
    "state": "active",
    "text": "[TASK-ORD-003][done] 完成 为订单查询增加金额区间筛选"
  },
  {
    "artifact": {
      "family": "atomic-memory",
      "artifact_id": "art_e339ff1fac9242cea34ccd057bd7ae2e",
      "revision": 1
    },
    "kind": "sdd-task-state",
    "state": "active",
    "text": "[TASK-ORD-003][todo] 为金额区间筛选补充边界用例"
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
    "由 MiniMax 生成补丁并应用到 filter_orders 与 HTTP 查询接口",
    "在 seekdb 中建立规格/代码/测试索引并完成三路召回",
    "导入 5 条规格到 seekdb（规格 / 代码符号 / 测试用例）",
    "完成 为订单查询增加金额区间筛选"
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
  "origin": "powercontext:scp_4zzjwe6r0f22fb9yywq0390ykf"
}
```

- 状态来源：`powercontext:scp_4zzjwe6r0f22fb9yywq0390ykf`
