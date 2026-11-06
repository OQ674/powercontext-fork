-- =============================================================
-- 记仇酒馆 · seekdb 初始化脚本
-- 适用：OceanBase seekdb（MySQL 兼容模式），Docker 镜像 oceanbase/seekdb
-- 用法：
--   mysql -h127.0.0.1 -P2881 -uroot -p < seed/00_schema.sql
-- 说明：
--   1) props           —— 世界道具库：向量索引 + 全文索引（IK 中文分词）+ 结构化字段
--   2) revenge_plans   —— 老陈的报复剧本库：按记仇区间做结构化筛选，再按语义挑选
--   3) players         —— 玩家档案：Dify 的 sys.user_id 与 PowerContext scope_id 的映射
--   4) player_state    —— 当前局状态：记仇值 / 心情 / 回合数 / 是否已触发结局
--   5) turn_log        —— 每回合流水：用于复盘、证据与统计
-- NOTE: 向量维度为 1024，需与 seed/load_seed.py 使用的 Embedding 模型维度一致。
-- =============================================================

CREATE DATABASE IF NOT EXISTS tavern DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;
USE tavern;

DROP TABLE IF EXISTS turn_log;
DROP TABLE IF EXISTS player_state;
DROP TABLE IF EXISTS players;
DROP TABLE IF EXISTS revenge_plans;
DROP TABLE IF EXISTS props;

-- -------------------------------------------------------------
-- 1. 道具库
--    seekdb 限制（V1.4.0 实测）：声明了 PRIMARY KEY 的表无法被
--    DBMS_HYBRID_SEARCH 检索（报 1235），因此这里不声明主键，
--    改用 (id, name) 唯一索引保证 id 唯一。
-- -------------------------------------------------------------
CREATE TABLE props (
    id          INT           NOT NULL COMMENT '道具 id',
    name        VARCHAR(64)   NOT NULL COMMENT '道具名',
    category    VARCHAR(32)   NOT NULL COMMENT '类别：调料/食材/容器/电器/玩具/清洁/活物/雨具/物件/小道具',
    scene       VARCHAR(32)   NOT NULL COMMENT '场景：bar 吧台 / kitchen 后厨 / storeroom 储物间',
    danger      TINYINT       NOT NULL DEFAULT 0 COMMENT '危险度 0-2，越高越容易出事',
    mess        TINYINT       NOT NULL DEFAULT 0 COMMENT '混乱度 0-3，越高越难收拾',
    description VARCHAR(512)  NOT NULL COMMENT '给模型看的客观描述',
    tags        VARCHAR(255)  NOT NULL DEFAULT '' COMMENT '喜剧标签，逗号分隔',
    search_text VARCHAR(1024) NOT NULL COMMENT '混合检索用拼接文本',
    embedding   VECTOR(1024)  DEFAULT NULL COMMENT '语义向量，维度需与 Embedding 模型一致',
    UNIQUE KEY uk_props_id (id, name),
    VECTOR INDEX idx_props_vec (embedding) WITH (distance = cosine, type = hnsw, lib = vsag),
    FULLTEXT INDEX idx_props_ft (search_text) WITH PARSER ik PARSER_PROPERTIES = (ik_mode = "max_word")
);

-- -------------------------------------------------------------
-- 2. 报复剧本库（老陈真的会照着做）
-- -------------------------------------------------------------
CREATE TABLE revenge_plans (
    id          INT           NOT NULL,
    band_min    INT           NOT NULL COMMENT '记仇区间下限（含）',
    band_max    INT           NOT NULL COMMENT '记仇区间上限（含）',
    title       VARCHAR(64)   NOT NULL,
    plan        VARCHAR(1024) NOT NULL COMMENT '可被 NPC 直接执行的报复动作',
    prop_hint   VARCHAR(64)   NOT NULL DEFAULT '' COMMENT '涉及道具',
    tags        VARCHAR(255)  NOT NULL DEFAULT '',
    search_text VARCHAR(1024) NOT NULL,
    embedding   VECTOR(1024)  DEFAULT NULL,
    UNIQUE KEY uk_plans_id (id, title),
    VECTOR INDEX idx_plans_vec (embedding) WITH (distance = cosine, type = hnsw, lib = vsag),
    FULLTEXT INDEX idx_plans_ft (search_text) WITH PARSER ik PARSER_PROPERTIES = (ik_mode = "max_word")
);

-- -------------------------------------------------------------
-- 3. 玩家档案：user_id -> PowerContext scope
-- -------------------------------------------------------------
CREATE TABLE players (
    user_id          VARCHAR(128) NOT NULL COMMENT 'Dify sys.user_id',
    scope_id         VARCHAR(128) NOT NULL DEFAULT '' COMMENT 'PowerContext scope_id',
    scope_generation INT          NOT NULL DEFAULT 1 COMMENT '重置次数，重置会新建 scope',
    created_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id)
);

-- -------------------------------------------------------------
-- 4. 当前局状态（seekdb 是权威账本；PowerContext 管叙事记忆）
-- -------------------------------------------------------------
CREATE TABLE player_state (
    user_id    VARCHAR(128) NOT NULL,
    grudge     INT          NOT NULL DEFAULT 0 COMMENT '记仇值 0-100',
    mood       INT          NOT NULL DEFAULT 60 COMMENT '老陈心情 0-100',
    turn_no    INT          NOT NULL DEFAULT 0 COMMENT '已进行回合数',
    ending     TINYINT      NOT NULL DEFAULT 0 COMMENT '是否已触发结局',
    updated_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id)
);

-- -------------------------------------------------------------
-- 5. 回合流水
-- -------------------------------------------------------------
CREATE TABLE turn_log (
    id          BIGINT       NOT NULL AUTO_INCREMENT,
    user_id     VARCHAR(128) NOT NULL,
    turn_no     INT          NOT NULL,
    action      VARCHAR(1024) NOT NULL DEFAULT '' COMMENT '玩家原话',
    reply       VARCHAR(2048) NOT NULL DEFAULT '' COMMENT '老陈的回复',
    ledger      VARCHAR(255)  NOT NULL DEFAULT '' COMMENT '本轮记在账上的一句话',
    prop_used   VARCHAR(64)   NOT NULL DEFAULT '',
    grudge_after INT          NOT NULL DEFAULT 0,
    mood_after   INT          NOT NULL DEFAULT 60,
    ending       TINYINT      NOT NULL DEFAULT 0,
    created_at   TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_turn_user (user_id, turn_no)
);

-- -------------------------------------------------------------
-- 自检（可选）：确认索引已建好
-- -------------------------------------------------------------
-- SHOW INDEX FROM props;
-- SELECT COUNT(*) FROM props;
