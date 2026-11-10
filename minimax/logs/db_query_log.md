# seekdb 查询记录（数据库实际参与证据）

共 100 条 SQL，50 条检索命中，3 条测试记录。

## 一、SQL 执行记录

| # | session | SQL | 影响行数 | 耗时(ms) |
| --- | --- | --- | --- | --- |
| 1 | 20261110205611 | `SELECT VERSION()` | 1 | 0.857 |
| 1000001 | 20261110205614 | `USE `sddctx`` | 0 | 0.844 |
| 1000002 | 20261110205614 | `SELECT id, content_hash, revision FROM sdd_spec_item WHERE spec_id = %s` | 0 | 5.279 |
| 1000003 | 20261110205614 | `INSERT INTO sdd_spec_item (spec_id, title, module, status, body, keywords, related_code, related_tests, source_file, content_hash, revision, updated_at) VALUES ` | 1 | 14.426 |
| 1000004 | 20261110205614 | `SELECT id, content_hash, revision FROM sdd_spec_item WHERE spec_id = %s` | 0 | 0.714 |
| 1000005 | 20261110205614 | `INSERT INTO sdd_spec_item (spec_id, title, module, status, body, keywords, related_code, related_tests, source_file, content_hash, revision, updated_at) VALUES ` | 1 | 7.129 |
| 1000006 | 20261110205614 | `SELECT id, content_hash, revision FROM sdd_spec_item WHERE spec_id = %s` | 0 | 0.848 |
| 1000007 | 20261110205614 | `INSERT INTO sdd_spec_item (spec_id, title, module, status, body, keywords, related_code, related_tests, source_file, content_hash, revision, updated_at) VALUES ` | 1 | 5.698 |
| 1000008 | 20261110205614 | `SELECT id, content_hash, revision FROM sdd_spec_item WHERE spec_id = %s` | 0 | 0.626 |
| 1000009 | 20261110205614 | `INSERT INTO sdd_spec_item (spec_id, title, module, status, body, keywords, related_code, related_tests, source_file, content_hash, revision, updated_at) VALUES ` | 1 | 6.984 |
| 1000010 | 20261110205614 | `SELECT id, content_hash, revision FROM sdd_spec_item WHERE spec_id = %s` | 0 | 0.574 |
| 1000011 | 20261110205614 | `INSERT INTO sdd_spec_item (spec_id, title, module, status, body, keywords, related_code, related_tests, source_file, content_hash, revision, updated_at) VALUES ` | 1 | 6.816 |
| 1000012 | 20261110205614 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s,` | 1 | 27.434 |
| 1000013 | 20261110205614 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s,` | 1 | 7.194 |
| 1000014 | 20261110205614 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, 'class'` | 1 | 9.023 |
| 1000015 | 20261110205614 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s,` | 1 | 6.516 |
| 1000016 | 20261110205614 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, 'class'` | 1 | 7.124 |
| 1000017 | 20261110205614 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s,` | 1 | 6.392 |
| 1000018 | 20261110205614 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s,` | 1 | 5.794 |
| 1000019 | 20261110205614 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, 'class'` | 1 | 7.401 |
| 1000020 | 20261110205614 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s,` | 1 | 6.302 |
| 1000021 | 20261110205614 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, 'class'` | 1 | 6.992 |
| 1000022 | 20261110205614 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s,` | 1 | 6.695 |
| 1000023 | 20261110205614 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s,` | 1 | 6.757 |
| 1000024 | 20261110205614 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s,` | 1 | 5.703 |
| 1000025 | 20261110205614 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, 'class'` | 1 | 8.083 |
| 1000026 | 20261110205614 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s,` | 1 | 6.242 |
| 1000027 | 20261110205614 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s,` | 1 | 7.185 |
| 1000028 | 20261110205614 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s,` | 1 | 6.018 |
| 1000029 | 20261110205614 | `INSERT INTO sdd_code_symbol (file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s,` | 1 | 7.839 |
| 1000030 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 16.583 |
| 1000031 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 6.736 |
| 1000032 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 5.742 |
| 1000033 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 7.142 |
| 1000034 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 6.9 |
| 1000035 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 6.829 |
| 1000036 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 6.743 |
| 1000037 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 5.864 |
| 1000038 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 5.658 |
| 1000039 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 6.783 |
| 1000040 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 6.696 |
| 1000041 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 6.977 |
| 1000042 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 6.563 |
| 1000043 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 5.66 |
| 1000044 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 5.926 |
| 1000045 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 6.801 |
| 1000046 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 7.499 |
| 1000047 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 5.484 |
| 1000048 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 6.893 |
| 1000049 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 5.761 |
| 1000050 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 7.164 |
| 1000051 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 5.674 |
| 1000052 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 5.475 |
| 1000053 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 7.086 |
| 1000054 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 5.671 |
| 1000055 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 5.962 |
| 1000056 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 6.714 |
| 1000057 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 6.747 |
| 1000058 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 6.814 |
| 1000059 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 6.784 |
| 1000060 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 6.523 |
| 1000061 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 6.763 |
| 1000062 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 7.38 |
| 1000063 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 6.922 |
| 1000064 | 20261110205614 | `INSERT INTO sdd_test_case (node_id, file_path, test_name, purpose, markers, source_file, content_hash, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW()) ON` | 1 | 5.673 |
| 2000001 | 20261110205617 | `USE `sddctx`` | 0 | 0.707 |
| 2000002 | 20261110205617 | `SELECT spec_id, title, module, status, body, keywords, related_code, related_tests, source_file, content_hash, revision FROM sdd_spec_item WHERE (title LIKE %s ` | 5 | 7.421 |
| 2000003 | 20261110205617 | `INSERT INTO sdd_retrieval_log (task_id, query_text, target_kind, item_ref, score, sql_text, created_at) VALUES (%s, %s, %s, %s, %s, %s, NOW())` | 5 | 40.652 |
| 2000004 | 20261110205617 | `SELECT file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash FROM sdd_code_symbol WHERE file_path IN (%s, %s, %s) OR ((` | 8 | 7.694 |
| 2000005 | 20261110205617 | `INSERT INTO sdd_retrieval_log (task_id, query_text, target_kind, item_ref, score, sql_text, created_at) VALUES (%s, %s, %s, %s, %s, %s, NOW())` | 8 | 50.64 |
| 2000006 | 20261110205617 | `SELECT node_id, file_path, test_name, purpose, markers, source_file, content_hash FROM sdd_test_case WHERE file_path IN (%s, %s, %s, %s) OR file_path IN (%s, %s` | 12 | 8.576 |
| 2000007 | 20261110205617 | `INSERT INTO sdd_retrieval_log (task_id, query_text, target_kind, item_ref, score, sql_text, created_at) VALUES (%s, %s, %s, %s, %s, %s, NOW())` | 12 | 80.512 |
| 2000008 | 20261110205617 | `INSERT INTO sdd_task (task_id, title, description, status, created_at, updated_at) VALUES (%s, %s, %s, 'in_progress', NOW(), NOW()) ON DUPLICATE KEY UPDATE titl` | 1 | 8.692 |
| 2000009 | 20261110205617 | `SELECT VERSION()` | 1 | 1.257 |
| 3000001 | 20261110205621 | `USE `sddctx`` | 0 | 0.576 |
| 3000002 | 20261110205621 | `INSERT INTO sdd_verification (task_id, phase, command, exit_code, passed, failed, log_path, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())` | 1 | 16.623 |
| 4000001 | 20261110205625 | `USE `sddctx`` | 0 | 0.787 |
| 4000002 | 20261110205625 | `INSERT INTO sdd_verification (task_id, phase, command, exit_code, passed, failed, log_path, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())` | 1 | 17.586 |
| 5000001 | 20261110205631 | `USE `sddctx`` | 0 | 0.857 |
| 5000002 | 20261110205631 | `INSERT INTO sdd_verification (task_id, phase, command, exit_code, passed, failed, log_path, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())` | 1 | 15.738 |
| 6000001 | 20261110205633 | `USE `sddctx`` | 0 | 0.706 |
| 6000002 | 20261110205633 | `INSERT INTO sdd_task_progress (task_id, kind, content, origin, created_at) VALUES (%s, %s, %s, %s, NOW())` | 1 | 15.843 |
| 6000003 | 20261110205633 | `INSERT INTO sdd_task_progress (task_id, kind, content, origin, created_at) VALUES (%s, %s, %s, %s, NOW())` | 1 | 7.451 |
| 6000004 | 20261110205633 | `INSERT INTO sdd_task_progress (task_id, kind, content, origin, created_at) VALUES (%s, %s, %s, %s, NOW())` | 1 | 6.357 |
| 6000005 | 20261110205633 | `INSERT INTO sdd_task_progress (task_id, kind, content, origin, created_at) VALUES (%s, %s, %s, %s, NOW())` | 1 | 7.018 |
| 6000006 | 20261110205633 | `INSERT INTO sdd_task_progress (task_id, kind, content, origin, created_at) VALUES (%s, %s, %s, %s, NOW())` | 1 | 5.568 |
| 6000007 | 20261110205633 | `INSERT INTO sdd_task_progress (task_id, kind, content, origin, created_at) VALUES (%s, %s, %s, %s, NOW())` | 1 | 7.062 |
| 6000008 | 20261110205633 | `INSERT INTO sdd_task_progress (task_id, kind, content, origin, created_at) VALUES (%s, %s, %s, %s, NOW())` | 1 | 5.968 |
| 7000001 | 20261110205636 | `USE `sddctx`` | 0 | 0.755 |
| 8000001 | 20261110205638 | `USE `sddctx`` | 0 | 0.843 |
| 9000001 | 20261110205640 | `USE `sddctx`` | 0 | 0.74 |
| 9000002 | 20261110205640 | `SELECT spec_id, title, module, status, body, keywords, related_code, related_tests, source_file, content_hash, revision FROM sdd_spec_item WHERE (title LIKE %s ` | 5 | 7.225 |
| 9000003 | 20261110205640 | `INSERT INTO sdd_retrieval_log (task_id, query_text, target_kind, item_ref, score, sql_text, created_at) VALUES (%s, %s, %s, %s, %s, %s, NOW())` | 5 | 42.789 |
| 9000004 | 20261110205640 | `SELECT file_path, symbol, kind, signature, docstring, line_start, line_end, source_file, content_hash FROM sdd_code_symbol WHERE file_path IN (%s, %s, %s) OR ((` | 8 | 11.472 |
| 9000005 | 20261110205640 | `INSERT INTO sdd_retrieval_log (task_id, query_text, target_kind, item_ref, score, sql_text, created_at) VALUES (%s, %s, %s, %s, %s, %s, NOW())` | 8 | 55.178 |
| 9000006 | 20261110205640 | `SELECT node_id, file_path, test_name, purpose, markers, source_file, content_hash FROM sdd_test_case WHERE file_path IN (%s, %s, %s, %s) OR file_path IN (%s, %s` | 12 | 8.043 |
| 9000007 | 20261110205640 | `INSERT INTO sdd_retrieval_log (task_id, query_text, target_kind, item_ref, score, sql_text, created_at) VALUES (%s, %s, %s, %s, %s, %s, NOW())` | 12 | 82.752 |
| 9000008 | 20261110205640 | `INSERT INTO sdd_task (task_id, title, description, status, created_at, updated_at) VALUES (%s, %s, %s, 'in_progress', NOW(), NOW()) ON DUPLICATE KEY UPDATE titl` | 2 | 10.006 |
| 9000009 | 20261110205640 | `SELECT VERSION()` | 1 | 0.962 |
| 10000001 | 20261110205642 | `USE `sddctx`` | 0 | 0.75 |

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
