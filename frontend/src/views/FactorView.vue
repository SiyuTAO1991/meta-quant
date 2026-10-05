<template>
  <div class="factor-page">
    <div class="panel filter-panel">
      <el-form :inline="true" class="filter-form" @submit.prevent>
        <el-form-item label="股票池">
          <el-select v-model="form.universe" style="width: 130px" @change="onUniverseChange">
            <el-option label="全A股" value="all" />
            <el-option label="部分A股" value="custom" />
          </el-select>
        </el-form-item>

        <el-form-item v-if="form.universe === 'custom'" label="股票代码">
          <el-input
            v-model="form.stockCodes"
            clearable
            style="width: 280px"
            placeholder="如 600519.SH,000001.SZ"
            @blur="validateCodes"
          />
        </el-form-item>

        <el-form-item label="评价区间">
          <el-date-picker
            v-model="form.range"
            type="daterange"
            value-format="YYYY-MM-DD"
            start-placeholder="开始"
            end-placeholder="结束"
            style="width: 260px"
          />
        </el-form-item>

        <el-form-item label="调仓周期">
          <el-select v-model="form.holdingDays" style="width: 110px">
            <el-option
              v-for="p in holdingPeriods"
              :key="p.value"
              :label="p.label"
              :value="p.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="分类">
          <el-select v-model="form.category" style="width: 110px">
            <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>

        <el-form-item label="排序">
          <el-select v-model="form.sortBy" style="width: 150px">
            <el-option
              v-for="s in sortOptions"
              :key="s.value"
              :label="s.label"
              :value="s.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="因子">
          <el-select
            v-model="form.keyword"
            clearable
            filterable
            style="width: 200px"
            placeholder="全部因子"
          >
            <el-option
              v-for="f in factorOptions"
              :key="f.code"
              :label="`${f.name} (${f.code})`"
              :value="f.code"
            />
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="evaluating" @click="runEvaluate">评价</el-button>
          <el-button :loading="loading" @click="loadResults">刷新</el-button>
        </el-form-item>
      </el-form>

      <div v-if="form.universe === 'custom' && validateMsg" class="validate-msg" :class="{ bad: !validateOk }">
        {{ validateMsg }}
      </div>
    </div>

    <div class="panel summary-bar">
      <div class="summary-left">
        <span class="count">共 {{ total }} 条评价结果</span>
        <span class="legend orange">|IC| &gt; 0.03 (强信号)</span>
        <span class="legend blue">IR &gt; 0.5 (稳定)</span>
        <span class="legend green">单调性 &gt; 0.5</span>
      </div>
      <div class="summary-right">
        <span class="muted">按评价时间倒序平铺展示，每页 10 条</span>
      </div>
    </div>

    <div class="panel table-panel">
      <el-table :data="items" stripe v-loading="loading || evaluating" height="calc(100vh - 320px)">
        <el-table-column label="评价时间" width="170" fixed>
          <template #default="{ row }">{{ formatTime(row.eval_time) }}</template>
        </el-table-column>
        <el-table-column label="评价条件" min-width="200">
          <template #default="{ row }">
            <div class="cond">
              <div>{{ universeLabel(row.universe) }} · {{ row.holding_days }}日调仓</div>
              <div class="sub">{{ row.start_date }} ~ {{ row.end_date }} · {{ row.stock_count || 0 }}只</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="因子名" min-width="150">
          <template #default="{ row }">
            <div class="factor-name">
              <span class="dot" :class="badgeClass(row)" />
              <div>
                <div class="name">{{ row.name }}</div>
                <div class="code">{{ row.code }}</div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="分类" width="80" />
        <el-table-column label="IC 均值" width="100" align="right">
          <template #default="{ row }">
            <span :class="numClass(row.ic_mean)">{{ fmtPct(row.ic_mean, 4) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="IR" width="80" align="right">
          <template #default="{ row }">
            <span :class="numClass(row.ir)">{{ fmtNum(row.ir, 3) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="IC 胜率" width="90" align="right">
          <template #default="{ row }">{{ fmtPct(row.ic_win_rate, 2) }}</template>
        </el-table-column>
        <el-table-column label="Q1 超额" width="90" align="right">
          <template #default="{ row }">
            <span :class="numClass(row.q1_excess)">{{ fmtPct(row.q1_excess, 2) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="Q5 超额" width="90" align="right">
          <template #default="{ row }">
            <span :class="numClass(row.q5_excess)">{{ fmtPct(row.q5_excess, 2) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="Q5-Q1" width="90" align="right">
          <template #default="{ row }">
            <span :class="numClass(row.q5_q1)">{{ fmtPct(row.q5_q1, 2) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="Q5 换手" width="90" align="right">
          <template #default="{ row }">{{ fmtPct(row.q5_turnover, 2) }}</template>
        </el-table-column>
        <el-table-column label="单调性" width="80" align="right">
          <template #default="{ row }">{{ fmtPct(row.monotonicity, 2) }}</template>
        </el-table-column>
        <el-table-column label="样本数" width="110" align="right">
          <template #default="{ row }">
            {{ row.sample_stocks || 0 }} × {{ row.sample_periods || 0 }}
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          background
          @current-change="loadResults"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'

function defaultRange() {
  const end = new Date()
  const start = new Date()
  start.setFullYear(end.getFullYear() - 1)
  const fmt = (d) => {
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${y}-${m}-${day}`
  }
  return [fmt(start), fmt(end)]
}

const loading = ref(false)
const evaluating = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 10

const categories = ref(['全部'])
const factorOptions = ref([])
const holdingPeriods = ref([
  { label: '5日', value: 5 },
  { label: '10日', value: 10 },
  { label: '20日', value: 20 },
  { label: '60日', value: 60 },
])
const sortOptions = ref([
  { label: '|IR| (稳定性)', value: 'abs_ir' },
  { label: '|IC| (强度)', value: 'abs_ic' },
  { label: 'IC均值', value: 'ic_mean' },
  { label: 'Q5-Q1', value: 'q5_q1' },
  { label: '单调性', value: 'monotonicity' },
])
const validateOk = ref(true)
const validateMsg = ref('')

const form = reactive({
  universe: 'all',
  stockCodes: '',
  range: defaultRange(),
  holdingDays: 20,
  category: '全部',
  sortBy: 'abs_ir',
  keyword: '',
})

function onUniverseChange() {
  validateMsg.value = ''
  validateOk.value = true
}

function universeLabel(u) {
  return u === 'custom' ? '部分A股' : '全A股'
}

function formatTime(v) {
  if (!v) return '-'
  return String(v).replace('T', ' ').slice(0, 19)
}

async function validateCodes() {
  if (form.universe !== 'custom' || !form.stockCodes.trim()) {
    validateMsg.value = ''
    return
  }
  try {
    const data = await api.factorValidateStocks({ stock_codes: form.stockCodes.trim() })
    validateOk.value = !!data?.ok
    if (data?.ok) {
      validateMsg.value = `已校验通过 ${data.count} 只股票`
    } else {
      const bad = (data?.invalid || []).map((i) => i.ts_code).join(', ')
      validateMsg.value = `无效代码: ${bad || '请检查格式'}`
    }
  } catch {
    validateOk.value = false
    validateMsg.value = '股票校验失败'
  }
}

async function loadMeta() {
  try {
    const meta = await api.factorMeta()
    if (meta?.categories?.length) categories.value = meta.categories
    if (meta?.holding_periods?.length) holdingPeriods.value = meta.holding_periods
    if (meta?.sort_options?.length) sortOptions.value = meta.sort_options
    if (meta?.factors?.length) {
      factorOptions.value = meta.factors.map((f) => ({
        code: f.code,
        name: f.name,
        category: f.category,
      }))
    }
  } catch {
    // ignore
  }
}

async function loadResults() {
  loading.value = true
  try {
    const data = await api.factorResults({ page: page.value, size: pageSize })
    items.value = data?.items || []
    total.value = data?.total || 0
  } finally {
    loading.value = false
  }
}

async function runEvaluate() {
  if (!form.range?.[0] || !form.range?.[1]) {
    ElMessage.warning('请选择评价区间')
    return
  }
  if (form.universe === 'custom') {
    if (!form.stockCodes.trim()) {
      ElMessage.warning('请录入股票代码')
      return
    }
    await validateCodes()
    if (!validateOk.value) {
      ElMessage.warning(validateMsg.value || '股票代码校验未通过')
      return
    }
  }

  evaluating.value = true
  try {
    const data = await api.factorEvaluate({
      universe: form.universe,
      stock_codes: form.universe === 'custom' ? form.stockCodes.trim() : '',
      start_date: form.range[0],
      end_date: form.range[1],
      holding_days: form.holdingDays,
      category: form.category,
      sort_by: form.sortBy,
      keyword: form.keyword.trim(),
    })
    if (data?.crawl?.triggered) {
      ElMessage.success(data.crawl.message || '已自动补采缺失数据')
    } else {
      ElMessage.success(`评价完成，已写入 ${data?.total || 0} 条因子结果`)
    }
    page.value = 1
    await loadResults()
  } finally {
    evaluating.value = false
  }
}

function fmtNum(v, digits = 3) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '-'
  return Number(v).toFixed(digits)
}

function fmtPct(v, digits = 2) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '-'
  return `${(Number(v) * 100).toFixed(digits)}%`
}

function numClass(v) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return ''
  if (Number(v) > 0) return 'pos'
  if (Number(v) < 0) return 'neg'
  return ''
}

function badgeClass(row) {
  const ic = Math.abs(row.ic_mean || 0)
  const ir = Math.abs(row.ir || 0)
  const mono = row.monotonicity || 0
  if (ic > 0.03) return 'orange'
  if (ir > 0.5) return 'blue'
  if (mono > 0.5) return 'green'
  return 'gray'
}

onMounted(async () => {
  await loadMeta()
  await loadResults()
})
</script>

<style scoped>
.factor-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel {
  background: #fff;
  border: 1px solid var(--mq-border, #e5e7eb);
  border-radius: 10px;
  padding: 14px 16px;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
}

.validate-msg {
  margin-top: 6px;
  font-size: 12px;
  color: #059669;
}

.validate-msg.bad {
  color: #dc2626;
}

.summary-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.summary-left {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
  font-size: 13px;
}

.count {
  font-weight: 700;
  color: #111827;
}

.legend {
  position: relative;
  padding-left: 14px;
  color: #4b5563;
}

.legend::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  width: 8px;
  height: 8px;
  border-radius: 2px;
  transform: translateY(-50%);
}

.legend.orange::before {
  background: #f59e0b;
}
.legend.blue::before {
  background: #3b82f6;
}
.legend.green::before {
  background: #10b981;
}

.muted {
  color: #9ca3af;
  font-size: 12px;
}

.table-panel {
  padding: 8px;
}

.cond .sub {
  margin-top: 2px;
  font-size: 12px;
  color: #9ca3af;
}

.factor-name {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.factor-name .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 6px;
  flex-shrink: 0;
}

.factor-name .dot.orange {
  background: #f59e0b;
}
.factor-name .dot.blue {
  background: #3b82f6;
}
.factor-name .dot.green {
  background: #10b981;
}
.factor-name .dot.gray {
  background: #d1d5db;
}

.factor-name .name {
  font-weight: 600;
  color: #111827;
  line-height: 1.2;
}

.factor-name .code {
  font-size: 12px;
  color: #9ca3af;
  margin-top: 2px;
}

.pos {
  color: #059669;
  font-variant-numeric: tabular-nums;
}

.neg {
  color: #dc2626;
  font-variant-numeric: tabular-nums;
}

.pager {
  display: flex;
  justify-content: flex-end;
  padding: 12px 4px 4px;
}
</style>
