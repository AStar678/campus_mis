<template>
  <div class="student-dashboard">
    <!-- 顶部导航栏 -->
    <div class="top-nav">
      <div class="nav-left">
        <h2>校园教务管理系统</h2>
        <span class="nav-badge">学生端</span>
      </div>
      <div class="nav-right">
        <span class="user-info">{{ currentUser.username }}</span>
        <el-button type="danger" size="small" @click="handleLogout">退出登录</el-button>
      </div>
    </div>

    <!-- 主内容区域 -->
    <div class="dashboard-content">
      <!-- 个人信息卡片 -->
      <div class="profile-card" v-loading="loading">
        <div class="profile-header">
          <div class="avatar">{{ studentInfo.name ? studentInfo.name[0] : '?' }}</div>
          <div class="profile-basic">
            <h3>{{ studentInfo.name }}</h3>
            <p>学号: {{ studentInfo.student_id }}</p>
          </div>
          <div class="gpa-badge">
            <div class="gpa-value">{{ studentInfo.gpa }}</div>
            <div class="gpa-label">GPA</div>
          </div>
        </div>
        <div class="profile-details">
          <div class="detail-item">
            <span class="detail-label">性别</span>
            <span class="detail-value">{{ studentInfo.gender }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">学院</span>
            <span class="detail-value">{{ studentInfo.college || '-' }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">专业</span>
            <span class="detail-value">{{ studentInfo.major || '-' }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">班级</span>
            <span class="detail-value">{{ studentInfo.class_name || '-' }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">入学年份</span>
            <span class="detail-value">{{ studentInfo.enrollment_year || '-' }}</span>
          </div>
        </div>
      </div>

      <!-- 服务入口 -->
      <h3 class="section-title">教务服务</h3>
      <div class="service-grid">
        <div class="service-card disabled">
          <div class="service-icon">📖</div>
          <div class="service-name">选课系统</div>
          <div class="service-desc">查看可选课程，提交选课申请</div>
          <div class="service-badge">即将上线</div>
        </div>
        <div class="service-card disabled">
          <div class="service-icon">📅</div>
          <div class="service-name">我的课表</div>
          <div class="service-desc">查看本学期个人课表</div>
          <div class="service-badge">即将上线</div>
        </div>
        <div class="service-card disabled">
          <div class="service-icon">📊</div>
          <div class="service-name">成绩查询</div>
          <div class="service-desc">查询各科成绩与GPA统计</div>
          <div class="service-badge">即将上线</div>
        </div>
        <div class="service-card disabled">
          <div class="service-icon">📝</div>
          <div class="service-name">学业报告</div>
          <div class="service-desc">查看学分完成情况与学业分析</div>
          <div class="service-badge">即将上线</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { studentApi } from '../api'

const router = useRouter()
const currentUser = ref(JSON.parse(localStorage.getItem('user') || '{}'))
const loading = ref(false)

const studentInfo = ref({
  student_id: '',
  name: '',
  gender: '',
  college: '',
  major: '',
  class_name: '',
  gpa: 0,
  enrollment_year: null
})

const fetchMyInfo = async () => {
  loading.value = true
  try {
    // 学生通过 ref_id (即学号) 获取自己的信息
    const studentId = currentUser.value.ref_id
    if (!studentId) {
      ElMessage.warning('未绑定学生信息')
      return
    }
    const res = await studentApi.getById(studentId)
    if (res.code === 200) {
      studentInfo.value = res.data
    }
  } catch (error) {
    ElMessage.error('获取个人信息失败')
  } finally {
    loading.value = false
  }
}

const handleLogout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  router.push('/login')
}

onMounted(() => {
  fetchMyInfo()
})
</script>

<style scoped>
.student-dashboard {
  min-height: 100vh;
  background-color: #f5f7fa;
}

.top-nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 24px;
  background: white;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.nav-left h2 {
  color: #303133;
  font-size: 18px;
}

.nav-badge {
  background: #67c23a;
  color: white;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-info {
  color: #606266;
  font-size: 14px;
}

.dashboard-content {
  max-width: 900px;
  margin: 0 auto;
  padding: 24px;
}

/* 个人信息卡片 */
.profile-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 32px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.profile-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid #ebeef5;
}

.avatar {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: bold;
}

.profile-basic h3 {
  font-size: 20px;
  color: #303133;
  margin-bottom: 4px;
}

.profile-basic p {
  font-size: 14px;
  color: #909399;
}

.gpa-badge {
  margin-left: auto;
  text-align: center;
  background: #ecf5ff;
  padding: 12px 20px;
  border-radius: 8px;
}

.gpa-value {
  font-size: 28px;
  font-weight: bold;
  color: #409eff;
}

.gpa-label {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

.profile-details {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-label {
  font-size: 12px;
  color: #909399;
}

.detail-value {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
}

/* 服务入口 */
.section-title {
  color: #303133;
  font-size: 16px;
  margin-bottom: 16px;
}

.service-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.service-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  position: relative;
  overflow: hidden;
}

.service-card:not(.disabled):hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.12);
}

.service-card.disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.service-icon {
  font-size: 28px;
  margin-bottom: 8px;
}

.service-name {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 4px;
}

.service-desc {
  font-size: 12px;
  color: #909399;
}

.service-badge {
  position: absolute;
  top: 10px;
  right: 10px;
  background: #e6a23c;
  color: white;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 3px;
}
</style>
