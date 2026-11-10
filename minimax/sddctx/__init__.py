"""SDD 上下文管理模块。

模块职责：为 AI 开发助手提供"当前任务应该遵守什么规格、应该改哪些代码、用哪些测试验证"，
并把任务进展保存到 PowerContext 以便跨进程、跨会话复用。

主要组件：

* :mod:`sddctx.db` —— seekdb / OceanBase 访问层（MySQL 协议）。
* :mod:`sddctx.importer` —— 规格、代码符号、测试用例的导入与版本化。
* :mod:`sddctx.retriever` —— 基于 SQL 的三路召回（规格 / 代码 / 测试）。
* :mod:`sddctx.context` —— 上下文包组装（JSON + Markdown）。
* :mod:`sddctx.powercontext_client` —— PowerContext 任务状态存取。
* :mod:`sddctx.agent` —— MiniMax 代码生成接入（在线 API / 离线补丁回放）。
* :mod:`sddctx.verify` —— 功能与回归测试执行。
"""

__version__ = "1.0.0"

__all__ = ["__version__"]
