<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2>GBDT 涨跌预测</h2>
        <p>日 K → 技术因子 → MAD/Z-score → 共用滚动窗口，分别训练 XGBoost / LightGBM，结果仅展示不落库</p>
      </div>
      <div class="toolbar">
        <el-button @click="resetDefaults">恢复默认</el-button>
        <el-button type="primary" :loading="running" @click="runPredict">开始预测</el-button>
      </div>
    </div>

    <div class="panel">
      <el-form :model="form" label-width="120px" class="cfg-form">
        <el-row :gutter="16">
          <el-col :xs="24" :md="16">
            <el-form-item label="股票代码">
              <el-input v-model="form.stock_codes" clearable placeholder="默认 600519.SH,688981.SH" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="8">
            <el-form-item label="样本区间">
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
          <el-col :xs="24" :md="6">
            <el-form-item label="标签天数">
              <el-input-number v-model="form.label_horizon" :min="1" :max="20" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="6">
            <el-form-item label="最少K线">
              <el-input-number v-model="form.min_bars" :min="60" :max="2000" :step="10" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="6">
            <el-form-item label="训练窗口">
              <el-input-number v-model="form.train_days" :min="30" :max="1000" :step="10" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :md="6">
            <el-form-item label="重训间隔">
              <el-input-number v-model="form.retrain_interval" :min="1" :max="250" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="X 特征列">
          <div class="feature-row">
            <el-select
              v-model="pendingFactor"
              filterable
              clearable
              placeholder="下拉选择 / 取消技术因子"
              style="width: 360px"
              popper-class="factor-select-popper"
              @change="toggleFeatureFromSelect"
            >
              <el-option-group v-for="cat in categories" :key="cat.key" :label="cat.name">
                <el-option
                  v-for="f in cat.features"
                  :key="f.code"
                  :label="`${f.name} (${f.code})`"
                  :value="f.code"
                >
                  <div class="opt-row" :class="{ picked: isSelected(f.code) }">
                    <span class="opt-mark">{{ isSelected(f.code) ? '✓' : '' }}</span>
                    <span class="opt-name">{{ f.name }}</span>
                    <span class="opt-code">{{ f.code }}</span>
                    <span v-if="isSelected(f.code)" class="opt-badge">已选</span>
                  </div>
                </el-option>
              </el-option-group>
            </el-select>
            <el-button size="small" @click="selectAllFeatures">全选</el-button>
            <el-button size="small" @click="form.feature_cols = []">清空</el-button>
            <span class="muted">已选 {{ form.feature_cols.length }} / {{ allFeatureCodes.length }}</span>
          </div>
          <div class="tag-box" :class="{ empty: !form.feature_cols.length }">
            <template v-if="selectedFactorItems.length">
              <el-tag
                v-for="item in selectedFactorItems"
                :key="item.code"
                closable
                effect="plain"
                type="primary"
                class="factor-tag"
                @close="removeFeature(item.code)"
              >
                <span class="tag-name">{{ item.name }}</span>
                <span class="tag-code">{{ item.code }}</span>
              </el-tag>
            </template>
            <span v-else class="muted">从下拉选择因子后会显示在这里，点标签可取消</span>
          </div>
        </el-form-item>

        <el-collapse>
          <el-collapse-item title="XGBoost 超参数" name="xgb">
            <el-row :gutter="16">
              <el-col v-for="p in xgbParamFields" :key="p.key" :xs="12" :md="6">
                <el-form-item>
                  <template #label>
                    <el-tooltip :content="p.tip" placement="top" :show-after="200">
                      <span class="param-label">{{ p.label }}</span>
                    </el-tooltip>
                  </template>
                  <el-input-number
                    v-model="form.xgb_params[p.key]"
                    :min="p.min"
                    :max="p.max"
                    :step="p.step"
                    :precision="p.precision"
                    style="width: 100%"
                  />
                </el-form-item>
              </el-col>
            </el-row>
          </el-collapse-item>
          <el-collapse-item title="LightGBM 超参数" name="lgb">
            <el-row :gutter="16">
              <el-col v-for="p in lgbParamFields" :key="p.key" :xs="12" :md="6">
                <el-form-item>
                  <template #label>
                    <el-tooltip :content="p.tip" placement="top" :show-after="200">
                      <span class="param-label">{{ p.label }}</span>
                    </el-tooltip>
                  </template>
                  <el-input-number
                    v-model="form.lgb_params[p.key]"
                    :min="p.min"
                    :max="p.max"
                    :step="p.step"
                    :precision="p.precision"
                    style="width: 100%"
                  />
                </el-form-item>
              </el-col>
            </el-row>
          </el-collapse-item>
        </el-collapse>
      </el-form>
    </div>

    <el-collapse v-if="hasRun" v-model="resultOpen" class="result-collapse">
      <el-collapse-item v-for="block in resultBlocks" :key="block.key" :name="block.key">
        <template #title>
          <div class="result-title">
            <span>{{ block.title }}</span>
            <el-tag v-if="block.pending" size="small" type="info">等待结果</el-tag>
            <el-tag v-else-if="block.error" size="small" type="danger">失败</el-tag>
            <el-tag v-else-if="block.result?.ok" size="small" type="success">完成</el-tag>
            <el-tag v-else-if="block.result" size="small" type="warning">未成功</el-tag>
          </div>
        </template>

        <div v-if="block.error" class="err-box">{{ block.error }}</div>
        <template v-else-if="block.result">
          <div class="conclusion">{{ block.result.conclusion }}</div>
          <el-table v-if="block.result.comparison?.length" :data="block.result.comparison" stripe size="small">
            <el-table-column prop="stock_name" label="股票" min-width="110" />
            <el-table-column prop="stock_code" label="代码" width="120" />
            <el-table-column label="AUC" width="90">
              <template #default="{ row }">{{ fmt(row.auc) }}</template>
            </el-table-column>
            <el-table-column label="Accuracy" width="100">
              <template #default="{ row }">{{ fmt(row.accuracy) }}</template>
            </el-table-column>
            <el-table-column label="Precision" width="100">
              <template #default="{ row }">{{ fmt(row.precision) }}</template>
            </el-table-column>
            <el-table-column label="Recall" width="90">
              <template #default="{ row }">{{ fmt(row.recall) }}</template>
            </el-table-column>
            <el-table-column label="F1" width="90">
              <template #default="{ row }">{{ fmt(row.f1) }}</template>
            </el-table-column>
            <el-table-column prop="n_samples" label="样本数" width="90" />
          </el-table>
          <div v-if="block.result.errors?.length" class="err-box">
            <div v-for="e in block.result.errors" :key="e.stock_code">
              {{ e.stock_name }} ({{ e.stock_code }}): {{ e.message }}
            </div>
          </div>

          <div v-for="item in block.result.results || []" :key="`${block.key}-${item.stock_code}`" class="stock-block">
            <h3>{{ item.stock_name }} ({{ item.stock_code }})</h3>
            <p class="muted">
              标签 跌={{ item.label_dist?.down }} 涨={{ item.label_dist?.up }} ·
              预测样本 {{ item.n_samples }} · 稳定性 {{ item.stability }} ·
              月度准确率 std={{ fmt(item.monthly_accuracy_std) }}
            </p>
            <el-row :gutter="16">
              <el-col :md="10">
                <div class="sub-title">混淆矩阵</div>
                <el-table :data="cmRows(item)" size="small" border>
                  <el-table-column prop="label" label="" width="90" />
                  <el-table-column prop="pred_down" label="预测跌" />
                  <el-table-column prop="pred_up" label="预测涨" />
                </el-table>
              </el-col>
              <el-col :md="14">
                <div class="sub-title">
                  按月准确率
                  <span class="muted">共 {{ item.monthly?.length || 0 }} 个月，可滚动查看</span>
                </div>
                <div class="monthly-scroll">
                  <el-table :data="item.monthly || []" size="small" height="320" stripe>
                    <el-table-column prop="month" label="月份" width="110" />
                    <el-table-column prop="samples" label="样本" width="80" />
                    <el-table-column label="Accuracy">
                      <template #default="{ row }">{{ fmt(row.accuracy) }}</template>
                    </el-table-column>
                    <el-table-column label="AUC">
                      <template #default="{ row }">{{ row.auc == null ? 'N/A' : fmt(row.auc) }}</template>
                    </el-table-column>
                  </el-table>
                </div>
              </el-col>
            </el-row>
            <div class="sub-title">最近预测（最多 60 条）</div>
            <el-table :data="item.predictions" size="small" max-height="280" stripe>
              <el-table-column prop="date" label="日期" width="120" />
              <el-table-column label="真实">
                <template #default="{ row }">{{ row.y_true === 1 ? '涨' : '跌' }}</template>
              </el-table-column>
              <el-table-column label="预测">
                <template #default="{ row }">{{ row.y_pred === 1 ? '涨' : '跌' }}</template>
              </el-table-column>
              <el-table-column label="上涨概率">
                <template #default="{ row }">{{ fmt(row.y_prob) }}</template>
              </el-table-column>
            </el-table>
          </div>

          <div v-if="block.result.logs?.length" class="log-panel">
            <div class="sub-title">运行日志</div>
            <pre class="logs">{{ block.result.logs.join('\n') }}</pre>
          </div>
        </template>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'

