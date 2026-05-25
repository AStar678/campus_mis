import axios from 'axios'

// 创建 axios 实例
const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器 - 自动附加 Token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器 - 处理401
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    if (error.response && error.response.status === 401) {
      // Token 过期或无效，跳转到登录页
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error.response ? error.response.data : error)
  }
)

// ========== 认证相关 API ==========
export const authApi = {
  login(data) {
    return api.post('/auth/login', data)
  },
  getProfile() {
    return api.get('/auth/profile')
  }
}

// ========== 学生管理 API ==========
export const studentApi = {
  getList(params) {
    return api.get('/students', { params })
  },
  getById(studentId) {
    return api.get(`/students/${studentId}`)
  },
  create(data) {
    return api.post('/students', data)
  },
  update(studentId, data) {
    return api.put(`/students/${studentId}`, data)
  },
  delete(studentId) {
    return api.delete(`/students/${studentId}`)
  }
}

export default api
