<template>
  <section>
    <header class="page-header">
      <h1>采集记录管理</h1>
      <p>管理不可移动文物采集记录，支持查询、编辑以及 CSV 导入导出</p>
    </header>

    <div class="toolbar card top-space">
      <el-input
        v-model="filters.keyword"
        placeholder="文物名称/四普编号/地址/管理单位"
        clearable
        style="max-width: 320px"
      />
      <el-select v-model="filters.category" clearable placeholder="文物类别" style="width: 180px">
        <el-option v-for="item in categoryOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-select v-model="filters.level" clearable placeholder="保护级别" style="width: 220px">
        <el-option v-for="item in levelOptions" :key="item.value" :label="item.label" :value="item.value" />
      </el-select>
      <el-button type="primary" :loading="loading" @click="handleSearch">查询</el-button>
      <el-button :loading="exporting" @click="handleExport">导出 CSV</el-button>
      <el-upload
        :show-file-list="false"
        accept=".csv"
        :before-upload="beforeImport"
      >
        <el-button type="success" :loading="importing">导入 CSV</el-button>
      </el-upload>
      <el-button type="warning" :loading="sipu.running" @click="openSipuDialog">四普抓取并导入</el-button>
    </div>

    <div class="card top-space">
      <el-table :data="rows" stripe v-loading="loading">
        <el-table-column prop="sip_code" label="四普编号" width="150" />
        <el-table-column label="文物名称" min-width="200">
          <template #default="scope">
            <a
              class="heritage-view-link"
              href="#"
              @click.prevent="openPreview(scope.row)"
            >
              {{ scope.row.name }}
            </a>
          </template>
        </el-table-column>
        <el-table-column prop="category_label" label="文物类别" width="130" />
        <el-table-column prop="level_label" label="保护级别" width="190" />
        <el-table-column prop="address" label="详细地址" min-width="220" show-overflow-tooltip />
        <el-table-column prop="manager" label="管理单位" width="160" show-overflow-tooltip />
        <el-table-column label="坐标" min-width="170">
          <template #default="scope">
            {{ scope.row.longitude }}, {{ scope.row.latitude }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="scope">
            <el-button link type="primary" @click="openEdit(scope.row)">编辑</el-button>
            <el-button link type="danger" @click="handleDelete(scope.row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="top-space" style="display: flex; justify-content: flex-end">
        <el-pagination
          background
          layout="total, prev, pager, next"
          :total="pagination.total"
          :page-size="pagination.page_size"
          :current-page="pagination.page"
          @current-change="onPageChange"
        />
      </div>
    </div>

    <el-dialog v-model="dialog.visible" title="编辑采集记录" width="920px">
      <el-form label-width="110px" label-position="left">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="文物名称">
              <el-input v-model="dialog.form.name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="采集编号">
              <el-input v-model="dialog.form.survey_code" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="曾用名/别名">
              <el-input v-model="dialog.form.former_name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="时代">
              <el-input v-model="dialog.form.era" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="文物类别">
              <el-select v-model="dialog.form.category" style="width: 100%">
                <el-option v-for="item in categoryOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="保护级别">
              <el-select v-model="dialog.form.level" style="width: 100%">
                <el-option v-for="item in levelOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="文物类型">
          <el-input v-model="dialog.form.heritage_type" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="省/自治区">
              <el-input v-model="dialog.form.province" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="市/州">
              <el-input v-model="dialog.form.city" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="县/区">
              <el-input v-model="dialog.form.county" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="乡镇/街道">
              <el-input v-model="dialog.form.township" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="村/社区">
              <el-input v-model="dialog.form.village" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="经度">
              <el-input v-model="dialog.form.longitude" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="纬度">
              <el-input v-model="dialog.form.latitude" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="坐标系">
              <el-input v-model="dialog.form.coordinate_system" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="海拔(m)">
              <el-input v-model="dialog.form.altitude" />
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="占地面积">
              <el-input v-model="dialog.form.area" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="详细地址">
          <el-input v-model="dialog.form.address" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="权属">
              <el-select v-model="dialog.form.ownership" style="width: 100%">
                <el-option v-for="item in ownershipOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="保存现状">
              <el-select v-model="dialog.form.preservation_status" style="width: 100%">
                <el-option v-for="item in preservationOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="权属单位/人">
          <el-input v-model="dialog.form.ownership_detail" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="使用单位/人">
              <el-input v-model="dialog.form.user_unit" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="管理单位">
              <el-input v-model="dialog.form.management_unit" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="管理责任人">
          <el-input v-model="dialog.form.manager" />
        </el-form-item>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="公布批次">
              <el-input v-model="dialog.form.protection_announced_batch" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="公布日期">
              <el-input v-model="dialog.form.protection_announced_date" placeholder="YYYY-MM-DD" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="保护措施">
          <el-checkbox v-model="dialog.form.has_marker_stele">已设立保护标志碑</el-checkbox>
          <el-checkbox v-model="dialog.form.has_protection_zone_announced">已公布保护范围</el-checkbox>
          <el-checkbox v-model="dialog.form.has_construction_control_zone_announced">已公布建设控制地带</el-checkbox>
        </el-form-item>
        <el-form-item label="消失/迁移">
          <el-checkbox v-model="dialog.form.is_disappeared">是否已消失</el-checkbox>
          <el-checkbox v-model="dialog.form.is_relocated">是否涉及迁移</el-checkbox>
        </el-form-item>
        <el-form-item label="消失原因" v-if="dialog.form.is_disappeared">
          <el-input v-model="dialog.form.disappear_reason" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="迁移说明" v-if="dialog.form.is_relocated">
          <el-input v-model="dialog.form.relocation_note" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="破坏原因">
          <el-input v-model="dialog.form.damage_cause" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="威胁因素">
          <el-input v-model="dialog.form.threat_factors" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="现状描述">
          <el-input v-model="dialog.form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="dialog.form.remarks" type="textarea" :rows="2" />
        </el-form-item>

        <el-form-item label="坐标点列表">
          <div class="coord-editor">
            <div class="coord-editor-actions">
              <el-button size="small" type="primary" plain @click="addCoordPoint">新增坐标点</el-button>
              <span class="coord-editor-hint">经纬度必填，类型支持边界点/标志点/其他</span>
            </div>
            <el-table :data="dialog.form.coord_list" size="small" border empty-text="暂无坐标点，请点击新增">
              <el-table-column label="序号" width="62" align="center">
                <template #default="scope">{{ scope.$index + 1 }}</template>
              </el-table-column>
              <el-table-column label="类型" width="130">
                <template #default="scope">
                  <el-select v-model="scope.row.type" style="width: 100%">
                    <el-option label="边界点" value="boundary" />
                    <el-option label="标志点" value="marker" />
                    <el-option label="其他" value="other" />
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column label="经度" min-width="130">
                <template #default="scope">
                  <el-input v-model="scope.row.longitude" placeholder="如 90.335167" />
                </template>
              </el-table-column>
              <el-table-column label="纬度" min-width="130">
                <template #default="scope">
                  <el-input v-model="scope.row.latitude" placeholder="如 42.870531" />
                </template>
              </el-table-column>
              <el-table-column label="海拔(m)" min-width="110">
                <template #default="scope">
                  <el-input v-model="scope.row.altitude" placeholder="选填" />
                </template>
              </el-table-column>
              <el-table-column label="来源" min-width="130">
                <template #default="scope">
                  <el-input v-model="scope.row.sourceTag" placeholder="GPS/手工" />
                </template>
              </el-table-column>
              <el-table-column label="说明" min-width="150">
                <template #default="scope">
                  <el-input v-model="scope.row.description" placeholder="点位说明" />
                </template>
              </el-table-column>
              <el-table-column label="备注" min-width="130">
                <template #default="scope">
                  <el-input v-model="scope.row.remark" placeholder="备注" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="76" align="center" fixed="right">
                <template #default="scope">
                  <el-button link type="danger" @click="removeCoordPoint(scope.$index)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="dialog.loading" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <HeritageA4PreviewDialog
      v-model="preview.visible"
      :record="preview.row"
      :loading="preview.loading"
      page-title="不可移动文物采集登记表预览"
    />

    <el-dialog v-model="sipu.visible" title="四普系统抓取并自动导入" width="860px" class="sipu-dialog" :close-on-click-modal="false">
      <el-alert
        title="将使用你填写的参数抓取四普数据，先生成 CSV，再自动导入当前系统"
        type="info"
        :closable="false"
        style="margin-bottom: 12px"
      />
      <div class="sipu-progress-wrap" v-if="sipu.running">
        <div class="sipu-progress-head">
          <span>正在执行抓取与导入，请勿关闭窗口...</span>
          <span class="sipu-progress-value">{{ sipu.progressPercent }}%</span>
        </div>
        <el-progress :percentage="sipu.progressPercent" :stroke-width="16" status="warning" />
        <div class="sipu-progress-tip">{{ sipu.progressText }}</div>
      </div>

      <div class="sipu-form-scroll">
      <el-form label-width="135px" label-position="left" class="sipu-form">
        <el-row :gutter="12">
          <el-col :span="24">
            <el-form-item label="四普系统地址">
              <el-input v-model="sipu.form.base_url" placeholder="如 http://202.41.243.152:9046" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="24">
            <el-form-item label="JSESSIONID">
              <el-input v-model="sipu.form.jsessionid" placeholder="必填" show-password />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="区县代码">
              <el-input v-model="sipu.form.user_county" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="输出CSV路径">
              <el-input v-model="sipu.form.output" placeholder="默认 data/sipu_base_data.csv" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="每页条数">
              <el-input-number v-model="sipu.form.page_size" :min="1" :max="500" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="并发线程">
              <el-input-number v-model="sipu.form.workers" :min="1" :max="32" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="超时秒数">
              <el-input-number v-model="sipu.form.timeout" :min="5" :max="120" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="重试次数">
              <el-input-number v-model="sipu.form.retries" :min="1" :max="10" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="最多页数">
              <el-input-number v-model="sipu.form.max_pages" :min="1" :max="5000" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="排序字段">
              <el-input v-model="sipu.form.sort_field" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="排序方向">
              <el-select v-model="sipu.form.sort_type" style="width: 100%">
                <el-option label="倒序(desc)" value="desc" />
                <el-option label="正序(asc)" value="asc" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="列表接口路径">
              <el-input v-model="sipu.form.endpoint" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="详情接口路径">
              <el-input v-model="sipu.form.detail_endpoint" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="12">
          <el-col :span="8">
            <el-form-item label="backStatus">
              <el-input v-model="sipu.form.back_status" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="抓详情页">
              <el-switch v-model="sipu.form.enable_detail" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="严格模式">
              <el-switch v-model="sipu.form.strict" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      </div>
      <template #footer>
        <el-button @click="sipu.visible = false">取消</el-button>
        <el-button type="warning" :loading="sipu.running" @click="submitSipuFetchImport">开始抓取并导入</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import HeritageA4PreviewDialog from '../../components/HeritageA4PreviewDialog.vue'

import {
  deleteImmovableHeritage,
  exportImmovableHeritage,
  fetchAndImportSipuImmovable,
  fetchHeritagePreview,
  fetchImmovableHeritageList,
  importImmovableHeritage,
  patchImmovableHeritage
} from '../../api/heritageApi'

const loading = ref(false)
const importing = ref(false)
const exporting = ref(false)
const rows = ref([])
const categoryOptions = ref([])
const levelOptions = ref([])
const ownershipOptions = ref([])
const preservationOptions = ref([])

const filters = reactive({
  keyword: '',
  category: '',
  level: ''
})

const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0
})

