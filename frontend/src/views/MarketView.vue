<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2>个股日线行情</h2>
        <p>主源 Tushare 前复权日线，支持区间查询与 K 线可视化</p>
      </div>
      <div class="toolbar">
        <el-input v-model="tsCode" placeholder="股票代码 600519.SH" style="width: 180px" />
        <el-date-picker
          v-model="range"
          type="daterange"
          value-format="YYYYMMDD"
          start-placeholder="开始"
          end-placeholder="结束"
        />
        <el-button type="primary" :loading="loading" @click="loadData">查询</el-button>
      </div>
    </div>

    <div class="panel">
      <v-chart v-if="option" class="chart-box" :option="option" autoresize />
      <el-empty v-else description="暂无数据，请先采集或检查代码" />
    </div>

    <div class="panel">
      <el-table :data="rows.slice().reverse()" height="320" stripe>
        <el-table-column prop="trade_date" label="日期" width="120" />
        <el-table-column prop="open_price" label="开盘" />
        <el-table-column prop="high_price" label="最高" />
        <el-table-column prop="low_price" label="最低" />
        <el-table-column prop="close_price" label="收盘" />
        <el-table-column prop="volume" label="成交量" />
        <el-table-column prop="amount" label="成交额" />
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { CandlestickChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, DataZoomComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import dayjs from 'dayjs'
import { api } from '@/api'

use([CanvasRenderer, CandlestickChart, BarChart, GridComponent, TooltipComponent, DataZoomComponent, LegendComponent])

const tsCode = ref('600519.SH')
const range = ref([dayjs().subtract(6, 'month').format('YYYYMMDD'), dayjs().format('YYYYMMDD')])
const loading = ref(false)
const rows = ref([])
const option = ref(null)

function buildOption(list) {
  if (!list?.length) {
    option.value = null
    return
  }
  const dates = list.map((i) => i.trade_date)
  const candles = list.map((i) => [i.open_price, i.close_price, i.low_price, i.high_price])
  const volumes = list.map((i) => i.volume)
  option.value = {
    animation: false,
    legend: { data: ['K线', '成交量'] },
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: [
      { left: 50, right: 20, top: 40, height: '55%' },
      { left: 50, right: 20, top: '75%', height: '16%' },
    ],
    xAxis: [
      { type: 'category', data: dates, boundaryGap: true, axisLabel: { show: false } },
      { type: 'category', data: dates, gridIndex: 1, boundaryGap: true },
    ],
    yAxis: [{ scale: true }, { scale: true, gridIndex: 1, splitNumber: 2 }],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 60, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], start: 60, end: 100, bottom: 8 },
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: candles,
        itemStyle: {
          color: '#ef4444',
          color0: '#22c55e',
          borderColor: '#ef4444',
          borderColor0: '#22c55e',
        },
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes,
        itemStyle: { color: '#94a3b8' },
      },
    ],
  }
}

async function loadData() {
  loading.value = true
  try {
    const [start, end] = range.value || []
    const data = await api.stockDaily({
      ts_code: tsCode.value.trim(),
      start_date: start,
      end_date: end,
    })
    rows.value = data || []
    buildOption(rows.value)
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>
