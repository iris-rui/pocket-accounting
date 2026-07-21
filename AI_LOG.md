# AI 协同开发日志 (AI_LOG.md)

## 1. 工具链 (Toolchain)

### AI 工具
| 工具 | 用途 |
|------|------|
| **Claude Code (claude-opus-4-8)** | 主力开发助手：代码生成、架构设计、Bug 排查、文档撰写 |
| **Claude Code Agent** | 项目结构探索、需求分析 |

### 前端/后端框架
| 层级 | 选型 | 理由 |
|------|------|------|
| 前端 | Vue 3 + Vite + Chart.js | 响应式组件化开发，Vite 构建速度快，Chart.js 成熟稳定 |
| 后端 | FastAPI + SQLAlchemy + PyMySQL | FastAPI 高性能、自动生成 API 文档；SQLAlchemy ORM 防注入 |
| 数据库 | MySQL | 持久化存储，支持 DECIMAL 精确数值类型 |
| AI | DeepSeek API (可配置) | 国产大模型，兼容 OpenAI 接口格式，中文理解能力强 |

---

## 2. 核心 Prompt 展示

### Prompt 1：AI 一句话记账的 System Prompt

这是本项目最核心的 AI Prompt，用于让 LLM 从自然语言中精确提取记账信息。

```
你是一个记账助手，专门从用户的中文自然语言中提取记账信息。

请分析用户输入，提取以下字段并以 JSON 格式返回（只返回 JSON，不要其他内容）：
{
  "type": "expense 或 income",
  "amount": 数字金额（元，保留两位小数），
  "category_name": "分类名称，必须从以下列表中选择最匹配的：餐饮、购物...",
  "account_name": "账户名称，从以下选择：微信、支付宝、现金...",
  "transaction_date": "日期 YYYY-MM-DD",
  "note": "简短的备注说明",
  "confidence": 0.0到1.0之间的置信度
}

规则：
1. 金额可能是 "50块"、"100元"、"七十"、"50.5" 等形式。
2. 分类通过语义推断：吃饭/外卖/食堂→餐饮；打车/地铁→交通...
3. 账户通过关键词推断：微信/微信支付→微信；支付宝→支付宝...
4. 如果无法判断类型，根据语境：花钱→expense，发工资→income。
5. confidence 表示解析可信度，信息越完整越接近 1.0。
```

**成功原因**：
- 明确定义了 JSON Schema 约束输出格式
- 提供了充足的规则示例，覆盖各种口语表达
- 加入了 confidence 字段让用户知道可信度
- 限制了分类和账户的取值空间，避免幻觉

### Prompt 2：AI 财务毒舌顾问

```
你是一个风格犀利的个人财务顾问，名叫"小袋"。你的任务是根据用户的月度消费数据，
给出一针见血的财务点评和建议。

要求：
1. 先用一句话总结本月消费概况。
2. 指出消费中最大的问题或亮点。
3. 给出一条具体的改进建议。
4. 风格：默认"毒舌但有理有据"，让用户意识到问题但不会真的冒犯。
   如果用户当月消费控制得很好，则切换为"温馨表扬"风格。

输出 JSON 格式（只返回 JSON）：
{
  "advice": "完整财务点评（2-4句话）",
  "style": "毒舌 或 温馨",
  "spending_summary": "一句话消费总结"
}
```

**成功原因**：
- 设定了明确的角色和风格约束
- "毒舌但有理有据"的定位精准——既有趣又不冒犯
- 输入中提供了结构化的消费数据，让 LLM 有据可依
- 输出要求 JSON 格式，便于前端展示

---

## 3. Debug 经历

### Bug：Decimal 与 float 隐式转换导致精度丢失

**现象**：
在统计接口中，金额偶尔出现 `50.00000000000001` 这样的浮点数尾数。

**排查过程**：

1. **看日志**：先用 Python print 打印 `func.sum(Transaction.amount)` 的返回值类型，发现是 `float` 而非 `Decimal`。

2. **查源码**：定位到 `crud.py` 中的统计查询：
   ```python
   # ❌ 问题代码
   total_income = income_q.with_entities(func.sum(Transaction.amount)).scalar()
   ```

3. **根因分析**：MySQL 的 `SUM(DECIMAL)` 返回的是 `DECIMAL`，但 SQLAlchemy 在某些情况下会将其转换为 Python `float`，导致精度丢失。

4. **AI 辅助排查**：向 Claude Code 描述了"sum 返回的金额有浮点数尾数"的现象，Claude 指出问题是 SQLAlchemy 的 `func.sum()` 对 DECIMAL 列的返回类型处理不一致，建议用 `func.coalesce(func.sum(...), 0)` 确保类型，并在 Python 端手动转为 Decimal。

5. **修复方案**：
   ```python
   # ✅ 修复后
   raw = income_q.with_entities(func.coalesce(func.sum(Transaction.amount), 0)).scalar()
   total_income = Decimal(str(raw))
   ```

6. **验证**：修复后创建了多条金额为 `0.1`、`0.2`、`0.3` 的交易记录，统计求和结果精确为 `0.60`，浮点尾数消失。

**教训**：
- 涉及货币的场景，Python 侧必须显式使用 `Decimal`，不能用 `float`
- SQLAlchemy 的类型转换不是完全透明的，对 DECIMAL 列需要额外注意
- "浮点数精度灾难"正是考核指南中提到的踩坑点，这个 Bug 的解决印证了项目对精度问题的重视

---

## 4. 开发过程记录

### 整体流程

1. **需求分析** ：阅读《选拔考核指南》PDF，提取选题二的全部需求
2. **架构设计** ：确定 Vue 3 + FastAPI + MySQL 三层架构，设计数据库 ER 模型
3. **后端开发** ：模型 → Schema → CRUD → AI 服务 → 路由，逐层实现
4. **前端开发** ：从纯 HTML 重构为 Vue 3 SFC 组件化架构
5. **集成测试** ：MySQL 建库、种子数据、API 端到端测试、前端 build 验证
6. **文档撰写** ：README + AI_LOG

### AI 协同模式

- **代码生成**：核心业务逻辑（CRUD、AI 解析）由 Claude Code 按设计规范生成
- **代码审查**：生成后逐一检查 Decimal 精度、SQL 安全、异常处理
- **Bug 修复**：上述 Decimal 精度问题通过 AI 辅助排查 + 人工验证解决
- **重构**：前端从原生 HTML 重构为 Vue 3 组件化架构时，AI 批量迁移代码

### 关键决策

- **Decimal 而非 Float**：响应考核指南中"浮点数精度灾难"的踩坑点要求
- **Vue 3 Composition API**：更灵活的逻辑复用，配合 `<script setup>` 语法糖
- **AI 降级策略**：AI API 不可用时自动切换本地规则解析，确保核心功能不中断
- **Chart.js CDN 转 npm**：从 CDN 引入改为 npm 包，配合 Vite tree-shaking 减小打包体积
