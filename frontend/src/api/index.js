import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({
  baseURL: '',
  timeout: 60000,
})

http.interceptors.response.use(
  (resp) => {
    const payload = resp.data
    if (payload && typeof payload.code === 'number' && payload.code !== 0) {
      ElMessage.error(payload.message || '请求失败')
      return Promise.reject(payload)
    }
    return payload?.data !== undefined ? payload.data : payload
  },
  (err) => {
    const msg = err?.response?.data?.detail || err.message || '网络错误'
    ElMessage.error(typeof msg === 'string' ? msg : JSON.stringify(msg))
    return Promise.reject(err)
  },
)

export const api = {
  stockDaily: (body) => http.post('/quant/stock/daily', body),
  indexDaily: (body) => http.post('/quant/stock/index/daily', body),
  stockConcept: (body) => http.post('/quant/stock/concept', body),
  stockList: () => http.get('/quant/stock/list'),

  financeIndicator: (body) => http.post('/quant/finance/indicator', body),
  financeIncome: (body) => http.post('/quant/finance/income', body),
  financeBalance: (body) => http.post('/quant/finance/balance', body),
  financeCashflow: (body) => http.post('/quant/finance/cashflow', body),
  financeCompare: (body) => http.post('/quant/finance/compare', body),

  macroList: (body) => http.post('/quant/macro/list', body),
  macroTrend: (body) => http.post('/quant/macro/trend', body),

  newsStock: (body) => http.post('/quant/news/stock', body),
  newsHot: (body) => http.post('/quant/news/hot', body),
  newsDetail: (body) => http.post('/quant/news/detail', body),

  reportList: (body) => http.post('/quant/report/list', body),
  reportDetail: (body) => http.post('/quant/report/detail', body),

  calendarList: (body) => http.post('/quant/calendar/list', body),
  calendarToday: (body) => http.post('/quant/calendar/today', body),

  catalystEvent: (body) => http.post('/quant/catalyst/event', body),
  catalystToday: (body) => http.post('/quant/catalyst/event_today', body),

  crawlTaskList: () => http.post('/quant/crawl/task/list', {}),
  crawlTrigger: (body) => http.post('/quant/crawl/task/trigger', body),
  crawlLog: (body) => http.post('/quant/crawl/task/log', body),
  crawlRetry: (body) => http.post('/quant/crawl/task/retry', body),

  health: () => http.get('/health'),
}

export default http
