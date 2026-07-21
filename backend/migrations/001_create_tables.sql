-- ============================================================
-- 口袋记账 AI — 建表 DDL
-- 导出自 MySQL 8.0，字符集 utf8mb4
-- 执行方式: mysql -u <user> -p <db> < 001_create_tables.sql
-- ============================================================

-- 收支分类表
CREATE TABLE IF NOT EXISTS `categories` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '分类名称',
  `icon` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '图标emoji',
  `type` enum('income','expense') COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '类型: income=收入, expense=支出',
  `is_default` int NOT NULL COMMENT '是否默认分类',
  `sort_order` int NOT NULL COMMENT '排序',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 账户表
CREATE TABLE IF NOT EXISTS `accounts` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '账户名称',
  `icon` varchar(10) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '图标',
  `is_default` int NOT NULL COMMENT '是否默认',
  `sort_order` int NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 交易流水表（核心表）
CREATE TABLE IF NOT EXISTS `transactions` (
  `id` int NOT NULL AUTO_INCREMENT,
  `type` enum('income','expense') COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '类型',
  `amount` decimal(12,2) NOT NULL COMMENT '金额（元），精确到分',
  `category_id` int NOT NULL,
  `account_id` int NOT NULL,
  `transaction_date` date NOT NULL COMMENT '交易日期',
  `note` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '备注',
  `created_at` datetime NOT NULL COMMENT '创建时间',
  `updated_at` datetime NOT NULL COMMENT '更新时间',
  PRIMARY KEY (`id`),
  KEY `category_id` (`category_id`),
  KEY `account_id` (`account_id`),
  KEY `ix_txn_date_type` (`transaction_date`,`type`),
  CONSTRAINT `transactions_ibfk_1` FOREIGN KEY (`category_id`) REFERENCES `categories` (`id`),
  CONSTRAINT `transactions_ibfk_2` FOREIGN KEY (`account_id`) REFERENCES `accounts` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 预算表
CREATE TABLE IF NOT EXISTS `budgets` (
  `id` int NOT NULL AUTO_INCREMENT,
  `year` int NOT NULL COMMENT '年份',
  `month` int NOT NULL COMMENT '月份',
  `amount` decimal(12,2) NOT NULL COMMENT '预算金额',
  `category_id` int DEFAULT NULL COMMENT '为空=总预算，不为空=分类预算',
  `alert_threshold` decimal(5,2) NOT NULL COMMENT '预警阈值（比例），默认0.80即80%时预警',
  `created_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  KEY `category_id` (`category_id`),
  CONSTRAINT `budgets_ibfk_1` FOREIGN KEY (`category_id`) REFERENCES `categories` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
