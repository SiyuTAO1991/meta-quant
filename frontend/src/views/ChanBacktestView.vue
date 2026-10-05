<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2>缠论回测</h2>
        <p>基于 ChanAnalyzer 的缠论策略回测；支持三买与多周期缠论策略</p>
      </div>
      <div class="toolbar">
        <el-button :loading="analyzing" @click="runAnalyze">缠论分析</el-button>
        <el-button type="primary" :loading="running" @click="runBacktest">开始回测</el-button>
      </div>
    </div>

    <div class="panel">
      <el-form :model="form" label-width="100px" class="bt-form">
        <el-row :gutter="16">
          <el-col :xs="24" :md="8">
            <el-form-item label="策略">
              <el-select v-model="form.strategy_key" style="width: 100%" @change="onStrategyChange">
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
              <el-input v-model="form.ts_code" placeholder="如 600036.SH" clearable />
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
                :step="p.param_type === 'float' ? 0.01 : 1"
                :precision="p.param_type === 'float' ? 2 : 0"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="策略描述">
          <el-input v-model="strategyDesc" type="textarea" :rows="2" readonly resize="none" />
        </el-form-item>
      </el-form>
    </div>

    <div v-if="analysis" class="metrics">
      <div class="metric-card">
        <div class="metric-label">实际K线</div>
        <div class="metric-value">{{ analysis.data_range?.bars ?? 0 }}</div>
        <div v-if="analysis.data_range" class="metric-sub">
          {{ analysis.data_range.start }} ~ {{ analysis.data_range.end }}
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-label">合并K线</div>
        <div class="metric-value">{{ analysis.summary.merged_kline_count }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">分型</div>
        <div class="metric-value">{{ analysis.summary.fractal_count }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">笔</div>
        <div class="metric-value">{{ analysis.summary.bi_count }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">中枢</div>
        <div class="metric-value">{{ analysis.summary.zs_count }}</div>
      </div>
    </div>

    <div v-if="analysis" class="panel">
      <div class="panel-title">
        缠论结构（{{ analysis.ts_code || form.ts_code }}）
        <span class="panel-hint">仅展示所选区间的笔与中枢，与回测无关</span>
      </div>
      <v-chart v-if="klineOption" class="chart-box kline-chart" :option="klineOption" autoresize />
      <el-empty v-else description="点击「缠论分析」生成结构图" />
    </div>

    <div v-if="report" class="metrics">
      <div class="metric-card">
        <div class="metric-label">总收益率</div>
        <div class="metric-value" :class="pctClass(report.total_return)">{{ fmtPct(report.total_return) }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">年化收益</div>
        <div class="metric-value" :class="pctClass(report.annual_return)">{{ fmtPct(report.annual_return) }}</div>
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
        <div class="metric-label">交易次数</div>
        <div class="metric-value">{{ report.trade_count ?? 0 }}</div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-title">净值 / 回撤曲线</div>
      <v-chart v-if="curveOption" class="chart-box" :option="curveOption" autoresize />
      <el-empty v-else description="运行回测后展示净值与回撤曲线" />
    </div>

    <div class="panel">
      <div class="panel-title">成交明细（含买卖信号日）</div>
      <el-table :data="report?.trade_fills || []" height="240" stripe size="small">
        <el-table-column prop="stock_code" label="代码" width="100" />
        <el-table-column prop="signal_date" label="信号日" width="110" />
        <el-table-column prop="trade_date" label="成交日" width="110" />
        <el-table-column prop="direction" label="方向" width="70">
          <template #default="{ row }">
            <span :class="row.direction === 'buy' ? 'up' : 'down'">
              {{ row.direction === 'buy' ? '买入' : '卖出' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="price" label="成交价" width="90" />
        <el-table-column prop="volume" label="数量" width="80" />
      </el-table>
    </div>

    <div class="panel">
      <div class="panel-title">交易明细（已平仓）</div>
      <el-table :data="report?.trade_logs || []" height="280" stripe>
        <el-table-column prop="buy_signal_date" label="买入信号日" width="110" />
        <el-table-column prop="buy_date" label="买入成交日" width="110" />
        <el-table-column prop="buy_price" label="买入价" width="90" />
        <el-table-column prop="sell_signal_date" label="卖出信号日" width="110" />
        <el-table-column prop="sell_date" label="卖出成交日" width="110" />
        <el-table-column prop="sell_price" label="卖出价" width="90" />
        <el-table-column prop="pnlcomm" label="净盈亏" width="100">
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
import { CandlestickChart, LineChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
  MarkAreaComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { api } from '@/api'

use([
  CanvasRenderer,
  CandlestickChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  MarkLineComponent,
  MarkAreaComponent,
])

const strategies = ref([])
const paramTemplate = ref([])
const strategyDesc = ref('')
const analyzing = ref(false)
const running = ref(false)
const analysis = ref(null)
const report = ref(null)
const klineOption = ref(null)
const curveOption = ref(null)

const form = reactive({
  strategy_key: '',
  ts_code: '600036.SH',
  range: ['2023-01-01', dayjs().format('YYYY-MM-DD')],
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
    params[p.param_name] = form.strategy_params[p.param_name] ?? p.default_value
  }
  return params
}

async function onStrategyChange(key) {
  if (!key) return
  const detail = await api.strategyDetail({ strategy_key: key })
  paramTemplate.value = detail?.param_template || []
  strategyDesc.value = detail?.strategy_desc || ''
  applyParamDefaults(paramTemplate.value)
}

function lookupDateIndex(dateIndex, ...dates) {
  for (const d of dates) {
    if (d != null && dateIndex[d] !== undefined) return dateIndex[d]
  }
  return undefined
}

function buildKlineOption(data) {
  const klines = data?.klines || []
  if (!klines.length) {
    klineOption.value = null
    return
  }

  const dates = klines.map((k) => k.date)
  const candleData = klines.map((k) => [k.open, k.close, k.low, k.high])
  const dateIndex = Object.fromEntries(dates.map((d, i) => [d, i]))

  const biLines = (data.bi_list || [])
    .map((bi) => {
      const x0 = lookupDateIndex(dateIndex, bi.start_raw_date, bi.start_date)
      const x1 = lookupDateIndex(dateIndex, bi.end_raw_date, bi.end_date)
      if (x0 === undefined || x1 === undefined) return null
      const color = bi.direction === 'up' ? '#e74c3c' : '#27ae60'
      return [
        { coord: [x0, bi.start_price] },
        { coord: [x1, bi.end_price], lineStyle: { color, width: 2 } },
      ]
    })
    .filter(Boolean)

  const zsAreas = (data.zs_list || [])
    .map((zs) => {
      const x0 = lookupDateIndex(dateIndex, zs.start_date)
      const x1 = lookupDateIndex(dateIndex, zs.end_date)
      if (x0 === undefined || x1 === undefined) return null
      const zg = zs.ZG ?? zs.zg
      const zd = zs.ZD ?? zs.zd
      if (zg == null || zd == null) return null
      return [
        {
          xAxis: x0,
          yAxis: zd,
          itemStyle: { color: 'rgba(52, 152, 219, 0.14)' },
          label: {
            show: true,
            position: 'insideTopLeft',
            formatter: `ZG ${Number(zg).toFixed(2)} / ZD ${Number(zd).toFixed(2)}`,
            color: '#334155',
            fontSize: 10,
          },
        },
        { xAxis: x1, yAxis: zg },
      ]
    })
    .filter(Boolean)

  klineOption.value = {
    animation: false,
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: ['K线'] },
    grid: { left: 56, right: 24, top: 40, bottom: 72 },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', start: 0, end: 100, bottom: 8 },
    ],
    xAxis: { type: 'category', data: dates, boundaryGap: true },
    yAxis: { scale: true },
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: candleData,
        itemStyle: {
          color: '#ef4444',
          color0: '#22c55e',
          borderColor: '#ef4444',
          borderColor0: '#22c55e',
        },
        markLine: biLines.length
          ? { symbol: ['none', 'none'], animation: false, data: biLines }
          : undefined,
        markArea: zsAreas.length
          ? { silent: true, animation: false, data: zsAreas }
          : undefined,
      },
    ],
  }
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
    dataZoom: [{ type: 'inside', xAxisIndex: [0, 1] }, { type: 'slider', xAxisIndex: [0, 1], bottom: 8 }],
    xAxis: [
      { type: 'category', data: dates, boundaryGap: false, axisLabel: { show: false } },
      { type: 'category', data: dates, gridIndex: 1, boundaryGap: false },
    ],
    yAxis: [
      { type: 'value', scale: true, name: '净值' },
      { type: 'value', scale: true, gridIndex: 1, name: '回撤%', axisLabel: { formatter: '{value}%' } },
    ],
    series: [
      { name: '净值', type: 'line', data: eqSeries, showSymbol: false, lineStyle: { width: 2, color: '#0f766e' } },
      { name: '回撤%', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: ddSeries, showSymbol: false, lineStyle: { color: '#b91c1c' } },
    ],
  }
}

function validateForm() {
  const code = (form.ts_code || '').trim().toUpperCase()
  if (!code) {
    ElMessage.warning('请填写股票代码')
    return null
  }
  const [start, end] = form.range || []
  if (!start || !end) {
    ElMessage.warning('请选择区间')
    return null
  }
  return { code, start, end }
}

async function runAnalyze() {
  const payload = validateForm()
  if (!payload) return
  analyzing.value = true
  try {
    analysis.value = await api.chanAnalyze({
      ts_code: payload.code,
      start_date: payload.start,
      end_date: payload.end,
    })
    buildKlineOption(analysis.value)
    ElMessage.success('缠论分析完成')
  } finally {
    analyzing.value = false
  }
}

async function runBacktest() {
  if (!form.strategy_key) {
    ElMessage.warning('请选择策略')
    return
  }
  const payload = validateForm()
  if (!payload) return

  running.value = true
  try {
    const summary = await api.backtestRun({
      stock_list: [payload.code],
      start_date: payload.start,
      end_date: payload.end,
      strategy_key: form.strategy_key,
      strategy_params: buildStrategyParams(),
      cash: form.cash,
      commission: form.commission,
      enable_stamp_tax: form.enable_stamp_tax,
      plot_curve: true,
    })
    report.value = await api.backtestReport({ backtest_id: summary.backtest_id })
    buildCurveOption(report.value)
    ElMessage.success(`回测完成 #${summary.backtest_id}`)
  } finally {
    running.value = false
  }
}

onMounted(async () => {
  const listData = await api.strategyList({ page: 1, page_size: 50 })
  strategies.value = (listData?.items || []).filter((item) => item.strategy_key?.startsWith('chan_'))
  if (strategies.value.length) {
    form.strategy_key = strategies.value[0].strategy_key
    await onStrategyChange(form.strategy_key)
  }
})
</script>

<style scoped>
.bt-form {
  margin-top: 4px;
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

.metric-sub {
  margin-top: 4px;
  font-size: 11px;
  color: var(--mq-muted);
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 12px;
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.panel-hint {
  font-size: 12px;
  font-weight: 400;
  color: var(--mq-muted);
}

.kline-chart {
  min-height: 460px;
  width: 100%;
}

.chart-box {
  width: 100%;
  min-height: 280px;
}

.up {
  color: var(--mq-up);
}

.down {
  color: var(--mq-down);
}
</style>
