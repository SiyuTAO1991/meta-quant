<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2>财务核心指标</h2>
        <p>ROE / 营收 / 净利润 / 毛利率等季度财务数据</p>
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
        <el-table-column prop="revenue" label="营收" />
        <el-table-column prop="net_profit" label="净利润" />
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
const startYear = ref(2020)
const endYear = ref(2026)
const loading = ref(false)
const rows = ref([])
const option = ref(null)

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
      legend: { data: ['营收', '净利润', 'ROE'] },
      grid: { left: 50, right: 40, top: 40, bottom: 40 },
      xAxis: { type: 'category', data: sorted.map((i) => i.report_date) },
      yAxis: [
        { type: 'value', name: '金额' },
        { type: 'value', name: 'ROE(%)' },
      ],
      series: [
        { name: '营收', type: 'bar', data: sorted.map((i) => i.revenue) },
        { name: '净利润', type: 'bar', data: sorted.map((i) => i.net_profit) },
        { name: 'ROE', type: 'line', yAxisIndex: 1, data: sorted.map((i) => i.roe) },
      ],
    }
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>
