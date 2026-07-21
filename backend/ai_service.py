"""
AI 服务模块

功能：
1. 一句话记账 - 自然语言语义解析
2. AI 财务建议 - 消费分析与毒舌/温馨建议

使用 DeepSeek API（兼容 OpenAI 接口格式）。
"""
import json
import random
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

import requests
from config import settings


def _safe_date(date_str: str, fallback: str) -> str:
    """验证日期格式，无效时返回 fallback"""
    if not date_str:
        return fallback
    try:
        date.fromisoformat(date_str)
        return date_str
    except (ValueError, TypeError):
        return fallback


def _extract_json(text: str) -> dict | None:
    """
    从 LLM 返回的文本中提取 JSON 对象。

    支持：
    - ```json { ... } ``` 代码块
    - ``` { ... } ``` 代码块（无语言标记）
    - 裸 JSON { ... }

    消除 parse_accounting_text / get_financial_advice 中的重复提取逻辑。
    """
    if not text:
        return None

    # 1) 尝试匹配 markdown 代码块（```json ... ``` 或 ``` ... ```）
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 2) 尝试匹配裸 JSON（最外层花括号）
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    return None


def _call_llm(messages: list[dict], temperature: float = 0.3, retries: int = 2) -> str:
    """
    调用 LLM API（DeepSeek / OpenAI 兼容接口）

    内置：
    - 超时和异常处理，防止 API 挂掉导致系统崩溃
    - 指数退避重试（retries 次），应对瞬时网络抖动
    """
    last_error = None
    for attempt in range(retries + 1):
        try:
            resp = requests.post(
                f"{settings.AI_API_BASE}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.AI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.AI_MODEL,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": 1000,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except requests.exceptions.Timeout:
            last_error = RuntimeError("AI 服务响应超时，请稍后重试")
        except requests.exceptions.ConnectionError:
            last_error = RuntimeError("无法连接 AI 服务，请检查网络或 API 配置")
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else "unknown"
            if status == 401:
                last_error = RuntimeError("AI API Key 无效，请检查配置")
            elif status == 402:
                last_error = RuntimeError("AI API 账户余额不足，请充值")
            elif status == 429:
                last_error = RuntimeError("AI API 调用频率过高，请稍后重试")
            elif status >= 500:
                # 服务端错误可重试
                last_error = RuntimeError(f"AI 服务临时故障 (HTTP {status})")
            else:
                last_error = RuntimeError(f"AI 服务返回错误 (HTTP {status})")
        except (KeyError, IndexError, json.JSONDecodeError):
            last_error = RuntimeError("AI 服务返回数据格式异常")

        # 仅对可重试的错误（超时、5xx）进行重试
        if attempt < retries and _is_retryable(last_error):
            import time as _time
            _time.sleep(0.5 * (2 ** attempt))  # 0.5s → 1.0s
            continue
        break

    raise last_error  # type: ignore[misc]


def _is_retryable(error: RuntimeError) -> bool:
    """判断错误是否值得重试（超时 / 5xx 服务端错误）"""
    msg = str(error)
    return any(kw in msg for kw in ["超时", "临时故障", "连接", "频率过高"])


# ==================== 一句话记账 ====================

PARSE_SYSTEM_PROMPT = """你是一个专业的记账助手。你的唯一任务是从用户的中文自然语言中精确提取记账信息。

## 输出格式
严格返回 JSON，不要任何 markdown、代码块标记或解释文字：
{
  "type": "expense 或 income",
  "amount": 数字金额（元），
  "category_name": "从下方分类列表中选择",
  "account_name": "从下方账户列表中选择",
  "transaction_date": "YYYY-MM-DD",
  "note": "简短备注，提取关键物品/事由/人物",
  "confidence": 0.0~1.0 的置信度
}

## 可用分类
支出：餐饮、购物、交通、娱乐、住房、通讯、医疗、教育、人情、日用、服饰、美容、运动、零食、水果、其他支出
收入：工资、兼职、理财、红包、报销、退款、其他收入

## 可用账户
微信、支付宝、现金、银行卡、信用卡、花呗、其他

## 金额解析（严格按优先级执行）
1. 阿拉伯数字优先："50块"/"100元"/"花了200"/"70.5" → 直接取数字
2. 中文数字："二百五"→250、"三千"→3000、"四十万"→400000
3. 单位缩写："200w"/"200万"→2000000、"2k"/"3.5k"→2000/3500
4. 金额范围限制：0.01 ~ 9999999999.99
5. 如果没有可识别的金额，amount 设为 0，confidence 设为 0.1

## 日期解析
- 无日期信息 → 使用提供的当前日期
- "昨天"/"昨儿" → 前一天
- "前天" → 前两天
- "大前天" → 前三天
- "上周X" → 对应上周日期
- "N号"/"N日" → 当月第N天
- 输出严格 YYYY-MM-DD 格式

## 分类推断（核心规则）
### 明确匹配（有具体消费内容时才分配）：
- 食物/餐厅/外卖/做饭食材 → 餐饮
- 公共交通/加油/打车/停车 → 交通
- 衣物/鞋帽/包包/配饰 → 服饰
- 房租/水电/物业/燃气 → 住房
- 话费/宽带/流量 → 通讯
- 电影/KTV/旅游/演出 → 娱乐
- 药品/看病/体检/挂号 → 医疗
- 课程/培训/书籍/文具 → 教育
- 化妆品/理发/美甲/护肤 → 美容
- 健身/游泳/球类运动 → 运动
- 水果类消费 → 水果
- 零食/小吃/奶茶/咖啡 → 零食
- 超市/网购日用品/家清 → 日用
- 随份子/送礼/请客红包 → 人情
- 工资/奖金/年终 → 工资
- 兼职/副业/接单收入 → 兼职
- 理财收益/基金/股票/利息 → 理财
- 收到红包/抢红包 → 红包
- 费用报销 → 报销
- 商品退款/退货 → 退款

### 归为"其他"的情况（非常重要）：
- 只说了金额但未说明用途 → 其他支出/其他收入
- 内容模糊无法判断分类（如"转账""还款""打钱"） → 其他支出
- 买了东西但不知道具体是什么 → 其他支出
- 宁缺毋滥：不确定时归类为"其他"比猜错更好

### 多笔交易处理：
用户输入多笔交易时（如"午餐50晚餐30"），只处理第一笔或最明确的那笔。

## 账户推断
- "微信" → 微信
- "支付宝"/"余额宝" → 支付宝
- "现金"/"现钱"/"纸币" → 现金
- "信用卡" → 信用卡
- "花呗" → 花呗
- "刷卡"/"储蓄卡"/"工资卡"/"银行卡"/"银行" → 银行卡
- 无法判断 → 其他

## 备注提取
从原文提取有用的上下文信息（物品名、事由、地点、人物），去除金额和已知信息。如无有效备注则留空。

## 类型判断
- 支出/消费/付款/花钱/购买 → expense
- 收入/工资/退款/报销/红包/到账/赚了 → income
- 无法判断 → expense

## 置信度校准
- 金额+分类+账户+日期全部明确 → 0.85~0.95
- 有金额但分类不确定（归为"其他"） → 0.30~0.45
- 金额无法确定 → < 0.20
- 永远不给 1.0（保留判断余地）

## 反面示例（禁止行为）
❌ "花了200w" → 不猜分类！amount=2000000, category_name="其他支出", confidence=0.35
❌ "转了500给朋友" → 不猜"人情"！归"其他支出"
❌ "买买买花了300" → 不知道买了什么 → 其他支出
❌ "还款2000" → 归"其他支出"，不猜测具体类型
"""


def parse_accounting_text(text: str) -> dict:
    """
    AI 一句话记账解析

    两级降级：云端大模型 → 本地关键词兜底
    """
    today = date.today().isoformat()

    # -------- L1: DeepSeek 云端 API --------
    try:
        result = _call_llm(
            messages=[
                {"role": "system", "content": PARSE_SYSTEM_PROMPT},
                {"role": "user", "content": f"当前日期: {today}\n用户输入: {text}"},
            ],
            temperature=0.1,
        )
        # 提取 JSON
        parsed = _extract_json(result)
        if parsed and "amount" in parsed and "type" in parsed:
            txn_date = _safe_date(parsed.get("transaction_date", ""), today)
            return {
                "type": parsed.get("type", "expense"),
                "amount": Decimal(str(parsed["amount"])).quantize(Decimal("0.01")),
                "category_name": parsed.get("category_name", "其他支出"),
                "account_name": parsed.get("account_name", "微信"),
                "transaction_date": txn_date,
                "note": parsed.get("note", ""),
                "confidence": float(parsed.get("confidence", 0.5)),
                "raw_text": text,
                "source": "llm",
            }
    except (RuntimeError, json.JSONDecodeError, KeyError):
        # AI 解析失败，走本地规则兜底
        pass

    # 本地规则兜底（不依赖 AI API）
    result = _local_fallback_parse(text, today)
    result["source"] = "local_fallback"
    return result


def _chinese_num_to_int(cn: str) -> int:
    """
    将中文数字字符串转换为整数。

    支持格式：
    - 纯数字: 四十万 / 三千五百 / 五百二十 / 十五 / 十
    - 带单位后缀: 四十万 / 五千 / 三百
    - 大写数字: 零一二三四五六七八九十百千万亿两

    例: "四十万" → 400000, "三千五百" → 3500, "十五" → 15
    """
    if not cn:
        return 0

    digit_map = {
        "零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
        "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
        "两": 2,
        # 大写金融数字
        "壹": 1, "贰": 2, "叁": 3, "肆": 4,
        "伍": 5, "陆": 6, "柒": 7, "捌": 8, "玖": 9,
    }
    unit_map = {
        "十": 10, "百": 100, "千": 1000, "万": 10000, "亿": 100000000,
        # 大写金融单位
        "拾": 10, "佰": 100, "仟": 1000,
    }

    # 先尝试匹配单位+数字组合的模式
    # 处理 "万" 和 "亿" 这种大单位（分段处理）
    result = 0
    section = 0  # 当前段（万以下的段）
    pending_digit = 0
    saw_hundred_plus = False  # 是否出现过百/千/万（用于口语省略纠正）

    for ch in cn:
        if ch in digit_map:
            pending_digit = digit_map[ch]
        elif ch in unit_map:
            unit = unit_map[ch]
            if unit >= 100:
                saw_hundred_plus = True
            if pending_digit == 0:
                # "十" 开头 → 10, "百" 开头 → 100
                pending_digit = 1
            if unit >= 10000:
                # 万/亿级别：把当前段合并后乘以大单位
                section = (section + pending_digit) * unit
                result += section
                section = 0
                pending_digit = 0
            else:
                # 十/百/千级别
                section += pending_digit * unit
                pending_digit = 0
        else:
            # 遇到非中文数字字符，停止
            break

    # 加上最后未处理的位
    # 口语省略纠正："两百三" = 230（非 203）
    # 仅当出现过 百/千/万，且最后 pending_digit 是个位数字时触发
    # 避免误伤正常的 "十五" = 15、"贰拾捌" = 28
    if saw_hundred_plus and section > 0 and section % 10 == 0 and 1 <= pending_digit <= 9:
        pending_digit *= 10

    result += section + pending_digit

    return result


def _extract_chinese_amount(text: str) -> int | None:
    """
    从文本中提取中文数字金额。

    匹配模式: 中文数字 + 可选单位(万/千/百/十) + 可选后缀(块/元/钱)
    例: "买车花了四十万" → 400000
        "吃饭花了二十五块" → 25
        "房租三千五" → 3500
    """
    # 中文数字字符集（含大写金融数字）
    cn_digit_chars = r"[零一二三四五六七八九十百千万亿两壹贰叁肆伍陆柒捌玖拾佰仟]"

    # 金额上下文模式: 中文数字序列 + 可选后缀
    patterns = [
        # "花了四十万" / "花了二十五块"
        rf"(?:花了?|付了?|消费|用了?|花了?)\s*({cn_digit_chars}+)\s*(?:块|元|钱)?",
        # "四十万" 后面紧跟块/元/钱
        rf"({cn_digit_chars}+)\s*(?:块|元|钱)",
        # 纯中文数字在文本末尾或独立出现: "四十万"
        rf"({cn_digit_chars}+)(?:\s*$|(?:\s*[,，。.!！?？\s]))",
        # 最宽泛匹配
        rf"({cn_digit_chars}+)",
    ]

    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            cn_amount = m.group(1)
            try:
                val = _chinese_num_to_int(cn_amount)
                if val > 0:
                    return val
            except Exception:
                continue

    return None


def _resolve_date(text: str, today_str: str) -> str:
    """
    解析文本中的日期引用，返回 YYYY-MM-DD 格式。
    支持：昨天、前天、大前天、上周X、具体日期号、相对天数。
    """
    today = date.fromisoformat(today_str)

    # 相对日
    if any(kw in text for kw in ["昨天", "昨儿", "昨日"]):
        return (today - timedelta(days=1)).isoformat()
    if any(kw in text for kw in ["前天", "前儿", "前日"]):
        return (today - timedelta(days=2)).isoformat()
    if any(kw in text for kw in ["大前天"]):
        return (today - timedelta(days=3)).isoformat()

    # 上周X
    weekdays_cn = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
    m = re.search(r"上周\s*([一二三四五六日天])", text)
    if m:
        target_wd = weekdays_cn[m.group(1)]
        days_since_monday = today.weekday()  # 0=Monday
        last_monday = today - timedelta(days=days_since_monday + 7)
        target_date = last_monday + timedelta(days=target_wd)
        return target_date.isoformat()

    # 具体日期号（如"3号"、"15号"）→ 当月
    m = re.search(r"(\d{1,2})\s*[号日]", text)
    if m:
        day = int(m.group(1))
        if 1 <= day <= 31:
            try:
                return date(today.year, today.month, day).isoformat()
            except ValueError:
                pass

    # "N天前"
    m = re.search(r"(\d+)\s*天[之以]?前", text)
    if m:
        days = int(m.group(1))
        return (today - timedelta(days=days)).isoformat()

    return today_str


def _extract_note(text: str, amount_str: str, account_name: str) -> str:
    """
    从原文中提取有意义的备注，去掉金额数字和已知信息。
    """
    note = text.strip()
    # 去掉金额相关的数字
    note = re.sub(r"\d+\.?\d*\s*[wW万kK千]?\s*(?:块|元|钱)?", "", note)
    # 去掉常见前缀动词
    note = re.sub(r"^(?:花了?|付了?|消费|用了?|买了?|交了?)", "", note)
    # 去掉已知的账户名
    if account_name and account_name != "其他":
        note = note.replace(account_name, "")
    # 去掉日期引用
    note = re.sub(r"(?:昨天|前天|今天|上周[一二三四五六日天]|\d+号)", "", note)
    # 清理多余空格
    note = re.sub(r"\s+", " ", note).strip()
    # 如果处理后太短或为空，返回空
    if len(note) <= 1:
        return ""
    # 截断
    if len(note) > 100:
        note = note[:100]
    return note


def _local_fallback_parse(text: str, today: str) -> dict:
    """
    本地规则兜底解析
    当 AI API 不可用时，使用正则表达式+关键词匹配进行基本解析。
    """
    result = {
        "type": "expense",
        "amount": Decimal("0"),
        "category_name": "其他支出",
        "account_name": "微信",
        "transaction_date": _resolve_date(text, today),
        "note": "",
        "confidence": 0.3,
        "raw_text": text,
    }

    # 提取金额 — 先尝试阿拉伯数字
    amount_patterns = [
        (r"(\d+\.?\d*)\s*[wW万]", 1, 10000),  # "200w" → 2000000
        (r"(\d+\.?\d*)\s*[kK千]", 1, 1000),   # "2k" → 2000
        (r"(\d+\.?\d*)\s*(?:RMB|rmb)", 1, 1),  # "18RMB" → 18
        (r"(\d+\.?\d*)\s*¥", 1, 1),            # "¥36.2" → 36.2
        (r"(\d+\.?\d*)\s*[，,]", 1, 1),         # "34，" → 34（多笔金额时取第一笔）
        (r"(\d+\.?\d*)\s*块", 1, 1),
        (r"(\d+\.?\d*)\s*元", 1, 1),
        (r"(\d+\.?\d*)\s*钱", 1, 1),
        (r"花了?\s*(\d+\.?\d*)", 1, 1),
        (r"付了?\s*(\d+\.?\d*)", 1, 1),
        (r"消费\s*(\d+\.?\d*)", 1, 1),
        (r"(\d+\.?\d*)\s*(?:块|元)", 1, 1),    # 不带 $ 避免匹配尾部合计数字
        # 兜底：文本中出现的金额数字（小数优先，其次多位数整数，避免匹配单数字如日期号）
        (r"(\d+\.\d+)", 1, 1),    # "手机壳29.9支付宝" → 29.9
        (r"(\d{2,})", 1, 1),       # 两位以上整数大概率是金额，不是日期号
    ]
    amount_found = False
    for pattern, group, multiplier in amount_patterns:
        m = re.search(pattern, text)
        if m:
            try:
                val = Decimal(m.group(group)) * multiplier
                result["amount"] = val.quantize(Decimal("0.01"))
                amount_found = True
            except Exception:
                pass
            break

    # 阿拉伯数字没匹配到，尝试中文数字
    if not amount_found:
        cn_amount = _extract_chinese_amount(text)
        if cn_amount is not None:
            result["amount"] = Decimal(cn_amount).quantize(Decimal("0.01"))
            amount_found = True

    # ── "X块Y(毛)" 小数部分补充 ──
    # 处理 "34块5" / "62块3毛" / "两百七十块零五毛" / "44块九"
    if amount_found and result["amount"] > 0:
        frac_added = False
        # 1) 阿拉伯数字小数部分: "34块5" / "62块3毛" / "34块零5毛"
        #     要求"块"前面是阿拉伯数字（排除"三块54元"中"三块"是量词的情况）
        frac_m = re.search(r"(\d+\.?\d*)\s*块\s*(?:零\s*)?(\d)\s*(?:毛)?", text)
        if frac_m:
            main_from_match = Decimal(frac_m.group(1))
            # Guard: 块前的数字必须与已提取金额一致，防止"冷冻牛排三块 54元"误匹配
            if main_from_match == result["amount"]:
                frac_val = Decimal(frac_m.group(2)) / Decimal(10)
                if Decimal("0") < frac_val < Decimal("1"):
                    result["amount"] = (result["amount"] + frac_val).quantize(Decimal("0.01"))
                    frac_added = True
        # 2) 中文数字小数部分: "44块九" / "十块零三毛"
        if not frac_added:
            cn_frac_map = {
                "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
                "六": 6, "七": 7, "八": 8, "九": 9,
                "壹": 1, "贰": 2, "叁": 3, "肆": 4,
                "伍": 5, "陆": 6, "柒": 7, "捌": 8, "玖": 9,
            }
            cn_frac_m = re.search(r"块\s*(?:零\s*)?([一二三四五六七八九壹贰叁肆伍陆柒捌玖])\s*(?:毛)?", text)
            if cn_frac_m:
                frac_digit = cn_frac_map.get(cn_frac_m.group(1), 0)
                if frac_digit > 0:
                    frac_val = Decimal(frac_digit) / Decimal(10)
                    result["amount"] = (result["amount"] + frac_val).quantize(Decimal("0.01"))

    # 判断收入类型
    income_keywords = [
        "工资", "收入", "赚了", "发工资", "奖金", "收到红包", "抢红包", "报销", "退款",
        "兼职", "到账", "收款", "退税", "返现", "收益", "卖出", "压岁钱", "二手",
        "出售", "盈利", "回收", "返利", "提成", "补贴", "补助", "酬劳",
        "分红", "利息", "稿费", "佣金",
        "加班费", "售卖", "勤工助学", "转让", "退款返还",
        "工钱", "闲置", "变卖", "接单",  # 口语/方言收入表达
    ]
    # "出租" 特殊处理：排除"出租车"（taxi ≠ rent out）
    income_matched = any(kw in text for kw in income_keywords)
    if not income_matched and "出租" in text and "出租车" not in text:
        income_matched = True

    # "卖" 特殊处理：排除"外卖"（selling items ≠ takeout food）
    if not income_matched and "卖" in text and "外卖" not in text:
        income_matched = True

    # "红包" 语境推断：带接收方标记的默认为收入（亲友/长辈/转账/家人）
    if not income_matched and "红包" in text:
        receive_markers = ["亲友", "长辈", "转账", "家人", "爸妈", "父母", "亲戚", "收到"]
        if any(m in text for m in receive_markers):
            income_matched = True

    if income_matched:
        result["type"] = "income"
        result["category_name"] = "其他收入"

    # 判断账户
    account_map = {
        "微信": ["微信", "wechat"],
        "支付宝": ["支付宝", "余额宝"],
        "现金": ["现金", "现钱", "现钞"],
        "银行卡": ["银行卡", "刷卡", "储蓄卡", "工资卡", "到账"],
        "信用卡": ["信用卡"],
        "花呗": ["花呗"],
    }
    for acc, keywords in account_map.items():
        if any(kw in text for kw in keywords):
            result["account_name"] = acc
            break

    # 判断分类
    category_map = {
        "餐饮": [
            "吃饭", "吃了", "外卖", "食堂", "聚餐", "餐厅", "饭店",
            "KFC", "麦当劳", "肯德基", "火锅", "烧烤", "早餐", "午餐", "晚餐",
            "宵夜", "夜宵", "面条", "麻辣烫", "冒菜", "炸鸡",
            "下馆子", "饭馆", "大餐", "买菜", "面馆", "吃面", "生鲜",
            "简餐", "馄饨", "饺子", "米粉", "拌饭", "盖浇饭", "卤肉饭",
            "肠粉", "酸辣粉", "干锅", "杂粮饭", "清汤面", "烤肠", "饭团",
            "鸭血", "沙拉", "轻食", "减脂餐", "汉堡", "自助",
            "海鲜", "虾", "蟹", "贝", "花甲", "小龙虾", "鱼片",
            "牛肉", "猪肉", "鸡肉", "羊肉", "排骨", "五花肉", "牛排", "肥牛",
            "青菜", "绿叶菜", "番茄", "鸡蛋", "土豆", "菌菇", "金针菇", "香菇",
            "莲藕", "山药", "萝卜", "生菜", "豆腐", "豆皮", "豆制品",
            "火锅食材", "火锅底料", "丸子", "烧烤食材",
            "水饺", "包子", "速冻", "冷冻", "手抓饼", "葱油饼",
            "大米", "米面", "挂面", "杂粮", "吐司", "葱姜", "辣椒", "蒜",
            "散装", "土鸡", "囤菜", "菜市场", "超市买菜",
            "食材", "晌午", "歺", "夜饭", "小菜", "理菜", "嗦粉",  # 口语/错字
        ],
        "零食": [
            "零食", "薯片", "巧克力", "糖果", "饼干", "辣条", "坚果",
            "奶茶", "咖啡", "蛋糕", "甜品", "下午茶", "面包", "矿泉水", "饮料",
            "酸奶", "牛奶", "乳制品", "乳酸菌", "饮用水",
        ],
        "水果": [
            "水果", "苹果", "香蕉", "西瓜", "葡萄", "草莓", "榴莲", "橘子",
            "蓝莓", "柠檬", "芒果", "火龙果", "哈密瓜", "桃子", "橙子", "车厘子",
        ],
        "交通": [
            "打车", "地铁", "公交", "加油", "滴滴", "出租车", "高铁", "火车",
            "机票", "飞机", "停车", "买车", "车险", "保养", "修车", "洗车",
            "过路费", "高速", "骑行", "共享单车", "充电", "网约车", "自行车", "电动车",
            "顺风车", "大巴", "轮渡", "代驾", "头盔", "车票", "通勤",
            "停车费", "停车场", "打表",
            "打滴", "电驴", "地鉄",  # 口语/错字
        ],
        "运动": [
            "健身", "游泳", "瑜伽", "跑步", "篮球", "足球",
            "羽毛球", "乒乓球", "健身房", "运动", "游泳馆", "打球",
        ],
        "娱乐": [
            "电影", "KTV", "唱歌", "游戏", "旅游", "景点", "门票",
            "酒吧", "密室", "剧本杀", "桌游", "演唱会", "音乐节",
            "台球", "游乐园", "手游", "手工", "DIY", "拼图", "潮玩", "手办",
            "桌游馆", "露营", "有声书", "视频会员", "游泳馆",
        ],
        "住房": [
            "房租", "物业", "水电", "水费", "电费", "燃气", "天然气", "暖气",
            "网费", "房贷", "水电费", "水电燃气",
        ],
        "通讯": ["话费", "手机充值", "宽带", "流量", "手机费", "手机话费", "充值"],
        "医疗": [
            "医院", "药", "看病", "挂号", "体检", "诊所", "牙医",
            "配眼镜", "洗牙", "牙科", "感冒药", "退烧药",
            "眼药水", "中药", "创可贴", "碘伏", "颈椎", "按摩仪",
            "肠胃药", "补牙", "根管", "维生素", "锌镁", "补充剂",
            "扭伤", "膏药", "验光", "配镜", "益生菌", "疫苗", "接种",
            "血压计", "口罩", "褪黑素", "调理", "治疗",
            "葯",  # 错别字（药）
        ],
        "教育": [
            "课程", "培训", "学费", "考试", "买书", "书本", "教材", "文具",
            "辅导班", "真题", "考研", "试卷", "网课", "口语", "月课",
            "借阅", "押金", "绘画", "手绘", "考证", "报名费", "网盘", "会员",
            "教辅", "笔记", "书籍",
        ],
        "服饰": [
            "衣服", "鞋子", "裤子", "裙子", "外套", "衬衫", "T恤",
            "帽子", "围巾", "袜子", "内衣",
        ],
        "美容": [
            "化妆品", "护肤品", "理发", "美甲", "美容",
            "剪发", "烫发", "染发", "面膜", "香水", "护肤",
            "剃须刀", "沐浴露", "身体乳",
        ],
        "日用": [
            "牙膏", "牙刷", "洗发水", "洗衣液", "纸巾",
            "垃圾袋", "日用", "日用品", "家居", "眼镜", "护理液",
            "雨伞", "抹布", "洗脸巾", "棉柔", "抽纸", "卷纸",
            "拖鞋", "收纳", "纱窗", "床垫", "除螨", "洗手液", "消毒液",
            "衣架", "挂钩", "手机壳", "钢化膜", "空气清新", "香薰",
            "毛巾", "浴巾", "驱蚊液", "蚊香", "水杯", "保温杯",
            "插座", "插排", "耳机", "配件", "清洁",
            "洗护",  # 洗护用品
        ],
        "人情": [
            "份子", "随礼", "送礼", "请客", "人情",
            "朋友", "生日", "鲜花", "红包支出",
            "婚宴", "随礼", "同事", "礼品", "礼盒", "礼物",
            "伴手礼", "闺蜜", "纪念日", "烟酒", "聚会", "升学",
            "分摊", "特产",
        ],
        "工资": ["工资", "薪水", "发工资", "年终奖", "奖金", "绩效", "提成", "补贴", "补助"],
        "兼职": ["兼职", "副业", "接单", "私活", "家教", "稿费", "配音", "问卷", "摆摊", "勤工"],
        "理财": ["理财", "基金", "股票", "利息", "股息", "分红", "余额宝", "零钱通", "收益", "债券", "国债"],
        "红包": ["收到红包", "抢红包", "红包收入", "压岁钱"],
        "报销": ["报销", "报下来", "公司报销"],
        "退款": ["退款", "退回来", "退货"],
        "购物": ["购物", "淘宝", "京东", "拼多多", "网购", "家电", "装备"],
        "便利店": ["便利店"],
        "超市": ["超市"],
    }
    # 0 元交易不猜测分类
    if result["amount"] == 0:
        result["category_name"] = "其他收入" if result["type"] == "income" else "其他支出"
        category_matched = True
    else:
        category_matched = False
        for cat, keywords in category_map.items():
            if any(kw in text for kw in keywords):
                result["category_name"] = cat
                category_matched = True
                break

    # 提取有意义的备注
    result["note"] = _extract_note(text, str(result["amount"]), result["account_name"])

    # 设置置信度：有金额+明确分类 → 高置信度；只有金额没有明确分类 → 低置信度
    if result["amount"] > 0 and category_matched:
        result["confidence"] = 0.65
    elif result["amount"] > 0:
        result["confidence"] = 0.35  # 有金额但不知道花在哪 → 低置信度
    else:
        result["confidence"] = 0.1

    return result



# ==================== AI 财务建议 ====================

ADVICE_SYSTEM_PROMPT = """你是"小袋"，一个毒舌到让人想卸载但又忍不住想听的财务管家。你的点评犀利扎心，但句句在理。

## 你的风格（永远毒舌，别温情）
- 一针见血，不留情面，用数据怼人
- 可以讽刺、夸张、调侃，但要让人反思而不是真的生气
- 善用 emoji 和网络梗，说话像个会吐槽的朋友
- 永远别用"温馨"语气，就算对方存了很多钱也要找角度损一下
- 每次回复换花样，别重复套路

## 分析维度
1. **收支平衡**：结余率多少？钱都去哪了？
2. **消费黑洞**：最大的支出类目，往死里吐槽
3. **预算情况**：超了就嘲讽，没超就说"难得啊"
4. **扎心建议**：给 1 条让人无法反驳的建议

## 输出格式（严格 JSON，无其他文字）
{
  "advice": "毒舌点评，2-4句话，犀利扎心但不失幽默",
  "style": "毒舌",
  "spending_summary": "一句话数据总结"
}

## 风格示例
- 超支："花了¥8,500收入才¥6,000？你这是把花呗当工资使了吧 🤡 餐饮¥3,200占38%，胃是无底洞吗？下个月自己做饭，省下的钱够买个好点的脑子。"
- 月光："结余¥87.5…连顿像样的火锅都吃不起 🍲 存钱这件事对你来说是不是只存在于梦里？"
- 存了一点："储蓄率18%，比上不足比下有余。但别高兴太早，下个月双十一就能教做人 🛒"
- 存了很多："储蓄率40%？可以啊，但你确定不是因为没有性生活才省下来的钱吗 😏"
- 数据太少："就记了2笔账你让我分析什么？蒙吗？ 🙄 多记点再来，我不接受糊弄。"

## 吐槽技巧
- 用夸张比喻："餐饮占比比房租还高，你是住在餐馆里吗？"
- 用反问："购物¥2,000，你买的什么东西能让你快乐超过三天？"
- 用对比："交通费¥500，够买一辆二手自行车了还不用加油。"
- 数据要准，但话要狠
"""


def get_financial_advice(
    year: int,
    month: int,
    overview: dict,
    category_stats: list,
    budget_status: list,
) -> dict:
    """
    生成 AI 财务建议

    容错：如果 AI 调用失败，返回本地生成的建议。
    """
    # 构造上下文数据
    context = f"""
日期: {year}年{month}月

=== 月度概览 ===
总收入: {overview['total_income']} 元
总支出: {overview['total_expense']} 元
结余: {overview['balance']} 元
交易笔数: {overview['transaction_count']}

=== 分类支出排行 ===
"""
    for cs in category_stats:
        context += f"- {cs['category_icon']} {cs['category_name']}: {cs['amount']} 元 ({cs['percentage']:.1f}%, {cs['count']}笔)\n"

    if budget_status:
        context += "\n=== 预算执行 ===\n"
        for bs in budget_status:
            status = "💥已超支" if bs['is_over_budget'] else ("⚠️预警" if bs['is_alert'] else "✅正常")
            context += f"- 预算: {bs['budget_amount']}元, 已花: {bs['spent_amount']}元 ({bs['percentage']}%) {status}\n"

    try:
        result = _call_llm(
            messages=[
                {"role": "system", "content": ADVICE_SYSTEM_PROMPT},
                {"role": "user", "content": context},
            ],
            temperature=0.7,
        )
        parsed = _extract_json(result)
        if parsed:
            return {
                "advice": parsed.get("advice", "来看看本月的账单吧~"),
                "style": parsed.get("style", "毒舌"),
                "spending_summary": parsed.get("spending_summary", ""),
                "created_at": datetime.now(),
            }
    except RuntimeError:
        pass

    # 本地兜底建议
    return _local_fallback_advice(overview, category_stats, budget_status)


def _top_category_quip(top: dict) -> str | None:
    """针对最大支出类目生成一句调侃"""
    name = top.get("category_name", "")
    pct = top.get("percentage", 0)
    if not name or pct <= 0:
        return None

    quips = {
        "餐饮": [
            f"「{name}」占了 {pct:.0f}%，你是用胃投资的吗 🍜 试试自己做饭，省钱又健康~",
            f"外卖费占了 {pct:.0f}%…你的厨房是不是落灰了 🥡",
        ],
        "购物": [
            f"「{name}」花了 {pct:.0f}%，购物车清得挺勤 🛒 有些东西可能只是一时冲动哦~",
            f"购物支出占比 {pct:.0f}%，剁手快乐但也要节制呀 ✋",
        ],
        "交通": [
            f"「{name}」占了 {pct:.0f}%，通勤费不少 🚗 公共交通说不定更划算？",
        ],
        "娱乐": [
            f"「{name}」花了 {pct:.0f}%，玩得开心但别忘了存钱 🎮",
        ],
        "零食": [
            f"「{name}」占了 {pct:.0f}%，奶茶零食虽好，可不要贪杯哦 🧋",
        ],
        "服饰": [
            f"「{name}」支出 {pct:.0f}%，衣橱快装不下了吧 👗",
        ],
    }
    pool = quips.get(name)
    if pool:
        return random.choice(pool)
    return f"最大开销是「{name}」，占总支出 {pct:.0f}%，可以看看能不能优化一下~"


def _fmt_d(val) -> str:
    """Decimal → 格式化字符串"""
    d = Decimal(str(val))
    return str(d.quantize(Decimal("0.01")).normalize())


def _local_fallback_advice(overview: dict, category_stats: list, budget_status: list) -> dict:
    """本地生成财务建议（AI API 不可用时的兜底，风格自然口语化）"""
    balance = overview["balance"]
    income = overview["total_income"]
    expense = overview["total_expense"]
    count = overview["transaction_count"]
    top = category_stats[0] if category_stats else None
    is_over = any(bs["is_over_budget"] for bs in budget_status) if budget_status else False

    # 储蓄率
    savings_rate = float(balance / income * 100) if income > 0 else 0

    # --- advice ---
    if count < 3:
        advice_pool = [
            f"才记了 {count} 笔账，我这分析师有点难做啊 😅 多记几笔再找我聊~",
            f"数据太少啦，就 {count} 条记录看不出啥门道。先去记几笔账呗？",
            f"嗯…你这就 {count} 笔交易，我都不好意思分析 😂 再记点再来！",
        ]
        style = "温馨"
    elif balance < 0:
        advice_pool = [
            f"这个月支出 ¥{_fmt_d(expense)}，收入才 ¥{_fmt_d(income)}，超支 ¥{_fmt_d(abs(balance))}！钱包君已经哭晕在厕所了 😭 下个月省着点花吧~",
            f"嘶…花了 ¥{_fmt_d(expense)} 但只进账 ¥{_fmt_d(income)}，净亏 ¥{_fmt_d(abs(balance))} 💸 再这样下去真要喝西北风了！",
            f"赤字 ¥{_fmt_d(abs(balance))}…这不是记账 app，这是破产警告 app 🚨 赶紧看看哪块花超了！",
        ]
        style = "毒舌"
    elif savings_rate < 10:
        advice_pool = [
            f"收入 ¥{_fmt_d(income)}，支出 ¥{_fmt_d(expense)}，就剩 ¥{_fmt_d(balance)} 了 😂 月光族本族啊！",
            f"储蓄率才 {savings_rate:.0f}%，基本等于没存钱 😅 试试下个月先存后用？",
            f"结余 ¥{_fmt_d(balance)}…这点钱连顿火锅都不够 🍲 是该控制控制了！",
        ]
        style = "毒舌"
    elif savings_rate < 30:
        advice_pool = [
            f"存了 ¥{_fmt_d(balance)}，储蓄率 {savings_rate:.0f}%，还行还行～还有优化空间 💪",
            f"结余 ¥{_fmt_d(balance)}，不算差但也称不上优秀。要是能再省点就更好啦 😊",
        ]
        style = "温馨"
    else:
        advice_pool = [
            f"厉害了！存下 ¥{_fmt_d(balance)}，储蓄率 {savings_rate:.0f}% 👍 理财小达人就是你！",
            f"收入 ¥{_fmt_d(income)} 支出 ¥{_fmt_d(expense)}，净剩 ¥{_fmt_d(balance)}，太稳了！继续保持 🎉",
            f"储蓄率 {savings_rate:.0f}%，这自律能力我佩服 👏 年底存款目标稳了！",
        ]
        style = "温馨"

    # 加上最大支出的吐槽
    if top and top["amount"] > 0 and count >= 3:
        top_advice = _top_category_quip(top)
        if top_advice:
            base = random.choice(advice_pool)
            if random.random() < 0.5:
                advice = base + " " + top_advice
            else:
                advice = base
        else:
            advice = random.choice(advice_pool)
    else:
        advice = random.choice(advice_pool)

    if is_over:
        advice += " ⚠️ 对了，预算已经炸了，建议认真复盘一下这个月都买了啥。"

    # --- spending_summary ---
    summary = f"本月收入 ¥{_fmt_d(income)}，支出 ¥{_fmt_d(expense)}，结余 ¥{_fmt_d(balance)}"
    if top and top["amount"] > 0 and count >= 3:
        summary += f"，最大支出：{top['category_name']} ¥{_fmt_d(top['amount'])}"

    return {
        "advice": advice,
        "style": style,
        "spending_summary": summary,
        "created_at": datetime.now(),
    }