const running = ref(false)
const hasRun = ref(false)
const resultOpen = ref([])
const xgbResult = ref(null)
const lgbResult = ref(null)
const xgbError = ref('')
const lgbError = ref('')
const categories = ref([])
const allFeatureCodes = ref([])
const defaultSnapshot = ref(null)
const pendingFactor = ref('')

const xgbParamFields = [
  {
    key: 'n_estimators',
    label: '树的数量',
    min: 10,
    max: 2000,
    step: 10,
    precision: 0,
    tip: 'n_estimators：弱学习器（树）的个数。越大拟合能力越强，也更容易过拟合、训练更慢。默认 200。',
  },
  {
    key: 'max_depth',
    label: '最大深度',
    min: 1,
    max: 16,
    step: 1,
    precision: 0,
    tip: 'max_depth：单棵树的最大深度。越大模型越复杂，过拟合风险越高。默认 5。',
  },
  {
    key: 'learning_rate',
    label: '学习率',
    min: 0.001,
    max: 1,
    step: 0.01,
    precision: 3,
    tip: 'learning_rate：每一步对残差的学习步长。较小通常更稳，但需要更多树。默认 0.05。',
  },
  {
    key: 'subsample',
    label: '样本抽样',
    min: 0.1,
    max: 1,
    step: 0.05,
    precision: 2,
    tip: 'subsample：每棵树随机使用的训练样本比例。小于 1 可减轻过拟合。默认 0.8。',
  },
  {
    key: 'colsample_bytree',
    label: '特征抽样',
    min: 0.1,
    max: 1,
    step: 0.05,
    precision: 2,
    tip: 'colsample_bytree：每棵树随机使用的特征比例。小于 1 可降低特征共线性影响。默认 0.8。',
  },
  {
    key: 'min_child_weight',
    label: '叶节点权重',
    min: 0,
    max: 100,
    step: 1,
    precision: 0,
    tip: 'min_child_weight：叶子节点所需的最小样本权重和。越大越保守，越不容易学到噪声。默认 10。',
  },
  {
    key: 'reg_alpha',
    label: 'L1正则',
    min: 0,
    max: 10,
    step: 0.1,
    precision: 2,
    tip: 'reg_alpha：L1 正则系数。越大越倾向把不重要特征权重压成 0，模型更稀疏。默认 0.1。',
  },
  {
    key: 'reg_lambda',
    label: 'L2正则',
    min: 0,
    max: 20,
    step: 0.1,
    precision: 2,
    tip: 'reg_lambda：L2 正则系数。越大权重越平滑，有助于抑制过拟合。默认 1.0。',
  },
  {
    key: 'random_state',
    label: '随机种子',
    min: 0,
    max: 9999,
    step: 1,
    precision: 0,
    tip: 'random_state：随机数种子。固定后抽样和建树可复现。默认 42。',
  },
]