const dialog = reactive({
  visible: false,
  loading: false,
  editId: null,
  form: {
    survey_code: '',
    name: '',
    former_name: '',
    era: '',
    category: '',
    level: '',
    heritage_type: '',
    province: '',
    city: '',
    county: '',
    township: '',
    village: '',
    address: '',
    coordinate_system: 'CGCS2000',
    altitude: '',
    area: '',
    longitude: '',
    latitude: '',
    ownership: 'state',
    ownership_detail: '',
    user_unit: '',
    management_unit: '',
    manager: '',
    preservation_status: '一般',
    is_disappeared: false,
    disappear_reason: '',
    is_relocated: false,
    relocation_note: '',
    protection_announced_batch: '',
    protection_announced_date: '',
    has_marker_stele: false,
    has_protection_zone_announced: false,
    has_construction_control_zone_announced: false,
    damage_cause: '',
    threat_factors: '',
    description: '',
    remarks: '',
    coord_list: []
  }
})

const preview = reactive({
  visible: false,
  loading: false,
  row: {},
})

const sipu = reactive({
  visible: false,
  running: false,
  progressPercent: 0,
  progressText: '准备中',
  form: {
    base_url: 'http://202.41.243.152:9046',
    endpoint: '/immovableListController.do?queryRelicList',
    detail_endpoint: '/tBBdataBasicController.do?goBasicView',
    jsessionid: '',
    user_county: '650421',
    page_size: 100,
    timeout: 25,
    max_pages: null,
    sort_field: 'update_date',
    sort_type: 'desc',
    back_status: '0',
    workers: 8,
    retries: 3,
    output: 'data/sipu_base_data.csv',
    enable_detail: true,
    strict: false,
  },
})

