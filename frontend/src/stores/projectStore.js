import { defineStore } from 'pinia'

import { fetchProjectList } from '../api/projectApi'

export const useProjectStore = defineStore('project', {
  state: () => ({
    loading: false,
    rows: [],
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
      } finally {
        this.loading = false
      }
    }
  }
})
