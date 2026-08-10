<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2>宏观经济指标</h2>
        <p>CPI / PPI / PMI / M2 / LPR / 国债收益率时间序列</p>
      </div>
      <div class="toolbar">
        <el-select v-model="indicator" style="width: 220px">
          <el-option
            v-for="item in catalog"
            :key="item.indicator_code"
            :label="`${item.name} (${item.indicator_code})`"
            :value="item.indicator_code"
          />
        </el-select>
        <el-date-picker
          v-model="range"
          type="daterange"
          value-format="YYYYMMDD"
          start-placeholder="开始"
          end-placeholder="结束"
        />
        <el-button type="primary" :loading="loading" @click="loadTrend">查询</el-button>
      </div>
    </div>

    <div class="panel">
      <v-chart v-if="option" class="chart-box" :option="option" autoresize />
      <el-empty v-else description="暂无宏观数据，可在采集任务中触发 macro" />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import dayjs from 'dayjs'
import { api } from '@/api'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent])

const catalog = ref([])
const indicator = ref('CPI')
const range = ref([dayjs().subtract(3, 'year').format('YYYYMMDD'), dayjs().format('YYYYMMDD')])
const loading = ref(false)
const option = ref(null)

async function loadCatalog() {
  const data = await api.macroList({ indicator_type: '', page: 1, size: 50 })
  catalog.value = data?.items || []
  if (catalog.value.length) indicator.value = catalog.value[0].indicator_code
}

async function loadTrend() {
  loading.value = true
  try {
    const [start, end] = range.value || []
    const data = await api.macroTrend({
      indicator_code: indicator.value,
      start_date: start,
      end_date: end,
    })
    if (!data?.length) {
      option.value = null
      return
    }
    option.value = {
      tooltip: { trigger: 'axis' },
      grid: { left: 50, right: 20, top: 30, bottom: 40 },
      xAxis: { type: 'category', data: data.map((i) => i.date) },
      yAxis: { type: 'value' },
      series: [
        {
          type: 'line',
          smooth: true,
          data: data.map((i) => i.value),
          areaStyle: { opacity: 0.08 },
          lineStyle: { color: '#0f766e' },
          itemStyle: { color: '#0f766e' },
        },
      ],
    }
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadCatalog()
  await loadTrend()
})
</script>
