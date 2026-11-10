# seekdb 查询记录（数据库实际参与证据）

共 101 条 SQL，50 条检索命中，3 条测试记录。

## 一、SQL 执行记录

| # | session | SQL | 影响行数 | 耗时(ms) |
| --- | --- | --- | --- | --- |
| 1 | 20261110210210 | `SELECT VERSION()` | 1 | 0.703 |
| 1000001 | 20261110210212 | `USE `sddctx`` | 0 | 0.613 |
| 1000002 | 20261110210212 | `SELECT id, content_hash, revision FROM sdd_spec_item WHERE spec_id = %s` | 0 | 5.929 |
| 1000003 | 20261110210212 | `INSERT INTO sdd_spec_item (spec_id, title, module, status, body, keywords, related_code, related_tests, source_file, content_hash, revision, updated_at) VALUES ` | 1 | 15.454 |
| 1000004 | 20261110210212 | `SELECT id, content_hash, revision FROM sdd_spec_item WHERE spec_id = %s` | 0 | 0.554 |
| 1000005 | 20261110210212 | `INSERT INTO sdd_spec_item (spec_id, title, module, status, body, keywords, related_code, related_tests, source_file, content_hash, revision, updated_at) VALUES ` | 1 | 6.968 |
| 1000006 | 20261110210212 | `SELECT id, content_hash, revision FROM sdd_spec_item WHERE spec_id = %s` | 0 | 0.475 |
| 1000007 | 20261110210212 | `INSERT INTO sdd_spec_item (spec_id, title, module, status, body, keywords, related_code, related_tests, source_file, content_hash, revision, updated_at) VALUES ` | 1 | 5.708 |
| 1000008 | 20261110210212 | `SELECT id, content_hash, revision FROM sdd_spec_item WHERE spec_id = %s` | 0 | 0.704 |
| 1000009 | 20261110210212 | `INSERT INTO sdd_spec_item (spec_id, title, module, status, body, keywords, related_code, related_tests, source_file, content_hash, revision, updated_at) VALUES ` | 1 | 6.791 |
| 1000010 | 20261110210212 | `SELECT id, content_hash, revision FROM sdd_spec_item WHERE spec_id = %s` | 0 | 0.648 |
| 1000011 | 20261110210212 | `INSERT INTO sdd_spec_item (spec_id, title, module, status, body, keywords, related_code, related_tests, source_file, content_hash, revision, updated_at) VALUES ` | 1 | 6.427 |
| 1000012 | 20261110210212 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s,` | 1 | 21.386 |
| 1000013 | 20261110210212 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s,` | 1 | 6.516 |
| 1000014 | 20261110210212 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, 'class'` | 1 | 7.151 |
| 1000015 | 20261110210212 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s,` | 1 | 6.74 |
| 1000016 | 20261110210212 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, 'class'` | 1 | 5.546 |
| 1000017 | 20261110210212 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s,` | 1 | 5.463 |
| 1000018 | 20261110210212 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s,` | 1 | 6.068 |
| 1000019 | 20261110210212 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, 'class'` | 1 | 5.907 |
| 1000020 | 20261110210212 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s,` | 1 | 7.136 |
| 1000021 | 20261110210212 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, 'class'` | 1 | 6.892 |
| 1000022 | 20261110210212 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s,` | 1 | 5.796 |
| 1000023 | 20261110210212 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s,` | 1 | 6.68 |
| 1000024 | 20261110210212 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s,` | 1 | 6.996 |
| 1000025 | 20261110210212 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, 'class'` | 1 | 6.945 |
| 1000026 | 20261110210212 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s,` | 1 | 5.282 |
| 1000027 | 20261110210212 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s,` | 1 | 5.355 |
| 1000028 | 20261110210212 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s,` | 1 | 5.875 |
| 1000029 | 20261110210212 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s,` | 1 | 5.406 |
| 1000030 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 17.209 |
| 1000031 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 6.96 |
| 1000032 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 5.672 |
| 1000033 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 5.781 |
| 1000034 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 7.174 |
| 1000035 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 5.612 |
| 1000036 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 7.159 |
| 1000037 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 7.061 |
| 1000038 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 5.485 |
| 1000039 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 5.658 |
| 1000040 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 8.304 |
| 1000041 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 7.115 |
| 1000042 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 5.731 |
| 1000043 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 6.982 |
| 1000044 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 6.901 |
| 1000045 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 7.078 |
| 1000046 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 7.366 |
| 1000047 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 7.158 |
| 1000048 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 5.834 |
| 1000049 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 6.832 |
| 1000050 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 7.166 |
| 1000051 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 6.822 |
| 1000052 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 5.769 |
| 1000053 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 5.693 |
| 1000054 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 6.128 |
| 1000055 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 6.751 |
| 1000056 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 6.885 |
| 1000057 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 5.609 |
| 1000058 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 5.833 |
| 1000059 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 5.359 |
| 1000060 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 6.42 |
| 1000061 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 5.324 |
| 1000062 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 5.719 |
| 1000063 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 5.597 |
| 1000064 | 20261110210212 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 6.509 |
| 2000001 | 20261110210215 | `USE `sddctx`` | 0 | 0.964 |
| 2000002 | 20261110210215 | `SELECT spec_id, title, module, status, body, keywords, related_code, related_tests, source_file, content_hash, revision FROM sdd_spec_item WHERE (title LIKE %s ` | 5 | 6.699 |
| 2000003 | 20261110210215 | `INSERT INTO sdd_retrieval_log (task_id, query_text, target_kind, item_ref, score, sql_text, created_at) VALUES (%s, %s, %s, %s, %s, %s, NOW())` | 5 | 40.773 |
| 2000004 | 20261110210215 | `SELECT file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash FROM sdd_code_symbol WHERE file_path IN (%s, %s, %s) OR ((` | 8 | 8.741 |
| 2000005 | 20261110210215 | `INSERT INTO sdd_retrieval_log (task_id, query_text, target_kind, item_ref, score, sql_text, created_at) VALUES (%s, %s, %s, %s, %s, %s, NOW())` | 8 | 51.399 |
| 2000006 | 20261110210215 | `SELECT node_id, file_path, test_name, purpose, markers, source_file, content_hash FROM sdd_test_case WHERE file_path IN (%s, %s, %s, %s) OR file_path IN (%s, %s` | 12 | 5.862 |
| 2000007 | 20261110210215 | `INSERT INTO sdd_retrieval_log (task_id, query_text, target_kind, item_ref, score, sql_text, created_at) VALUES (%s, %s, %s, %s, %s, %s, NOW())` | 12 | 86.788 |
| 2000008 | 20261110210215 | `INSERT INTO sdd_task (task_id, title, description, status, created_at, updated_at) VALUES (%s, %s, %s, 'in_progress', NOW(), NOW()) ON DUPLICATE KEY UPDATE titl` | 1 | 7.757 |
| 2000009 | 20261110210215 | `SELECT VERSION()` | 1 | 0.928 |
| 3000001 | 20261110210219 | `USE `sddctx`` | 0 | 0.835 |
| 3000002 | 20261110210219 | `INSERT INTO sdd_verification (task_id, phase, command, exit_code, passed, failed, log_path, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())` | 1 | 17.695 |
| 4000001 | 20261110210224 | `USE `sddctx`` | 0 | 0.987 |
| 4000002 | 20261110210224 | `INSERT INTO sdd_verification (task_id, phase, command, exit_code, passed, failed, log_path, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())` | 1 | 16.722 |
| 5000001 | 20261110210230 | `USE `sddctx`` | 0 | 0.882 |
| 5000002 | 20261110210230 | `INSERT INTO sdd_verification (task_id, phase, command, exit_code, passed, failed, log_path, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())` | 1 | 14.466 |
| 6000001 | 20261110210232 | `USE `sddctx`` | 0 | 1.236 |
| 6000002 | 20261110210232 | `SELECT kind, content FROM sdd_task_progress WHERE task_id = %s` | 0 | 5.179 |
| 6000003 | 20261110210232 | `INSERT INTO sdd_task_progress (task_id, kind, content, origin, created_at) VALUES (%s, %s, %s, %s, NOW())` | 1 | 13.582 |
| 6000004 | 20261110210232 | `INSERT INTO sdd_task_progress (task_id, kind, content, origin, created_at) VALUES (%s, %s, %s, %s, NOW())` | 1 | 6.898 |
| 6000005 | 20261110210232 | `INSERT INTO sdd_task_progress (task_id, kind, content, origin, created_at) VALUES (%s, %s, %s, %s, NOW())` | 1 | 6.571 |
| 6000006 | 20261110210232 | `INSERT INTO sdd_task_progress (task_id, kind, content, origin, created_at) VALUES (%s, %s, %s, %s, NOW())` | 1 | 7.927 |
| 6000007 | 20261110210232 | `INSERT INTO sdd_task_progress (task_id, kind, content, origin, created_at) VALUES (%s, %s, %s, %s, NOW())` | 1 | 7.31 |
| 6000008 | 20261110210232 | `INSERT INTO sdd_task_progress (task_id, kind, content, origin, created_at) VALUES (%s, %s, %s, %s, NOW())` | 1 | 8.015 |
| 6000009 | 20261110210232 | `INSERT INTO sdd_task_progress (task_id, kind, content, origin, created_at) VALUES (%s, %s, %s, %s, NOW())` | 1 | 6.238 |
| 7000001 | 20261110210235 | `USE `sddctx`` | 0 | 0.814 |
| 8000001 | 20261110210237 | `USE `sddctx`` | 0 | 0.693 |
| 9000001 | 20261110210239 | `USE `sddctx`` | 0 | 0.9 |
| 9000002 | 20261110210239 | `SELECT spec_id, title, module, status, body, keywords, related_code, related_tests, source_file, content_hash, revision FROM sdd_spec_item WHERE (title LIKE %s ` | 5 | 8.174 |
| 9000003 | 20261110210239 | `INSERT INTO sdd_retrieval_log (task_id, query_text, target_kind, item_ref, score, sql_text, created_at) VALUES (%s, %s, %s, %s, %s, %s, NOW())` | 5 | 61.115 |
| 9000004 | 20261110210239 | `SELECT file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash FROM sdd_code_symbol WHERE file_path IN (%s, %s, %s) OR ((` | 8 | 8.227 |
| 9000005 | 20261110210239 | `INSERT INTO sdd_retrieval_log (task_id, query_text, target_kind, item_ref, score, sql_text, created_at) VALUES (%s, %s, %s, %s, %s, %s, NOW())` | 8 | 46.707 |
| 9000006 | 20261110210239 | `SELECT node_id, file_path, test_name, purpose, markers, source_file, content_hash FROM sdd_test_case WHERE file_path IN (%s, %s, %s, %s) OR file_path IN (%s, %s` | 12 | 6.636 |
| 9000007 | 20261110210239 | `INSERT INTO sdd_retrieval_log (task_id, query_text, target_kind, item_ref, score, sql_text, created_at) VALUES (%s, %s, %s, %s, %s, %s, NOW())` | 12 | 82.043 |
| 9000008 | 20261110210239 | `INSERT INTO sdd_task (task_id, title, description, status, created_at, updated_at) VALUES (%s, %s, %s, 'in_progress', NOW(), NOW()) ON DUPLICATE KEY UPDATE titl` | 2 | 8.936 |
| 9000009 | 20261110210239 | `SELECT VERSION()` | 1 | 0.752 |
| 10000001 | 20261110210241 | `USE `sddctx`` | 0 | 0.698 |

