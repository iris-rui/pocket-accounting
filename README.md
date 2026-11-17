# 口袋记账 AI — 智能个人财务管家

> 选拔考核选题二：口袋记账 AI 版  
> 技术栈：Vue 3 + FastAPI + MySQL + AI 语义解析

---

## 📋 项目简介

口袋记账 AI 是一款结合自然语言处理（NLP）和数据可视化的个人财务管家。支持手动记账与"一句话记账"AI 智能解析，提供丰富的统计图表和 AI 财务诊断功能。

### ✨ 核心功能

| 功能 | 说明 |
|------|------|
| 📝 手动记账 | 金额、分类、账户、日期、备注，十进制精确存储 |
| 🤖 AI 一句话记账 | 自然语言输入 → AI 自动提取金额/分类/账户/备注 |
| 📊 数据可视化 | 饼图（分类分布）、折线图（月度趋势） |
| 🎯 智能预算 | 月度预算设置、超支预警、进度条展示 |
| 💬 AI 毒舌看板 | AI 分析消费结构，给出"一针见血"的财务建议 |
| 🔢 精度保障 | Decimal 类型杜绝 `0.1 + 0.2 = 0.30000000000000004` |

### 🎯 进阶功能实现

1. **"一句话记账"** — AI 语义解析 ✅
2. **智能预算与"毒舌"看板** — 月度预算 + AI 财务诊断 ✅
3. **浮点数精度** — 全部使用 Python `Decimal` + MySQL `DECIMAL(12,2)` ✅
4. **数据持久化** — MySQL 数据库存储 ✅

---

## 🛠 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 前端框架 | Vue 3 (Composition API) | ^3.5 |
| 构建工具 | Vite | ^6.3 |
| 图表库 | Chart.js | ^4.4 |
| 后端框架 | FastAPI | 0.136 |
| ORM | SQLAlchemy | 2.0 |
| 数据库 | MySQL | — |
| Python | 3.x | — |

---

## 🚀 快速启动

### 1. 环境要求

- Python 3.10+
- Node.js 18+
- MySQL 8.0+

### 2. 数据库配置

```sql
CREATE DATABASE IF NOT EXISTS pocket_accounting
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

默认数据库连接配置（可在 `backend/config.py` 中修改）：
- Host: `localhost`
- Port: `3306`
- User: `root`
- Password: `XXXX`
- Database: `pocket_accounting`

### 3. 后端启动

```bash
cd backend
pip install -r requirements.txt
python main.py
# 服务运行在 http://localhost:8000
# API 文档: http://localhost:8000/docs
```

### 4. 前端启动

```bash
cd frontend
npm install
npm run dev
# 开发服务器运行在 http://localhost:3000
```

### 5. 配置 AI API（可选）

编辑 `backend/config.py` 设置 AI API Key：

```python
AI_API_KEY = "__AI_API_KEY_REMOVED__"
AI_API_BASE = "https://api.deepseek.com"
AI_MODEL = "deepseek-chat"
```

> 💡 不配置 AI API 也能使用！系统会自动降级为本地规则解析，同样可以识别金额、分类和账户。

---

## 📡 API 接口一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/categories` | 获取分类列表 |
| POST | `/api/categories` | 创建分类 |
| GET | `/api/accounts` | 获取账户列表 |
| POST | `/api/accounts` | 创建账户 |
| POST | `/api/transactions` | 手动记账 |
| GET | `/api/transactions` | 流水列表（支持按月/周/分类筛选） |
| DELETE | `/api/transactions/:id` | 删除交易 |
| POST | `/api/ai/parse` | AI 解析记账文本 |
| POST | `/api/ai/parse-and-save` | AI 解析 + 自动保存 |
| POST | `/api/budgets` | 设置月度预算 |
| GET | `/api/budgets` | 获取预算 |
| GET | `/api/budgets/status` | 预算执行状态 |
| GET | `/api/stats/overview` | 月度收支概览 |
| GET | `/api/stats/categories` | 分类统计（饼图） |
| GET | `/api/stats/monthly` | 月度趋势（折线图） |
| GET | `/api/ai/advice` | AI 财务建议 |

完整 Swagger 文档：http://localhost:8000/docs

---

## 📁 项目结构

```
pocket-accounting/
├── backend/
│   ├── main.py          # FastAPI 主应用 + 路由
│   ├── models.py        # SQLAlchemy 数据模型
│   ├── schemas.py       # Pydantic 请求/响应模型
│   ├── crud.py          # 数据库增删改查
│   ├── ai_service.py    # AI 语义解析 + 财务建议
│   ├── config.py        # 配置管理
│   ├── database.py      # 数据库连接
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── main.js
│       ├── App.vue       # 主布局 + 路由
│       ├── api/index.js  # API 请求层
│       ├── assets/style.css
│       └── components/
│           ├── Dashboard.vue       # 仪表盘（概览+图表）
│           ├── TransactionPage.vue # 记账 + AI 解析 + 流水
│           ├── BudgetPanel.vue     # 预算管理
│           └── AIAdvice.vue        # AI 财务看板
├── AI_LOG.md            # AI 协同开发日志
└── README.md
```

---

## 🔒 安全与容错

- **输入校验**：金额范围限制、分类类型白名单、字符串长度限制
- **SQL 注入防护**：SQLAlchemy ORM 参数化查询
- **AI API 容错**：超时 15s，挂掉时自动降级为本地规则解析
- **全局异常捕获**：FastAPI 异常处理器统一拦截
- **CORS 配置**：可配置允许的跨域来源

---

## 📄 License

本项目仅用于选拔考核展示。