const lgbParamFields = [
  {
    key: 'n_estimators',
    label: '树的数量',
    min: 10,
    max: 2000,
    step: 10,
    precision: 0,
    tip: 'n_estimators：弱学习器（树）的个数。越大拟合能力越强，也更容易过拟合、训练更慢。默认 200。',
  },
  {
    key: 'max_depth',
    label: '最大深度',
    min: 1,
    max: 16,
    step: 1,
    precision: 0,
    tip: 'max_depth：单棵树的最大深度。LightGBM 还受叶子数约束。默认 5。',
  },
  {
    key: 'learning_rate',
    label: '学习率',
    min: 0.001,
    max: 1,
    step: 0.01,
    precision: 3,
    tip: 'learning_rate：每一步对残差的学习步长。较小通常更稳，但需要更多树。默认 0.05。',
  },
  {
    key: 'num_leaves',
    label: '叶子数',
    min: 2,
    max: 256,
    step: 1,
    precision: 0,
    tip: 'num_leaves：一棵树最多允许的叶子节点数。LightGBM 按叶子生长，该值通常比 2^max_depth 更关键。默认 31。',
  },
  {
    key: 'subsample',
    label: '样本抽样',
    min: 0.1,
    max: 1,
    step: 0.05,
    precision: 2,
    tip: 'subsample：每棵树随机使用的训练样本比例。小于 1 可减轻过拟合。默认 0.8。',
  },
  {
    key: 'colsample_bytree',
    label: '特征抽样',
    min: 0.1,
    max: 1,
    step: 0.05,
    precision: 2,
    tip: 'colsample_bytree：每棵树随机使用的特征比例。小于 1 可降低特征共线性影响。默认 0.8。',
  },
  {
    key: 'min_child_samples',
    label: '叶最小样本',
    min: 1,
    max: 200,
    step: 1,
    precision: 0,
    tip: 'min_child_samples：叶子节点所需的最少样本数。越大越保守，越不容易学到噪声。默认 20。',
  },
  {
    key: 'reg_alpha',
    label: 'L1正则',
    min: 0,
    max: 10,
    step: 0.1,
    precision: 2,
    tip: 'reg_alpha：L1 正则系数。越大越倾向把不重要特征权重压成 0。默认 0.1。',
  },
  {
    key: 'reg_lambda',
    label: 'L2正则',
    min: 0,
    max: 20,
    step: 0.1,
    precision: 2,
    tip: 'reg_lambda：L2 正则系数。越大权重越平滑，有助于抑制过拟合。默认 1.0。',
  },
  {
    key: 'random_state',
    label: '随机种子',
    min: 0,
    max: 9999,
    step: 1,
    precision: 0,
    tip: 'random_state：随机数种子。固定后抽样和建树可复现。默认 42。',
  },
]

