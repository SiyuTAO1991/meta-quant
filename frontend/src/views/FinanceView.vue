<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2>财务核心指标</h2>
        <p>ROE / 营收 / 净利润 / 毛利率等季度财务数据（金额单位：万元）</p>
      </div>
      <div class="toolbar">
        <el-input v-model="tsCode" style="width: 160px" placeholder="股票代码" />
        <el-input-number v-model="startYear" :min="2015" :max="2030" />
        <span>~</span>
        <el-input-number v-model="endYear" :min="2015" :max="2030" />
        <el-button type="primary" :loading="loading" @click="loadData">查询</el-button>
      </div>
    </div>

    <div class="panel">
      <v-chart v-if="option" class="chart-box" :option="option" autoresize />
      <el-empty v-else description="暂无财务数据" />
    </div>

    <div class="panel">
      <el-table :data="rows" stripe height="360">
        <el-table-column prop="report_date" label="报告期" width="120" />
        <el-table-column label="营收(万)" min-width="120">
          <template #default="{ row }">{{ formatWan(row.revenue) }}</template>
        </el-table-column>
        <el-table-column label="净利润(万)" min-width="120">
          <template #default="{ row }">{{ formatWan(row.net_profit) }}</template>
        </el-table-column>
        <el-table-column prop="eps" label="EPS" />
        <el-table-column prop="roe" label="ROE(%)" />
        <el-table-column prop="gross_margin" label="毛利率(%)" />
        <el-table-column prop="net_margin" label="净利率(%)" />
        <el-table-column prop="debt_ratio" label="资产负债率(%)" />
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { api } from '@/api'

use([CanvasRenderer, LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent])

const tsCode = ref('600519.SH')
const startYear = ref(1998)
const endYear = ref(2026)
const loading = ref(false)
const rows = ref([])
const option = ref(null)

function toWan(value) {
  if (value === null || value === undefined || value === '') return null
  const n = Number(value)
  if (Number.isNaN(n)) return null
  return Math.round((n / 10000) * 100) / 100
}

function formatWan(value) {
  const n = toWan(value)
  return n === null ? '-' : n.toFixed(2)
}

async function loadData() {
  loading.value = true
  try {
    const data = await api.financeIndicator({
      ts_code: tsCode.value.trim(),
      start_year: startYear.value,
      end_year: endYear.value,
      report_type: 1,
    })
    rows.value = data || []
    const sorted = [...rows.value].reverse()
    if (!sorted.length) {
      option.value = null
      return
    }
    option.value = {
      tooltip: { trigger: 'axis' },
      legend: { data: ['营收(万)', '净利润(万)', 'ROE'] },
      grid: { left: 16, right: 56, top: 48, bottom: 32, containLabel: true },
      xAxis: { type: 'category', data: sorted.map((i) => i.report_date) },
      yAxis: [
        {
          type: 'value',
          name: '金额(万)',
          axisLabel: { show: false },
          splitLine: { show: true },
        },
        { type: 'value', name: 'ROE(%)' },
      ],
      series: [
        { name: '营收(万)', type: 'bar', data: sorted.map((i) => toWan(i.revenue)) },
        { name: '净利润(万)', type: 'bar', data: sorted.map((i) => toWan(i.net_profit)) },
        { name: 'ROE', type: 'line', yAxisIndex: 1, data: sorted.map((i) => i.roe) },
      ],
    }
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>
