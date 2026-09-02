import { defineStore } from 'pinia'

import { fetchProjectList } from '../api/projectApi'

export const useProjectStore = defineStore('project', {
  state: () => ({
    loading: false,
    rows: [],
    summary: {
      total: 0,
      in_progress: 0,
      archived: 0,
      pending_precheck: 0,
      overlap: 0,
      status_counts: []
    },
    filters: {
      keyword: '',
      status: '',
      workflowPath: ''
    }
  }),
  actions: {
    async loadProjects() {
      this.loading = true
      try {
        const data = await fetchProjectList({
          keyword: this.filters.keyword,
          status: this.filters.status,
          workflowPath: this.filters.workflowPath
        })
        this.rows = data.rows || []
        if (data.summary) {
          this.summary = data.summary
        }
      } finally {
        this.loading = false
      }
    }
  }
})