const factorNameMap = computed(() => {
  const map = {}
  for (const cat of categories.value) {
    for (const f of cat.features || []) {
      map[f.code] = f.name || f.code
    }
  }
  return map
})

const selectedFactorItems = computed(() =>
  form.feature_cols.map((code) => ({
    code,
    name: factorNameMap.value[code] || code,
  })),
)

const resultBlocks = computed(() => [
  {
    key: 'xgb',
    title: 'XGBoost 结果',
    result: xgbResult.value,
    error: xgbError.value,
    pending: running.value && !xgbResult.value && !xgbError.value,
  },
  {
    key: 'lgb',
    title: 'LightGBM 结果',
    result: lgbResult.value,
    error: lgbError.value,
    pending: running.value && !lgbResult.value && !lgbError.value,
  },
])

const form = reactive({
  stock_codes: '600519.SH,688981.SH',
  range: ['2023-01-01', '2025-12-31'],
  label_horizon: 1,
  min_bars: 120,
  train_days: 120,
  retrain_interval: 20,
  feature_cols: [],
  xgb_params: {
    n_estimators: 200,
    max_depth: 5,
    learning_rate: 0.05,
    subsample: 0.8,
    colsample_bytree: 0.8,
    min_child_weight: 10,
    reg_alpha: 0.1,
    reg_lambda: 1.0,
    random_state: 42,
    eval_metric: 'logloss',
    verbosity: 0,
    use_label_encoder: false,
  },
  lgb_params: {
    n_estimators: 200,
    max_depth: 5,
    learning_rate: 0.05,
    num_leaves: 31,
    subsample: 0.8,
    colsample_bytree: 0.8,
    min_child_samples: 20,
    reg_alpha: 0.1,
    reg_lambda: 1.0,
    random_state: 42,
    verbose: -1,
  },
})

