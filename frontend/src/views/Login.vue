<template>
  <div class="login-container">
    <div class="login-card">
      <h2 class="login-title">校园教务管理系统</h2>
      <p class="login-subtitle">Campus MIS</p>
      <el-form
        ref="loginFormRef"
        :model="loginForm"
        :rules="loginRules"
        class="login-form"
        @keyup.enter="handleLogin"
      >
        <el-form-item prop="username">
          <el-input
            v-model="loginForm.username"
            placeholder="请输入用户名"
            prefix-icon="User"
            size="large"
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="loginForm.password"
            type="password"
            placeholder="请输入密码"
            prefix-icon="Lock"
            size="large"
            show-password
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            class="login-btn"
            @click="handleLogin"
          >
            登 录
          </el-button>
        </el-form-item>
      </el-form>
      <div class="login-tips">
        <p>管理员：admin / admin123</p>
        <p>学生：2024001 / 123456</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authApi } from '../api'

const router = useRouter()
const loginFormRef = ref(null)
const loading = ref(false)

const loginForm = reactive({
  username: '',
  password: ''
})

const loginRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const handleLogin = async () => {
  if (!loginFormRef.value) return
  await loginFormRef.value.validate(async (valid) => {
    if (!valid) return

    loading.value = true
    try {
      const res = await authApi.login({
        username: loginForm.username,
        password: loginForm.password
      })

      if (res.code === 200) {
        // 存储 token 和用户信息
        localStorage.setItem('token', res.data.token)
        localStorage.setItem('user', JSON.stringify(res.data.user))
        ElMessage.success('登录成功')
        // 根据角色跳转到不同的仪表盘
        const role = res.data.user.role
        if (role === 'admin') {
          router.push('/admin')
        } else if (role === 'student') {
          router.push('/student')
        } else {
          router.push('/login')
        }
      } else {
        ElMessage.error(res.message || '登录失败')
      }
    } catch (error) {
      ElMessage.error(error.message || '登录失败，请检查网络连接')
    } finally {
      loading.value = false
    }
  })
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-card {
  width: 400px;
  padding: 40px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.login-title {
  text-align: center;
  font-size: 24px;
  color: #303133;
  margin-bottom: 8px;
}

.login-subtitle {
  text-align: center;
  font-size: 14px;
  color: #909399;
  margin-bottom: 30px;
}

.login-form {
  width: 100%;
}

.login-btn {
  width: 100%;
}

.login-tips {
  margin-top: 16px;
  text-align: center;
  font-size: 12px;
  color: #909399;
}
</style>
