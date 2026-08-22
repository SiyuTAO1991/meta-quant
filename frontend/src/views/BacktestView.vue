<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2>策略回测</h2>
        <p>基于已采集日线数据，使用 Backtrader 运行内置策略；数据不足时将自动触发采集</p>
      </div>
      <div class="toolbar">
        <el-button type="primary" :loading="running" @click="runBacktest">开始回测</el-button>
      </div>
    </div>

    <div class="panel">
      <el-form :model="form" label-width="100px" class="bt-form">
        <el-row :gutter="16">
          <el-col :xs="24" :md="8">
            <el-form-item label="策略">
              <el-select
                v-model="form.strategy_key"
                placeholder="选择策略"
                style="width: 100%"
                @change="onStrategyChange"
              >
                <el-option
                  v-for="item in strategies"
                  :key="item.strategy_key"
                  :label="item.strategy_name"
                  :value="item.strategy_key"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="股票代码">
              <el-input
                v-model="form.ts_code"
                placeholder="如 600519.SH，多只用逗号分隔"
                clearable
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="回测区间">
              <el-date-picker
                v-model="form.range"
                type="daterange"
                value-format="YYYY-MM-DD"
                start-placeholder="开始"
                end-placeholder="结束"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :xs="24" :md="8">
            <el-form-item label="初始资金">
              <el-input-number v-model="form.cash" :min="1000" :step="10000" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="佣金费率">
              <el-input-number
                v-model="form.commission"
                :min="0"
                :max="0.01"
                :step="0.0001"
                :precision="4"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="印花税">
              <el-switch v-model="form.enable_stamp_tax" active-text="开启" inactive-text="关闭" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row v-if="paramTemplate.length" :gutter="16">
          <el-col v-for="p in paramTemplate" :key="p.param_name" :xs="24" :md="8">
            <el-form-item :label="p.param_label">
              <el-input-number
                v-model="form.strategy_params[p.param_name]"
                :min="p.min"
                :max="p.max"
                :step="1"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="策略描述">
          <el-input
            v-model="strategyDesc"
            type="textarea"
            :rows="2"
            readonly
            resize="none"
            placeholder="请选择策略后查看描述"
          />
        </el-form-item>
      </el-form>
    </div>

    <div v-if="report" class="panel report-meta">
      <div class="report-meta-item">
        <span class="muted">策略参数</span>
        <strong>{{ formatStrategyParams(report.strategy_params) }}</strong>
      </div>
      <div class="report-meta-item">
        <span class="muted">成交规则</span>
        <strong>交叉信号当日收盘确认，下一交易日开盘成交</strong>
      </div>
      <div class="report-meta-item">
        <span class="muted">收益构成</span>
        <strong>总收益含已实现盈亏与期末持仓浮动盈亏</strong>
      </div>
    </div>

    <div v-if="report" class="metrics">
      <div class="metric-card">
        <div class="metric-label">总收益率</div>
        <div class="metric-value" :class="pctClass(report.total_return)">
          {{ fmtPct(report.total_return) }}
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-label">年化收益</div>
        <div class="metric-value" :class="pctClass(report.annual_return)">
          {{ fmtPct(report.annual_return) }}
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-label">已实现盈亏</div>
        <div class="metric-value" :class="pctClass(report.realized_pnl / (report.initial_cash || 1))">
          {{ fmtMoney(report.realized_pnl) }}
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-label">浮动盈亏</div>
        <div class="metric-value" :class="pctClass(report.unrealized_pnl / (report.initial_cash || 1))">
          {{ fmtMoney(report.unrealized_pnl) }}
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-label">最大回撤</div>
        <div class="metric-value down">{{ fmtPct(report.max_drawdown) }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">夏普比率</div>
        <div class="metric-value">{{ fmtNum(report.sharpe) }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">胜率</div>
        <div class="metric-value">{{ fmtPct(report.win_rate) }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">盈亏比</div>
        <div class="metric-value">{{ fmtNum(report.profit_loss_ratio) }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">交易次数</div>
        <div class="metric-value">{{ report.trade_count ?? 0 }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">期末资产</div>
        <div class="metric-value">{{ fmtMoney(report.final_value) }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">买入持有</div>
        <div class="metric-value" :class="pctClass(report.benchmark_return)">
          {{ fmtPct(report.benchmark_return) }}
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-label">利润因子</div>
        <div class="metric-value">{{ fmtNum(report.profit_factor) }}</div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-title">净值 / 回撤曲线</div>
      <v-chart v-if="curveOption" class="chart-box" :option="curveOption" autoresize />
      <el-empty v-else description="运行回测后展示净值与回撤曲线" />
    </div>

    <div v-if="report?.open_positions?.length" class="panel">
      <div class="panel-title">期末持仓（未平仓）</div>
      <p class="muted panel-hint">以下持仓在回测结束日仍未卖出，其浮动盈亏已计入总收益</p>
      <el-table :data="report.open_positions" stripe>
        <el-table-column prop="stock_code" label="标的" width="120" />
        <el-table-column prop="buy_signal_date" label="买入信号日" width="110" />
        <el-table-column prop="buy_date" label="买入成交日" width="110" />
        <el-table-column prop="avg_price" label="成本价" width="100" />
        <el-table-column prop="last_price" label="期末价" width="100" />
        <el-table-column prop="volume" label="股数" width="90" />
        <el-table-column prop="market_value" label="市值" width="110" />
        <el-table-column prop="unrealized_pnl" label="浮动盈亏" width="110">
          <template #default="{ row }">
            <span :class="pctClass(row.unrealized_pnl)">{{ fmtMoney(row.unrealized_pnl) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="panel">
      <div class="panel-title">交易明细（已平仓）</div>
      <el-table :data="report?.trade_logs || []" height="320" stripe>
        <el-table-column prop="trade_id" label="ID" width="70" />
        <el-table-column prop="stock_code" label="标的" width="110" />
        <el-table-column prop="buy_signal_date" label="买入信号日" width="110" />
        <el-table-column prop="buy_date" label="买入成交日" width="110" />
        <el-table-column prop="buy_price" label="买入价" width="90" />
        <el-table-column prop="sell_signal_date" label="卖出信号日" width="110" />
        <el-table-column prop="sell_date" label="卖出成交日" width="110" />
        <el-table-column prop="sell_price" label="卖出价" width="90" />
        <el-table-column prop="pnl" label="盈亏" width="110">
          <template #default="{ row }">
            <span :class="pctClass(row.pnl)">{{ fmtNum(row.pnl) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="pnlcomm" label="净盈亏" width="110">
          <template #default="{ row }">
            <span :class="pctClass(row.pnlcomm)">{{ fmtNum(row.pnlcomm) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { api } from '@/api'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent])

const strategies = ref([])
const paramTemplate = ref([])
const strategyDesc = ref('')
const running = ref(false)
const report = ref(null)
const curveOption = ref(null)

const form = reactive({
  strategy_key: '',
  ts_code: '600519.SH',
  range: [dayjs().subtract(2, 'year').format('YYYY-MM-DD'), dayjs().format('YYYY-MM-DD')],
  cash: 100000,
  commission: 0.0003,
  enable_stamp_tax: true,
  strategy_params: {},
})

function fmtPct(v) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '--'
  return `${(Number(v) * 100).toFixed(2)}%`
}

function fmtNum(v) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '--'
  return Number(v).toFixed(2)
}

function fmtMoney(v) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '--'
  return Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

function pctClass(v) {
  const n = Number(v)
  if (Number.isNaN(n) || n === 0) return ''
  return n > 0 ? 'up' : 'down'
}

function applyParamDefaults(template) {
  const params = {}
  for (const p of template || []) {
    params[p.param_name] = p.default_value
  }
  form.strategy_params = params
}

function buildStrategyParams() {
  const params = {}
  for (const p of paramTemplate.value || []) {
    const val = form.strategy_params[p.param_name]
    params[p.param_name] = val ?? p.default_value
  }
  return params
}

function formatStrategyParams(params) {
  if (!params || !Object.keys(params).length) return '--'
  return Object.entries(params)
    .map(([k, v]) => `${k}=${v}`)
    .join('，')
}

async function onStrategyChange(key) {
  if (!key) return
  const detail = await api.strategyDetail({ strategy_key: key })
  paramTemplate.value = detail?.param_template || []
  strategyDesc.value = detail?.strategy_desc || ''
  applyParamDefaults(paramTemplate.value)
}

function buildCurveOption(data) {
  const equity = data?.equity_curve || []
  const drawdown = data?.drawdown_curve || []
  if (!equity.length) {
    curveOption.value = null
    return
  }
  const dates = equity.map((i) => i.date)
  const eqSeries = equity.map((i) => i.equity)
  const ddMap = Object.fromEntries(drawdown.map((i) => [i.date, i.drawdown]))
  const ddSeries = dates.map((d) => {
    const v = ddMap[d]
    return v === undefined ? null : Number((v * 100).toFixed(4))
  })

  curveOption.value = {
    animation: false,
    tooltip: { trigger: 'axis' },
    legend: { data: ['净值', '回撤%'] },
    grid: [
      { left: 56, right: 24, top: 40, height: '48%' },
      { left: 56, right: 24, top: '68%', height: '22%' },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], start: 0, end: 100, bottom: 8 },
    ],
    xAxis: [
      { type: 'category', data: dates, boundaryGap: false, axisLabel: { show: false } },
      { type: 'category', data: dates, gridIndex: 1, boundaryGap: false },
    ],
    yAxis: [
      { type: 'value', scale: true, name: '净值' },
      { type: 'value', scale: true, gridIndex: 1, name: '回撤%', axisLabel: { formatter: '{value}%' } },
    ],
    series: [
      {
        name: '净值',
        type: 'line',
        data: eqSeries,
        showSymbol: false,
        lineStyle: { width: 2, color: '#0f766e' },
        areaStyle: { color: 'rgba(15, 118, 110, 0.12)' },
      },
      {
        name: '回撤%',
        type: 'line',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: ddSeries,
        showSymbol: false,
        lineStyle: { width: 1.5, color: '#b91c1c' },
        areaStyle: { color: 'rgba(185, 28, 28, 0.12)' },
      },
    ],
  }
}

function parseStockCodes(text) {
  return (text || '')
    .split(/[,，\s]+/)
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean)
}

async function runBacktest() {
  if (!form.strategy_key) {
    ElMessage.warning('请选择策略')
    return
  }
  const stockList = parseStockCodes(form.ts_code)
  if (!stockList.length) {
    ElMessage.warning('请填写股票代码')
    return
  }
  const [start, end] = form.range || []
  if (!start || !end) {
    ElMessage.warning('请选择回测区间')
    return
  }

  running.value = true
  try {
    const summary = await api.backtestRun({
      stock_list: stockList,
      start_date: start,
      end_date: end,
      strategy_key: form.strategy_key,
      strategy_params: buildStrategyParams(),
      cash: form.cash,
      commission: form.commission,
      enable_stamp_tax: form.enable_stamp_tax,
      plot_curve: true,
    })
    const detail = await api.backtestReport({ backtest_id: summary.backtest_id })
    report.value = detail
    buildCurveOption(detail)
    ElMessage.success(`回测完成 #${summary.backtest_id}`)
  } finally {
    running.value = false
  }
}

onMounted(async () => {
  try {
    const listData = await api.strategyList({ page: 1, page_size: 50 })
    strategies.value = listData?.items || []
    if (strategies.value.length) {
      form.strategy_key = strategies.value[0].strategy_key
      await onStrategyChange(form.strategy_key)
    }
  } catch {
    /* interceptor already tips */
  }
})
</script>

<style scoped>
.report-meta {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
  padding-top: 12px;
  padding-bottom: 12px;
}

.report-meta-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
}

.bt-form {
  margin-top: 4px;
}

.bt-form :deep(.el-textarea__inner[readonly]) {
  background-color: var(--mq-bg);
  color: var(--mq-ink);
  cursor: default;
}

.metrics {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
}

.metric-card {
  background: var(--mq-panel);
  border: 1px solid var(--mq-border);
  border-radius: 12px;
  padding: 14px 16px;
}

.metric-label {
  color: var(--mq-muted);
  font-size: 12px;
  margin-bottom: 6px;
}

.metric-value {
  font-size: 20px;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
}

.metric-value.up {
  color: var(--mq-up);
}

.metric-value.down {
  color: var(--mq-down);
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 12px;
}

.panel-hint {
  margin: -6px 0 12px;
  font-size: 13px;
}

.up {
  color: var(--mq-up);
}

.down {
  color: var(--mq-down);
}
</style>
