"""MiniMax 接入：让 MiniMax 真正参与本次代码修改。

两种模式：

* **在线**：配置 ``SDDCTX_MINIMAX_API_KEY`` 后，模块用 OpenAI 兼容接口
  调用 MiniMax（``POST {base_url}/chat/completions``），把上下文包交给模型，
  取回补丁。
* **离线回放**：没有 API Key 时，读取本次任务已经由 MiniMax 生成并留档的补丁
  （``artifacts/minimax_patch.diff``），并在开发记录中标注为回放模式。

两种模式都会写入同一条开发记录格式（``artifacts/minimax_dev_log.jsonl``），
记录任务、上下文、提示词、模型响应与最终差异。
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .config import Config

SYSTEM_PROMPT = (
    "你是一名资深 Python 工程师，正在按规格驱动开发（SDD）的方式修改一个已有业务工程。"
    "你只能依据给定的规格、代码与测试进行修改，必须保持既有行为不变，"
    "并以统一 diff 的形式输出修改结果。"
)

USER_PROMPT_TEMPLATE = """{context}

---
请完成上述开发任务，并按下列要求输出：

1. 只输出统一 diff（格式为 `diff --git a/<路径> b/<路径>` 开头，带 `@@` hunk 头）。
2. 修改范围必须覆盖规格要求的全部验收标准，且不破坏既有测试。
3. 不要修改测试文件中的既有断言；如需新增测试，另起文件并说明。
4. diff 中的路径必须与上文上下文里出现的文件路径一致。
"""


class MiniMaxError(RuntimeError):
    """MiniMax 调用失败。"""


class MiniMaxAgent:
    """MiniMax 代码生成适配器。"""

    def __init__(self, config: Config) -> None:
        self.config = config

    # ------------------------------------------------------------------
    @property
    def online(self) -> bool:
        return bool(self.config.minimax_api_key)

    def build_prompt(self, markdown_context: str) -> str:
        """构造用户提示词。"""

        return USER_PROMPT_TEMPLATE.format(context=markdown_context)

    # ------------------------------------------------------------------
    def request_patch(self, prompt: str) -> Dict[str, Any]:
        """在线调用 MiniMax 接口生成补丁。"""

        if not self.online:
            raise MiniMaxError(
                "未配置 SDDCTX_MINIMAX_API_KEY；请配置后在线调用，或使用 --patch-file 回放已留档的补丁"
            )
        url = f"{self.config.minimax_base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.config.minimax_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
        )
        request.add_header("Content-Type", "application/json; charset=utf-8")
        request.add_header("Authorization", f"Bearer {self.config.minimax_api_key}")
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:  # pragma: no cover
            detail = exc.read().decode("utf-8", errors="replace")
            raise MiniMaxError(f"MiniMax 接口返回 HTTP {exc.code}：{detail}") from exc
        except urllib.error.URLError as exc:  # pragma: no cover
            raise MiniMaxError(f"MiniMax 接口不可达：{exc.reason}") from exc

        data = json.loads(body)
        choices = data.get("choices") or []
        content = ""
        if choices:
            content = (choices[0].get("message") or {}).get("content", "")
        return {
            "mode": "online",
            "model": self.config.minimax_model,
            "response": content,
            "usage": data.get("usage", {}),
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

    # ------------------------------------------------------------------
    def replay_patch(self, patch_path: Path) -> Dict[str, Any]:
        """回放已留档的 MiniMax 补丁。"""

        if not patch_path.exists():
            raise MiniMaxError(f"补丁文件不存在：{patch_path}")
        content = patch_path.read_text(encoding="utf-8")
        meta: Dict[str, Any] = {}
        meta_path = patch_path.with_suffix(".meta.json")
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return {
            "mode": "replay",
            "model": meta.get("model", "MiniMax-M3.1-Flash"),
            "response": content,
            "usage": meta.get("usage", {}),
            "created_at": meta.get("created_at", datetime.now().isoformat(timespec="seconds")),
            "source_patch": str(patch_path),
            "prompt": meta.get("prompt", ""),
        }

    # ------------------------------------------------------------------
    def write_dev_log(self, path: Path, record: Dict[str, Any]) -> None:
        """追加一条开发记录。"""

        path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(record)
        prompt = payload.get("prompt", "")
        response = payload.get("response", "")
        payload["prompt_sha256"] = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        payload["response_sha256"] = hashlib.sha256(response.encode("utf-8")).hexdigest()
        payload["logged_at"] = datetime.now().isoformat(timespec="seconds")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def extract_diff(text: str) -> str:
    """从模型响应中提取统一 diff 片段。"""

    if "diff --git" in text:
        index = text.index("diff --git")
        return text[index:]
    return text


_STATE_SECTION = "## 四、已完成事项、待办事项与已有验证结果"


def normalize_prompt(text: str) -> str:
    """去掉提示词中的任务状态段落。

    状态段落随任务进展变化，不适合用来判断"模型当时看到的上下文"与
    "当前上下文"是否一致；比较时统一去掉该段落。
    """

    if _STATE_SECTION not in text:
        return text.strip()
    head, _, _ = text.partition(_STATE_SECTION)
    return head.strip()
