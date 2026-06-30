<template>
  <section>
    <header class="page-header">
      <h1>项目管理</h1>
      <p>新架构首批迁移模块（保留旧页面并行）</p>
    </header>

    <div class="toolbar card">
      <el-input
        v-model="store.filters.keyword"
        placeholder="按项目名/企业名检索"
        clearable
        style="max-width: 320px"
      />
      <el-select v-model="store.filters.status" placeholder="状态筛选" clearable style="width: 220px">
        <el-option label="10_已收文" value="10_已收文" />
        <el-option label="20_初审安全" value="20_初审安全" />
        <el-option label="21_初审涉及" value="21_CHECK_OVERLAP" />
        <el-option label="30_现场勘查完成" value="30_现场勘查完成" />
        <el-option label="40_市局审批中" value="40_市局审批中" />
        <el-option label="45_考古流转中" value="45_考古流转中" />
        <el-option label="50_批复已收到" value="50_批复已收到" />
        <el-option label="60_已结案归档" value="60_已结案归档" />
      </el-select>
      <el-button type="primary" @click="store.loadProjects">查询</el-button>
      <el-button type="success" @click="goCreate">新建项目</el-button>
    </div>

    <div class="card">
      <el-table :data="store.rows" v-loading="store.loading" stripe>
        <el-table-column prop="project_name" label="项目名称" min-width="220" />
        <el-table-column prop="company_name" label="企业单位" min-width="180" />
        <el-table-column prop="receive_date" label="收文日期" width="130" />
        <el-table-column prop="status_label" label="状态" min-width="160" />
        <el-table-column prop="is_overlap_artifact" label="涉及文物" width="110">
          <template #default="scope">
            <el-tag :type="scope.row.is_overlap_artifact ? 'danger' : 'success'">
              {{ scope.row.is_overlap_artifact ? '是' : '否' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="scope">
            <el-button link type="primary" @click="goDetail(scope.row.id)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </section>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

import { useProjectStore } from '../../stores/projectStore'

const store = useProjectStore()
const router = useRouter()

function goCreate() {
  router.push('/projects/new')
}

function goDetail(projectId) {
  router.push(`/projects/${projectId}`)
}

onMounted(() => {
  store.loadProjects()
})
</script>