function saveSnapshot() {
  defaultSnapshot.value = JSON.parse(JSON.stringify({
    stock_codes: form.stock_codes,
    range: [...form.range],
    label_horizon: form.label_horizon,
    min_bars: form.min_bars,
    train_days: form.train_days,
    retrain_interval: form.retrain_interval,
    feature_cols: [...form.feature_cols],
    xgb_params: { ...form.xgb_params },
    lgb_params: { ...form.lgb_params },
  }))
}

function applySharedMeta(meta) {
  if (!meta) return
  form.stock_codes = meta.default_stock_codes || form.stock_codes
  form.range = [meta.default_start_date, meta.default_end_date]
  form.label_horizon = meta.default_label_horizon
  form.min_bars = meta.default_min_bars
  form.train_days = meta.default_train_days
  form.retrain_interval = meta.default_retrain_interval
  form.feature_cols = [...(meta.default_feature_cols || [])]
  categories.value = meta.categories || []
  allFeatureCodes.value = meta.default_feature_cols || []
}

function resetDefaults() {
  const snap = defaultSnapshot.value
  if (!snap) return
  form.stock_codes = snap.stock_codes
  form.range = [...snap.range]
  form.label_horizon = snap.label_horizon
  form.min_bars = snap.min_bars
  form.train_days = snap.train_days
  form.retrain_interval = snap.retrain_interval
  form.feature_cols = [...snap.feature_cols]
  Object.assign(form.xgb_params, snap.xgb_params)
  Object.assign(form.lgb_params, snap.lgb_params)
}

function selectAllFeatures() {
  form.feature_cols = [...allFeatureCodes.value]
  pendingFactor.value = ''
}

function isSelected(code) {
  return form.feature_cols.includes(code)
}

function removeFeature(code) {
  form.feature_cols = form.feature_cols.filter((c) => c !== code)
}

function toggleFeatureFromSelect(code) {
  if (!code) return
  if (isSelected(code)) removeFeature(code)
  else form.feature_cols = [...form.feature_cols, code]
  pendingFactor.value = ''
}

function fmt(v) {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '-'
  return Number(v).toFixed(4)
}

function cmRows(item) {
  const cm = item.confusion_matrix || [[0, 0], [0, 0]]
  return [
    { label: '实际跌', pred_down: cm[0][0], pred_up: cm[0][1] },
    { label: '实际涨', pred_down: cm[1][0], pred_up: cm[1][1] },
  ]
}

function errMessage(err) {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string' && detail) return detail
  if (typeof err?.message === 'string' && err.message) return err.message
  return '请求失败'
}

function sharedPredictBody() {
  return {
    stock_codes: form.stock_codes.trim(),
    start_date: form.range[0],
    end_date: form.range[1],
    label_horizon: form.label_horizon,
    min_bars: form.min_bars,
    train_days: form.train_days,
    retrain_interval: form.retrain_interval,
    feature_cols: form.feature_cols,
  }
}

async function runPredict() {
  if (!form.range?.[0] || !form.range?.[1]) {
    ElMessage.warning('请选择样本区间')
    return
  }
  if (!form.stock_codes.trim()) {
    ElMessage.warning('请填写股票代码')
    return
  }
  running.value = true
  hasRun.value = true
  resultOpen.value = []
  xgbResult.value = null
  lgbResult.value = null
  xgbError.value = ''
  lgbError.value = ''
  const base = sharedPredictBody()
  try {
    const [xgbSettled, lgbSettled] = await Promise.allSettled([
      api.xgboostPredict({ ...base, xgb_params: form.xgb_params }),
      api.lightgbmPredict({ ...base, lgb_params: form.lgb_params }),
    ])
    if (xgbSettled.status === 'fulfilled') xgbResult.value = xgbSettled.value
    else xgbError.value = errMessage(xgbSettled.reason)
    if (lgbSettled.status === 'fulfilled') lgbResult.value = lgbSettled.value
    else lgbError.value = errMessage(lgbSettled.reason)

    const xgbOk = Boolean(xgbResult.value?.ok)
    const lgbOk = Boolean(lgbResult.value?.ok)
    if (xgbOk && lgbOk) ElMessage.success('XGBoost 与 LightGBM 预测完成')
    else if (xgbOk || lgbOk) ElMessage.warning('仅一侧预测完成，请展开对应结果查看')
    else ElMessage.warning('两侧预测均未成功')
  } finally {
    running.value = false
  }
}

