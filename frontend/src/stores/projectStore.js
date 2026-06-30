import { defineStore } from 'pinia'

import { fetchProjectList } from '../api/projectApi'

export const useProjectStore = defineStore('project', {
  state: () => ({
    loading: false,
    rows: [],
    filters: {
      keyword: '',
      status: ''
    }
  }),
  actions: {
    async loadProjects() {
      this.loading = true
      try {
        const data = await fetchProjectList({
          keyword: this.filters.keyword,
          status: this.filters.status
        })
        this.rows = data.rows || []
      } finally {
        this.loading = false
      }
    }
  }
})
