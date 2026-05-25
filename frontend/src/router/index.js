import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import AdminDashboard from '../views/AdminDashboard.vue'
import StudentManage from '../views/StudentManage.vue'
import StudentDashboard from '../views/StudentDashboard.vue'

const routes = [
  {
    path: '/',
    redirect: '/login'
  },
  {
    path: '/login',
    name: 'Login',
    component: Login
  },
  // ========== 管理员端路由 ==========
  {
    path: '/admin',
    name: 'AdminDashboard',
    component: AdminDashboard,
    meta: { requiresAuth: true, role: 'admin' }
  },
  {
    path: '/admin/students',
    name: 'StudentManage',
    component: StudentManage,
    meta: { requiresAuth: true, role: 'admin' }
  },
  // ========== 学生端路由 ==========
  {
    path: '/student',
    name: 'StudentDashboard',
    component: StudentDashboard,
    meta: { requiresAuth: true, role: 'student' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫 - 检查登录状态和角色权限
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  const user = JSON.parse(localStorage.getItem('user') || '{}')

  if (to.meta.requiresAuth && !token) {
    next('/login')
  } else if (to.meta.role && user.role !== to.meta.role) {
    // 角色不匹配，重定向到对应的仪表盘
    if (user.role === 'admin') {
      next('/admin')
    } else if (user.role === 'student') {
      next('/student')
    } else {
      next('/login')
    }
  } else {
    next()
  }
})

export default router