onMounted(async () => {
  try {
    const [xgbMeta, lgbMeta] = await Promise.allSettled([api.xgboostMeta(), api.lightgbmMeta()])
    if (xgbMeta.status === 'fulfilled') {
      applySharedMeta(xgbMeta.value)
      if (xgbMeta.value?.default_xgb_params) Object.assign(form.xgb_params, xgbMeta.value.default_xgb_params)
    } else if (lgbMeta.status === 'fulfilled') {
      applySharedMeta(lgbMeta.value)
    }
    if (lgbMeta.status === 'fulfilled' && lgbMeta.value?.default_lgb_params) {
      Object.assign(form.lgb_params, lgbMeta.value.default_lgb_params)
    }
  } catch {
    // keep hardcoded CASE defaults
  }
  saveSnapshot()
})
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.page-header h2 {
  margin: 0 0 4px;
  font-size: 18px;
}
.page-header p {
  margin: 0;
  color: #6b7280;
  font-size: 13px;
}
.panel {
  background: #fff;
  border: 1px solid var(--mq-border, #e5e7eb);
  border-radius: 10px;
  padding: 14px 16px;
}
.cfg-form :deep(.el-form-item__label) {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
}
.feature-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
  width: 100%;
}
.tag-box {
  width: 100%;
  min-height: 72px;
  max-height: 168px;
  overflow: auto;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-content: flex-start;
  padding: 10px 12px;
  border: 1px solid var(--mq-border, #e5e7eb);
  border-radius: 8px;
  background: #f8fafc;
}
.tag-box.empty {
  align-items: center;
}
.factor-tag {
  margin: 0;
  height: auto;
  padding: 4px 8px;
  line-height: 1.2;
}
.tag-name {
  font-weight: 600;
  margin-right: 6px;
}
.tag-code {
  font-size: 11px;
  color: #64748b;
}
.opt-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.opt-row.picked {
  color: #0f766e;
  font-weight: 600;
}
.opt-mark {
  width: 14px;
  color: #0f766e;
}
.opt-name {
  flex: 1;
}
.opt-code {
  font-size: 12px;
  color: #94a3b8;
}
.opt-badge {
  font-size: 11px;
  color: #0f766e;
  background: rgba(15, 118, 110, 0.1);
  border-radius: 4px;
  padding: 0 6px;
}
.param-label {
  display: inline-flex;
  align-items: center;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  border-bottom: 1px dashed #94a3b8;
  cursor: help;
}
.param-label:hover {
  color: #0f766e;
  border-bottom-color: #0f766e;
}
.conclusion {
  font-weight: 600;
  margin-bottom: 12px;
}
.sub-title {
  font-weight: 600;
  margin: 12px 0 8px;
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.monthly-scroll {
  border: 1px solid var(--mq-border, #e5e7eb);
  border-radius: 8px;
  overflow: hidden;
}
.err-box {
  margin-top: 10px;
  color: #dc2626;
  font-size: 13px;
}
.log-panel {
  max-height: 360px;
  overflow: auto;
}
.logs {
  margin: 0;
  font-size: 12px;
  line-height: 1.45;
  white-space: pre-wrap;
  color: #374151;
}
h3 {
  margin: 0 0 6px;
  font-size: 16px;
}
.result-collapse {
  background: #fff;
  border: 1px solid var(--mq-border, #e5e7eb);
  border-radius: 10px;
  padding: 4px 12px 8px;
}
.result-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
}
.stock-block {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--mq-border, #e5e7eb);
}
.muted {
  color: #6b7280;
  font-size: 13px;
}
</style>

<style>
.factor-select-popper .el-select-group__title,
.factor-select-popper .el-select-group__label {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
  background: #e2e8f0;
  padding: 8px 12px;
  margin: 6px 0 2px;
  line-height: 1.4;
  letter-spacing: 0.4px;
  border-left: 4px solid #0f766e;
  position: sticky;
  top: 0;
  z-index: 3;
}
.factor-select-popper .el-select-group__title::before {
  content: none;
}
.factor-select-popper .el-select-dropdown__item {
  padding-left: 22px;
}
</style>
