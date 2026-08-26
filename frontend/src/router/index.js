import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/backtest' },
  {
    path: '/backtest',
    name: 'backtest',
    component: () => import('@/views/BacktestView.vue'),
    meta: { title: '策略回测', icon: 'Histogram' },
  },
  {
    path: '/chan-backtest',
    name: 'chan-backtest',
    component: () => import('@/views/ChanBacktestView.vue'),
    meta: { title: '缠论回测', icon: 'TrendCharts' },
  },
  {
    path: '/crawl',
    name: 'crawl',
    component: () => import('@/views/CrawlView.vue'),
    meta: { title: '采集任务', icon: 'Setting' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
