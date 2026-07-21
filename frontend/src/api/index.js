const BASE = '/api'
const TIMEOUT_MS = 8000
async function request(url, options = {}, silent = false) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)

  const config = {
    headers: { 'Content-Type': 'application/json' },
    signal: controller.signal,
    ...options,
  }

  try {
    const resp = await fetch(`${BASE}${url}`, config)
    clearTimeout(timer)

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ message: resp.statusText }))
      const msg = err.message || `请求失败 (${resp.status})`
      if (silent) {
        console.warn(`[API] ${url} → ${msg}`)
        return null
      }
      throw new Error(msg)
    }

    return await resp.json()
  } catch (e) {
    clearTimeout(timer)
    if (e.name === 'AbortError') {
      const msg = '请求超时，请检查后端服务是否启动'
      if (silent) {
        console.warn(`[API] ${url} → ${msg}`)
        return null
      }
      throw new Error(msg)
    }
    // 网络错误（fetch 本身失败）
    if (e instanceof TypeError && e.message.includes('fetch')) {
      const msg = '无法连接后端服务，请确保服务已启动'
      if (silent) {
        console.warn(`[API] ${url} → ${msg}`)
        return null
      }
      throw new Error(msg)
    }
    if (silent) {
      console.warn(`[API] ${url} →`, e.message)
      return null
    }
    throw e
  }
}

// 分类
export async function fetchCategories(type) {
  const params = type ? `?type=${type}` : ''
  return await request(`/categories${params}`, {}, true) || []
}

export function createCategory(data) {
  return request('/categories', { method: 'POST', body: JSON.stringify(data) })
}

// 账户
export async function fetchAccounts() {
  return await request('/accounts', {}, true) || []
}

// 交易
export async function fetchTransactions(params = {}) {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') qs.set(k, v)
  })
  const result = await request(`/transactions?${qs.toString()}`, {}, true)
  return result || { total: 0, items: [], total_income: '0', total_expense: '0' }
}

export function createTransaction(data) {
  return request('/transactions', { method: 'POST', body: JSON.stringify(data) })
}

export function deleteTransaction(id) {
  return request(`/transactions/${id}`, { method: 'DELETE' })
}

// AI 解析
export function aiParse(text) {
  return request('/ai/parse', {
    method: 'POST',
    body: JSON.stringify({ text }),
  })
}

export function aiParseAndSave(text) {
  return request('/ai/parse-and-save', {
    method: 'POST',
    body: JSON.stringify({ text }),
  })
}


// 预算
export async function fetchBudgets(year, month) {
  return await request(`/budgets?year=${year}&month=${month}`, {}, true) || []
}

export async function fetchBudgetStatus(year, month) {
  return await request(`/budgets/status?year=${year}&month=${month}`, {}, true) || []
}

export function createBudget(data) {
  return request('/budgets', { method: 'POST', body: JSON.stringify(data) })
}

// 统计
export async function fetchOverview(year, month) {
  const result = await request(`/stats/overview?year=${year}&month=${month}`, {}, true)
  return result || { total_income: '0', total_expense: '0', balance: '0', transaction_count: 0 }
}

export async function fetchCategoryStats(year, month, type = 'expense') {
  return await request(`/stats/categories?year=${year}&month=${month}&type=${type}`, {}, true) || []
}

export async function fetchMonthlyStats(year) {
  return await request(`/stats/monthly?year=${year}`, {}, true) || []
}

// 财务建议
export async function fetchAIAdvice(year, month) {
  return await request(`/ai/advice?year=${year}&month=${month}`, {}, true) || {}
}