let sipuProgressTimer = null

function startSipuProgress() {
  sipu.progressPercent = 8
  sipu.progressText = '正在连接四普系统并拉取列表...'
  if (sipuProgressTimer) {
    clearInterval(sipuProgressTimer)
  }
  sipuProgressTimer = setInterval(() => {
    if (!sipu.running) {
      clearInterval(sipuProgressTimer)
      sipuProgressTimer = null
      return
    }
    if (sipu.progressPercent < 90) {
      const step = sipu.progressPercent < 35 ? 4 : (sipu.progressPercent < 70 ? 2 : 1)
      sipu.progressPercent += step
    }
    if (sipu.progressPercent >= 30 && sipu.progressPercent < 70) {
      sipu.progressText = '正在批量抓取详情并转换CSV...'
    } else if (sipu.progressPercent >= 70) {
      sipu.progressText = '正在导入系统并进行联动同步...'
    }
  }, 700)
}

function stopSipuProgress(success = false) {
  if (sipuProgressTimer) {
    clearInterval(sipuProgressTimer)
    sipuProgressTimer = null
  }
  if (success) {
    sipu.progressPercent = 100
    sipu.progressText = '处理完成'
  } else {
    sipu.progressText = '执行中断'
  }
}

function buildParams() {
  return {
    page: pagination.page,
    page_size: pagination.page_size,
    keyword: filters.keyword,
    category: filters.category,
    level: filters.level
  }
}

