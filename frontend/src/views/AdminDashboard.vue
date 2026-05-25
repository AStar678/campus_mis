<template>
  <div class="admin-dashboard">
    <!-- 顶部导航栏 -->
    <div class="top-nav">
      <div class="nav-left">
        <h2>校园教务管理系统</h2>
        <span class="nav-badge">管理员端</span>
      </div>
      <div class="nav-right">
        <span class="user-info">{{ currentUser.username }} (管理员)</span>
        <el-button type="danger" size="small" @click="handleLogout">退出登录</el-button>
      </div>
    </div>

    <!-- 主内容区域 -->
    <div class="dashboard-content">
      <h3 class="section-title">数据概览</h3>
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-icon student-icon">👨‍🎓</div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.studentCount }}</div>
            <div class="stat-label">学生总数</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon teacher-icon">👨‍🏫</div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.teacherCount }}</div>
            <div class="stat-label">教师总数</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon course-icon">📚</div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.courseCount }}</div>
            <div class="stat-label">课程总数</div>
          </div>
        </div>
      </div>

      <h3 class="section-title">管理功能</h3>
      <div class="service-grid">
        <div class="service-card" @click="$router.push('/admin/students')">
          <div class="service-icon">📋</div>
          <div class="service-name">学生管理</div>
          <div class="service-desc">查看、新增、编辑、删除学生信息</div>
        </div>
        <div class="service-card disabled">
          <div class="service-icon">📖</div>
          <div class="service-name">课程管理</div>
          <div class="service-desc">发布课程、设置容量与时间（即将上线）</div>
          <div class="service-badge">即将上线</div>
        </div>
        <div class="service-card disabled">
          <div class="service-icon">📝</div>
          <div class="service-name">成绩管理</div>
          <div class="service-desc">确认成绩、查看统计分析（即将上线）</div>
          <div class="service-badge">即将上线</div>
        </div>
        <div class="service-card disabled">
          <div class="service-icon">📊</div>
          <div class="service-name">统计分析</div>
          <div class="service-desc">选课统计、成绩分布、GPA排行（即将上线）</div>
          <div class="service-badge">即将上线</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { studentApi } from '../api'

const router = useRouter()
const currentUser = ref(JSON.parse(localStorage.getItem('user') || '{}'))

const stats = reactive({
  studentCount: 0,
  teacherCount: 0,
  courseCount: 0
})

const fetchStats = async () => {
  try {
    const res = await studentApi.getList({ page: 1, per_page: 1 })
    if (res.code === 200) {
      stats.studentCount = res.data.total
    }
  } catch (e) {
    // ignore
  }
  // 教师和课程数暂用占位，后续接入对应微服务
  stats.teacherCount = 2
  stats.courseCount = 3
}

const handleLogout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  router.push('/login')
}

onMounted(() => {
  fetchStats()
})
</script>

<style scoped>
.admin-dashboard {
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
  background: #409eff;
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
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px;
}

.section-title {
  color: #303133;
  font-size: 16px;
  margin-bottom: 16px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 32px;
}

.stat-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.stat-icon {
  font-size: 36px;
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
}

.student-icon { background: #ecf5ff; }
.teacher-icon { background: #f0f9eb; }
.course-icon { background: #fef0f0; }

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}

.service-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.service-card {
  background: white;
  border-radius: 8px;
  padding: 24px;
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
  font-size: 32px;
  margin-bottom: 12px;
}

.service-name {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 6px;
}

.service-desc {
  font-size: 13px;
  color: #909399;
}

.service-badge {
  position: absolute;
  top: 12px;
  right: 12px;
  background: #e6a23c;
  color: white;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 3px;
}
</style>
