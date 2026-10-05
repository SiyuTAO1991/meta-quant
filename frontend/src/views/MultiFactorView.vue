<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2>多因子打分</h2>
        <p>按配置周期计算因子 → 横截面打分 → Top-N 等权持有至下一调仓日</p>
      </div>
      <div class="toolbar">
        <el-button @click="resetFactors">重置因子</el-button>
        <el-button type="primary" :loading="running" @click="runBacktest">开始回测</el-button>
      </div>
    </div>

    <div class="panel">
      <el-form :model="form" label-width="100px" class="mf-form">
        <el-row :gutter="16">
          <el-col :xs="24" :md="16">
            <el-form-item label="股票代码">
              <el-input
                v-model="form.stock_codes"
                clearable
                placeholder="留空则默认全部A股；填写示例 600519.SH,000001.SZ"
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
            <el-form-item label="调仓周期">
              <el-select v-model="form.holding_days" style="width: 100%">
                <el-option
                  v-for="p in holdingPeriods"
                  :key="p.value"
                  :label="p.label"
                  :value="p.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="Top-N">
              <el-input-number v-model="form.top_n" :min="1" :max="100" :step="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="初始资金">
              <el-input-number v-model="form.cash" :min="1000" :step="10000" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row v-if="useAllUniverse" :gutter="16">
          <el-col :xs="24" :md="8">
            <el-form-item label="股票池上限">
              <el-input-number
                v-model="form.max_stocks"
                :min="50"
                :max="3000"
                :step="50"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
    </div>

    <div class="panel">
      <div class="panel-title-row">
        <div class="panel-title">因子权重配置</div>
        <div class="muted">权重会在启用项内自动归一化；方向：正向=越大越好，反向=越小越好</div>
      </div>
      <el-table :data="factorRows" stripe size="small">
        <el-table-column label="启用" width="70" align="center">
          <template #default="{ row }">
            <el-switch v-model="row.enabled" size="small" />
          </template>
        </el-table-column>
        <el-table-column prop="name" label="因子" min-width="120" />
        <el-table-column prop="code" label="代码" min-width="130" />
        <el-table-column label="方向" width="130">
          <template #default="{ row }">
            <el-select v-model="row.direction" style="width: 100%" :disabled="!row.enabled">
              <el-option label="正向" :value="1" />
              <el-option label="反向" :value="-1" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="权重" width="160">
          <template #default="{ row }">
            <el-input-number
              v-model="row.weight"
              :min="0.01"
              :max="1"
              :step="0.05"
              :precision="2"
              :disabled="!row.enabled"
              style="width: 100%"
            />
          </template>
        </el-table-column>
        <el-table-column prop="desc" label="说明" min-width="180" show-overflow-tooltip />
      </el-table>
      <div class="weight-sum muted">
        启用权重合计 {{ weightSumText }}（回测时归一化）
      </div>
    </div>

    <div v-if="report" class="panel report-meta">
      <div class="report-meta-item">
        <span class="muted">回测区间</span>
        <strong>{{ report.params?.start_date }} ~ {{ report.params?.end_date }}</strong>
      </div>
      <div class="report-meta-item">
        <span class="muted">实际调仓</span>
        <strong>{{ report.params?.rebalance_start }} ~ {{ report.params?.rebalance_end }}</strong>
      </div>
      <div class="report-meta-item">
        <span class="muted">调仓周期</span>
        <strong>{{ report.params?.holding_label || '--' }}</strong>
      </div>
    </div>

    <div v-if="report" class="metrics">
      <div class="metric-card">
        <div class="metric-label">总收益率</div>
        <div class="metric-value" :class="pctClass(metrics.total_return)">
          {{ fmtPct(metrics.total_return) }}
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-label">年化收益</div>
        <div class="metric-value" :class="pctClass(metrics.annual_return)">
          {{ fmtPct(metrics.annual_return) }}
        </div>
      </div>
      <div class="metric-card">
        <div class="metric-label">最大回撤</div>
        <div class="metric-value down">{{ fmtPct(metrics.max_drawdown) }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">夏普比率</div>
        <div class="metric-value">{{ fmtNum(metrics.sharpe) }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Calmar</div>
        <div class="metric-value">{{ fmtNum(metrics.calmar) }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">调仓胜率</div>
        <div class="metric-value">{{ fmtPct(metrics.win_rate) }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">调仓期数</div>
        <div class="metric-value">{{ metrics.periods ?? 0 }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">期末净值</div>
        <div class="metric-value">{{ fmtMoney(metrics.final_value) }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">股票池规模</div>
        <div class="metric-value">{{ report.params?.stock_universe_size ?? '--' }}</div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-title">净值 / 回撤曲线</div>
      <v-chart v-if="curveOption" class="chart-box" :option="curveOption" autoresize />
      <el-empty v-else description="运行回测后展示净值与回撤曲线" />
    </div>

    <div class="panel">
      <div class="panel-title">每次调仓持股</div>
      <el-table
        :data="report?.rebalance_log || []"
        stripe
        height="420"
        row-key="date"
        @expand-change="() => {}"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="holdings-wrap">
              <el-table :data="row.holdings || []" size="small" stripe>
                <el-table-column label="股票" min-width="160">
                  <template #default="{ row: h }">
                    <div class="stock-cell">
                      <span class="stock-name">{{ h.stock_name || h.stock_code }}</span>
                      <span class="stock-code">{{ h.stock_code }}</span>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="综合分" width="100" align="right">
                  <template #default="{ row: h }">{{ fmtNum(h.score, 4) }}</template>
                </el-table-column>
                <el-table-column label="权重" width="90" align="right">
                  <template #default="{ row: h }">{{ fmtPct(h.weight) }}</template>
                </el-table-column>
                <el-table-column label="买入价" width="100" align="right">
                  <template #default="{ row: h }">{{ fmtNum(h.buy_price) }}</template>
                </el-table-column>
                <el-table-column label="卖出价" width="100" align="right">
                  <template #default="{ row: h }">{{ fmtNum(h.sell_price) }}</template>
                </el-table-column>
                <el-table-column label="期间收益" width="110" align="right">
                  <template #default="{ row: h }">
                    <span :class="pctClass(h.period_return)">{{ fmtPct(h.period_return) }}</span>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="date" label="调仓日" width="120" />
        <el-table-column prop="next_date" label="持有至" width="120" />
        <el-table-column label="持股数" width="80" align="right">
          <template #default="{ row }">{{ row.stock_count ?? row.stocks?.length ?? 0 }}</template>
        </el-table-column>
        <el-table-column label="持股列表" min-width="360">
          <template #default="{ row }">
            <div class="name-tags">
              <el-tooltip
                v-for="(h, idx) in row.holdings || []"
                :key="`${row.date}-${h.stock_code || idx}`"
                :content="h.stock_code"
                placement="top"
              >
                <span class="name-tag" :class="pctClass(h.period_return)">
                  {{ h.stock_name || h.stock_code }}
                </span>
              </el-tooltip>
              <template v-if="!(row.holdings || []).length">
                <span
                  v-for="(name, idx) in row.stock_names || []"
                  :key="`${row.date}-n-${idx}`"
                  class="name-tag"
                >
                  {{ name }}
                </span>
              </template>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="组合收益" width="110" align="right">
          <template #default="{ row }">
            <span :class="pctClass(row.return)">{{ fmtPct(row.return) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="净值" width="120" align="right">
          <template #default="{ row }">{{ fmtMoney(row.nav) }}</template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!report?.rebalance_log?.length && !running" description="运行回测后展示调仓明细" />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
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

const running = ref(false)
const report = ref(null)
const curveOption = ref(null)
const factorRows = ref([])
const defaultFactors = ref([])
const holdingPeriods = ref([
  { label: '月末调仓', value: 0 },
  { label: '5个交易日', value: 5 },
  { label: '10个交易日', value: 10 },
  { label: '20个交易日', value: 20 },
  { label: '60个交易日', value: 60 },
])

const form = reactive({
  stock_codes: '',
  range: [dayjs().subtract(1, 'year').format('YYYY-MM-DD'), dayjs().format('YYYY-MM-DD')],
  top_n: 10,
  cash: 1000000,
  max_stocks: 800,
  holding_days: 0,
})

const useAllUniverse = computed(() => !String(form.stock_codes || '').trim())
const metrics = computed(() => report.value?.metrics || {})

const weightSumText = computed(() => {
  const sum = factorRows.value
    .filter((r) => r.enabled)
    .reduce((acc, r) => acc + Number(r.weight || 0), 0)
  return `${(sum * 100).toFixed(0)}%`
})

function fmtPct(v, digits = 2) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '--'
  return `${(Number(v) * 100).toFixed(digits)}%`
}

function fmtNum(v, digits = 2) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '--'
  return Number(v).toFixed(digits)
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

function applyFactorDefaults(list) {
  factorRows.value = (list || []).map((f) => ({
    code: f.code,
    name: f.name,
    desc: f.desc || '',
    direction: f.direction ?? 1,
    weight: Number(f.weight ?? 0.1),
    enabled: f.enabled !== false,
  }))
}

function resetFactors() {
  applyFactorDefaults(defaultFactors.value)
  ElMessage.success('已恢复默认 8 因子权重')
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
        lineStyle: { width: 1.5, color: '#b45309' },
        areaStyle: { color: 'rgba(180, 83, 9, 0.12)' },
      },
    ],
  }
}

async function runBacktest() {
  if (!form.range?.length) {
    ElMessage.warning('请选择回测区间')
    return
  }
  const enabled = factorRows.value.filter((r) => r.enabled)
  if (!enabled.length) {
    ElMessage.warning('请至少启用一个因子')
    return
  }
  running.value = true
  try {
    const codes = String(form.stock_codes || '').trim()
    const data = await api.multiFactorBacktest({
      universe: codes ? 'custom' : 'all',
      stock_codes: codes,
      start_date: form.range[0],
      end_date: form.range[1],
      top_n: form.top_n,
      cash: form.cash,
      max_stocks: form.max_stocks,
      holding_days: form.holding_days,
      factor_weights: factorRows.value.map((r) => ({
        code: r.code,
        weight: r.weight,
        direction: r.direction,
        enabled: r.enabled,
      })),
    })
    report.value = data
    buildCurveOption(data)
    ElMessage.success(`回测完成，共 ${data?.metrics?.periods || 0} 期调仓`)
  } finally {
    running.value = false
  }
}

onMounted(async () => {
  try {
    const meta = await api.multiFactorMeta()
    defaultFactors.value = meta?.factors || []
    applyFactorDefaults(defaultFactors.value)
    if (meta?.holding_periods?.length) holdingPeriods.value = meta.holding_periods
    if (meta?.defaults) {
      form.top_n = meta.defaults.top_n ?? form.top_n
      form.cash = meta.defaults.cash ?? form.cash
      form.max_stocks = meta.defaults.max_stocks ?? form.max_stocks
      form.holding_days = meta.defaults.holding_days ?? form.holding_days
    }
  } catch {
    /* interceptor already tips */
  }
})
</script>

<style scoped>
.mf-form {
  margin-top: 4px;
}

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

.panel-title-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
}

.weight-sum {
  margin-top: 10px;
  font-size: 13px;
}

.metrics {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
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

.chart-box {
  height: 360px;
  width: 100%;
}

.holdings-wrap {
  padding: 8px 24px 16px;
}

.name-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 2px 0;
}

.name-tag {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  line-height: 1.6;
  background: color-mix(in srgb, var(--mq-border) 55%, transparent);
  color: var(--mq-ink);
  border: 1px solid var(--mq-border);
  white-space: nowrap;
  cursor: default;
}

.name-tag.up {
  background: color-mix(in srgb, var(--mq-up) 12%, transparent);
  border-color: color-mix(in srgb, var(--mq-up) 35%, var(--mq-border));
  color: var(--mq-up);
}

.name-tag.down {
  background: color-mix(in srgb, var(--mq-down) 12%, transparent);
  border-color: color-mix(in srgb, var(--mq-down) 35%, var(--mq-border));
  color: var(--mq-down);
}

.stock-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  line-height: 1.3;
}

.stock-name {
  font-weight: 600;
  color: var(--mq-ink);
}

.stock-code {
  font-size: 12px;
  color: var(--mq-muted);
  font-variant-numeric: tabular-nums;
}

.up {
  color: var(--mq-up);
}

.down {
  color: var(--mq-down);
}

.muted {
  color: var(--mq-muted);
  font-size: 13px;
}
</style>