async function loadRows() {
  loading.value = true
  try {
    const result = await fetchImmovableHeritageList(buildParams())
    if (!result.success) {
      throw new Error(result.message || '加载失败')
    }

    rows.value = result.rows || []
    Object.assign(pagination, result.pagination || {})
    categoryOptions.value = result.meta?.category_choices || []
    levelOptions.value = result.meta?.level_choices || []
    ownershipOptions.value = result.meta?.ownership_choices || []
    preservationOptions.value = result.meta?.preservation_choices || []
  } catch (error) {
    ElMessage.error(error?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pagination.page = 1
  loadRows()
}

function onPageChange(page) {
  pagination.page = page
  loadRows()
}

function openEdit(row) {
  dialog.editId = row.id
  dialog.form = {
    survey_code: row.survey_code || row.sip_code || '',
    name: row.name || '',
    former_name: row.former_name || '',
    era: row.era || '',
    category: row.category || '',
    level: row.level || '',
    heritage_type: row.heritage_type || '',
    province: row.province || '',
    city: row.city || '',
    county: row.county || '',
    township: row.township || '',
    village: row.village || '',
    address: row.address || '',
    coordinate_system: row.coordinate_system || 'CGCS2000',
    altitude: row.altitude ?? '',
    area: row.area ?? '',
    longitude: row.longitude,
    latitude: row.latitude,
    ownership: row.ownership || 'state',
    ownership_detail: row.ownership_detail || '',
    user_unit: row.user_unit || '',
    management_unit: row.management_unit || '',
    manager: row.manager || '',
    preservation_status: row.preservation_status || '一般',
    is_disappeared: !!row.is_disappeared,
    disappear_reason: row.disappear_reason || '',
    is_relocated: !!row.is_relocated,
    relocation_note: row.relocation_note || '',
    protection_announced_batch: row.protection_announced_batch || '',
    protection_announced_date: row.protection_announced_date || '',
    has_marker_stele: !!row.has_marker_stele,
    has_protection_zone_announced: !!row.has_protection_zone_announced,
    has_construction_control_zone_announced: !!row.has_construction_control_zone_announced,
    damage_cause: row.damage_cause || '',
    threat_factors: row.threat_factors || '',
    description: row.description || '',
    remarks: row.remarks || '',
    coord_list: Array.isArray(row.coord_list) ? row.coord_list : []
  }
  dialog.visible = true
}

function addCoordPoint() {
  if (!Array.isArray(dialog.form.coord_list)) {
    dialog.form.coord_list = []
  }
  dialog.form.coord_list.push({
    type: 'boundary',
    longitude: '',
    latitude: '',
    altitude: '',
    sourceTag: '',
    description: '',
    remark: ''
  })
}

function removeCoordPoint(index) {
  if (!Array.isArray(dialog.form.coord_list)) {
    return
  }
  dialog.form.coord_list.splice(index, 1)
}

function normalizeCoordList(rawList) {
  if (!Array.isArray(rawList)) {
    return []
  }

  const result = []
  for (const item of rawList) {
    const type = ['boundary', 'marker', 'other'].includes(item?.type) ? item.type : 'other'
    const lon = Number(item?.longitude)
    const lat = Number(item?.latitude)

    if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
      continue
    }
    if (lon < -180 || lon > 180 || lat < -90 || lat > 90) {
      continue
    }

    const altitudeValue = item?.altitude
    let altitude = null
    if (altitudeValue !== '' && altitudeValue !== null && altitudeValue !== undefined) {
      const parsedAlt = Number(altitudeValue)
      altitude = Number.isFinite(parsedAlt) ? parsedAlt : null
    }

    result.push({
      type,
      longitude: lon,
      latitude: lat,
      altitude,
      sourceTag: String(item?.sourceTag || '').trim(),
      description: String(item?.description || '').trim(),
      remark: String(item?.remark || '').trim()
    })
  }
  return result
}

async function openPreview(row) {
  preview.row = row || {}
  preview.visible = true
  preview.loading = true
  try {
    if (!row?.id) {
      return
    }
    const result = await fetchHeritagePreview({ immovable_id: row.id })
    if (result?.success && result?.data) {
      preview.row = { ...row, ...result.data }
    }
  } catch (error) {
    ElMessage.warning(error?.message || '预览详情加载失败，已展示当前行数据')
  } finally {
    preview.loading = false
  }
}

async function submitEdit() {
  dialog.loading = true
  try {
    const coordList = normalizeCoordList(dialog.form.coord_list)
    if (Array.isArray(dialog.form.coord_list) && dialog.form.coord_list.length > 0 && coordList.length === 0) {
      throw new Error('坐标点列表存在无效经纬度，请检查后再保存')
    }

    const payload = {
      ...dialog.form,
      longitude: Number(dialog.form.longitude),
      latitude: Number(dialog.form.latitude),
      altitude: dialog.form.altitude === '' ? null : Number(dialog.form.altitude),
      area: dialog.form.area === '' ? null : Number(dialog.form.area),
      coord_list: coordList
    }

    const result = await patchImmovableHeritage(dialog.editId, payload)
    if (!result.success) {
      throw new Error(result.message || '保存失败')
    }
    ElMessage.success('保存成功')
    dialog.visible = false
    await loadRows()
  } catch (error) {
    ElMessage.error(error?.message || '保存失败')
  } finally {
    dialog.loading = false
  }
}

async function handleDelete(row) {
  if (!row?.id) {
    return
  }

  try {
    await ElMessageBox.confirm(`确认删除文物档案“${row.name || row.id}”吗？`, '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }

  try {
    const result = await deleteImmovableHeritage(row.id)
    if (!result?.success) {
      throw new Error(result?.message || '删除失败')
    }

    ElMessage.success('删除成功')
    if (rows.value.length === 1 && pagination.page > 1) {
      pagination.page -= 1
    }
    await loadRows()
  } catch (error) {
    ElMessage.error(error?.message || '删除失败')
  }
}

async function handleExport() {
  exporting.value = true
  try {
    const response = await exportImmovableHeritage({
      keyword: filters.keyword,
      category: filters.category,
      level: filters.level
    })

    const blob = new Blob([response.data], { type: 'text/csv;charset=utf-8-sig;' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `采集记录_${new Date().toISOString().slice(0, 10)}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error(error?.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

async function beforeImport(file) {
  importing.value = true
  try {
    const result = await importImmovableHeritage(file)
    if (!result.success) {
      throw new Error(result.message || '导入失败')
    }
    const summary = result.data || {}
    ElMessage.success(
      `导入完成：新增 ${summary.created_count || 0}，更新 ${summary.updated_count || 0}，跳过 ${summary.skipped_count || 0}`
    )
    pagination.page = 1
    await loadRows()
  } catch (error) {
    ElMessage.error(error?.message || '导入失败')
  } finally {
    importing.value = false
  }

  return false
}

function openSipuDialog() {
  sipu.visible = true
}

async function submitSipuFetchImport() {
  if (!sipu.form.jsessionid) {
    ElMessage.warning('请先填写四普系统 JSESSIONID')
    return
  }

  sipu.running = true
  startSipuProgress()
  try {
    const payload = {
      ...sipu.form,
      skip_detail: !sipu.form.enable_detail,
      max_pages: sipu.form.max_pages || null,
    }
    delete payload.enable_detail

    const result = await fetchAndImportSipuImmovable(payload)
    if (!result?.success) {
      throw new Error(result?.message || '执行失败')
    }

    stopSipuProgress(true)

    const summary = result.data?.import_summary || {}
    ElMessage.success(
      `完成：抓取${result.data?.fetch_count || 0}条，转换${result.data?.csv_written_count || 0}条，导入新增${summary.created_count || 0}条、更新${summary.updated_count || 0}条`
    )
    sipu.visible = false
    pagination.page = 1
    await loadRows()
  } catch (error) {
    stopSipuProgress(false)
    ElMessage.error(error?.message || '抓取并导入失败')
  } finally {
    sipu.running = false
  }
}

onBeforeUnmount(() => {
  if (sipuProgressTimer) {
    clearInterval(sipuProgressTimer)
    sipuProgressTimer = null
  }
})

loadRows()
</script>

<style scoped>
.heritage-view-link {
  color: var(--accent, #409eff);
  text-decoration: none;
  font-weight: 600;
}

.heritage-view-link:hover {
  text-decoration: underline;
}

.coord-editor {
  width: 100%;
}

.coord-editor-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.coord-editor-hint {
  color: #8a8f99;
  font-size: 12px;
}

.sipu-progress-wrap {
  border: 1px solid #fde68a;
  background: #fffbeb;
  border-radius: 10px;
  padding: 10px 12px;
  margin-bottom: 12px;
}

.sipu-progress-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
  color: #92400e;
}

.sipu-progress-value {
  font-weight: 700;
}

.sipu-progress-tip {
  margin-top: 6px;
  font-size: 12px;
  color: #a16207;
}

.sipu-form-scroll {
  max-height: 58vh;
  overflow-y: auto;
  padding-right: 4px;
}

.sipu-form :deep(.el-form-item) {
  margin-bottom: 14px;
}

@media (max-width: 768px) {
  .sipu-form-scroll {
    max-height: 62vh;
  }
}
</style>