## 二、上下文召回记录

| # | 任务 | 类型 | 命中项 | 分数 |
| --- | --- | --- | --- | --- |
| 1 | TASK-ORD-003 | spec | `SPEC-ORD-003` | 6.0 |
| 2 | TASK-ORD-003 | spec | `SPEC-ORD-001` | 4.0 |
| 3 | TASK-ORD-003 | spec | `SPEC-API-001` | 3.0 |
| 4 | TASK-ORD-003 | spec | `SPEC-PRC-001` | 2.0 |
| 5 | TASK-ORD-003 | spec | `SPEC-ORD-002` | 1.0 |
| 6 | TASK-ORD-003 | code | `src/order_fulfillment/filters.py::filter_orders` | 7.0 |
| 7 | TASK-ORD-003 | code | `src/order_fulfillment/pricing.py::discount_rate` | 6.0 |
| 8 | TASK-ORD-003 | code | `src/order_fulfillment/filters.py::_sort_value` | 5.0 |
| 9 | TASK-ORD-003 | code | `src/order_fulfillment/service.py::OrderQueryHandler` | 5.0 |
| 10 | TASK-ORD-003 | code | `src/order_fulfillment/service.py::_send_json` | 5.0 |
| 11 | TASK-ORD-003 | code | `src/order_fulfillment/service.py::create_server` | 5.0 |
| 12 | TASK-ORD-003 | code | `src/order_fulfillment/service.py::do_GET` | 5.0 |
| 13 | TASK-ORD-003 | code | `src/order_fulfillment/service.py::log_message` | 5.0 |
| 14 | TASK-ORD-003 | test | `tests/test_feature_amount_filter.py::test_amount_comparison_uses_exact_decimal_arithmetic` | 7.0 |
| 15 | TASK-ORD-003 | test | `tests/test_feature_amount_filter.py::test_min_amount_greater_than_max_amount_is_rejected` | 7.0 |
| 16 | TASK-ORD-003 | test | `tests/test_feature_amount_filter.py::test_max_amount_keeps_orders_on_or_below_the_boundary` | 6.0 |
| 17 | TASK-ORD-003 | test | `tests/test_feature_amount_filter.py::test_min_amount_keeps_orders_on_or_above_the_boundary` | 6.0 |
| 18 | TASK-ORD-003 | test | `tests/test_feature_amount_filter.py::test_non_numeric_amount_is_rejected` | 6.0 |
| 19 | TASK-ORD-003 | test | `tests/test_feature_amount_filter.py::test_orders_endpoint_supports_min_amount_query` | 6.0 |
| 20 | TASK-ORD-003 | test | `tests/test_feature_amount_filter.py::test_amount_filter_combines_with_status_filter` | 5.0 |
| 21 | TASK-ORD-003 | test | `tests/test_feature_amount_filter.py::test_amount_range_is_inclusive_on_both_ends` | 5.0 |
| 22 | TASK-ORD-003 | test | `tests/test_feature_amount_filter.py::test_no_amount_filter_returns_every_order` | 5.0 |
| 23 | TASK-ORD-003 | test | `tests/test_feature_amount_filter.py::test_orders_endpoint_rejects_invalid_amount_query` | 5.0 |
| 24 | TASK-ORD-003 | test | `tests/test_filters.py::test_filters_by_status_instance` | 5.0 |
| 25 | TASK-ORD-003 | test | `tests/test_filters.py::test_filters_by_status_string` | 5.0 |
| 1000001 | TASK-ORD-003 | spec | `SPEC-ORD-003` | 6.0 |
| 1000002 | TASK-ORD-003 | spec | `SPEC-ORD-001` | 4.0 |
| 1000003 | TASK-ORD-003 | spec | `SPEC-API-001` | 3.0 |
| 1000004 | TASK-ORD-003 | spec | `SPEC-PRC-001` | 2.0 |
| 1000005 | TASK-ORD-003 | spec | `SPEC-ORD-002` | 1.0 |
| 1000006 | TASK-ORD-003 | code | `src/order_fulfillment/filters.py::filter_orders` | 7.0 |
| 1000007 | TASK-ORD-003 | code | `src/order_fulfillment/pricing.py::discount_rate` | 6.0 |
| 1000008 | TASK-ORD-003 | code | `src/order_fulfillment/filters.py::_sort_value` | 5.0 |
| 1000009 | TASK-ORD-003 | code | `src/order_fulfillment/service.py::OrderQueryHandler` | 5.0 |
| 1000010 | TASK-ORD-003 | code | `src/order_fulfillment/service.py::_send_json` | 5.0 |
| 1000011 | TASK-ORD-003 | code | `src/order_fulfillment/service.py::create_server` | 5.0 |
| 1000012 | TASK-ORD-003 | code | `src/order_fulfillment/service.py::do_GET` | 5.0 |
| 1000013 | TASK-ORD-003 | code | `src/order_fulfillment/service.py::log_message` | 5.0 |
| 1000014 | TASK-ORD-003 | test | `tests/test_feature_amount_filter.py::test_amount_comparison_uses_exact_decimal_arithmetic` | 7.0 |
| 1000015 | TASK-ORD-003 | test | `tests/test_feature_amount_filter.py::test_min_amount_greater_than_max_amount_is_rejected` | 7.0 |
| 1000016 | TASK-ORD-003 | test | `tests/test_feature_amount_filter.py::test_max_amount_keeps_orders_on_or_below_the_boundary` | 6.0 |
| 1000017 | TASK-ORD-003 | test | `tests/test_feature_amount_filter.py::test_min_amount_keeps_orders_on_or_above_the_boundary` | 6.0 |
| 1000018 | TASK-ORD-003 | test | `tests/test_feature_amount_filter.py::test_non_numeric_amount_is_rejected` | 6.0 |
| 1000019 | TASK-ORD-003 | test | `tests/test_feature_amount_filter.py::test_orders_endpoint_supports_min_amount_query` | 6.0 |
| 1000020 | TASK-ORD-003 | test | `tests/test_feature_amount_filter.py::test_amount_filter_combines_with_status_filter` | 5.0 |
| 1000021 | TASK-ORD-003 | test | `tests/test_feature_amount_filter.py::test_amount_range_is_inclusive_on_both_ends` | 5.0 |
| 1000022 | TASK-ORD-003 | test | `tests/test_feature_amount_filter.py::test_no_amount_filter_returns_every_order` | 5.0 |
| 1000023 | TASK-ORD-003 | test | `tests/test_feature_amount_filter.py::test_orders_endpoint_rejects_invalid_amount_query` | 5.0 |
| 1000024 | TASK-ORD-003 | test | `tests/test_filters.py::test_filters_by_status_instance` | 5.0 |
| 1000025 | TASK-ORD-003 | test | `tests/test_filters.py::test_filters_by_status_string` | 5.0 |

## 三、测试执行记录

| # | 任务 | 阶段 | 命令 | 退出码 | 通过 | 失败 | 日志 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | TASK-ORD-003 | before | `/root/venvs/seeklit/bin/python -m pytest -q tests/test_feature_amount_filter.py` | 1 | 1 | 11 | `logs/pytest_before_feature.log` |
| 1000001 | TASK-ORD-003 | after-feature | `/root/venvs/seeklit/bin/python -m pytest -q tests/test_feature_amount_filter.py` | 0 | 12 | 0 | `logs/pytest_after_feature.log` |
| 2000001 | TASK-ORD-003 | after | `/root/venvs/seeklit/bin/python -m pytest -q tests` | 0 | 37 | 0 | `logs/pytest_after.log` |
