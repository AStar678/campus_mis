<template>
  <div class="student-manage">
    <!-- 顶部导航 -->
    <div class="header">
      <div class="header-left">
        <el-button text @click="$router.push('/admin')">&lt; 返回</el-button>
        <h2>学生信息管理</h2>
      </div>
      <div class="header-right">
        <span class="user-info">{{ currentUser.username }} ({{ roleText }})</span>
        <el-button type="danger" size="small" @click="handleLogout">退出登录</el-button>
      </div>
    </div>

    <!-- 搜索和操作栏 -->
    <div class="toolbar">
      <el-input
        v-model="searchKeyword"
        placeholder="搜索学号或姓名"
        style="width: 250px"
        clearable
        @clear="fetchStudents"
        @keyup.enter="fetchStudents"
      >
        <template #append>
          <el-button @click="fetchStudents">搜索</el-button>
        </template>
      </el-input>
      <el-button v-if="isAdmin" type="primary" @click="openDialog('add')">
        新增学生
      </el-button>
    </div>

    <!-- 学生列表表格 -->
    <el-table :data="students" border stripe style="width: 100%" v-loading="tableLoading">
      <el-table-column prop="student_id" label="学号" width="120" />
      <el-table-column prop="name" label="姓名" width="100" />
      <el-table-column prop="gender" label="性别" width="70" />
      <el-table-column prop="college" label="学院" width="150" />
      <el-table-column prop="major" label="专业" width="150" />
      <el-table-column prop="class_name" label="班级" width="120" />
      <el-table-column prop="gpa" label="GPA" width="80" />
      <el-table-column prop="enrollment_year" label="入学年份" width="100" />
      <el-table-column label="操作" width="180" fixed="right" v-if="isAdmin">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="openDialog('edit', row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="pagination">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.perPage"
        :total="pagination.total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @size-change="fetchStudents"
        @current-change="fetchStudents"
      />
    </div>

    <!-- 新增/编辑对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogType === 'add' ? '新增学生' : '编辑学生'"
      width="500px"
    >
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="80px">
        <el-form-item label="学号" prop="student_id">
          <el-input v-model="formData.student_id" :disabled="dialogType === 'edit'" />
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input v-model="formData.name" />
        </el-form-item>
        <el-form-item label="性别" prop="gender">
          <el-radio-group v-model="formData.gender">
            <el-radio value="男">男</el-radio>
            <el-radio value="女">女</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="学院" prop="college">
          <el-input v-model="formData.college" />
        </el-form-item>
        <el-form-item label="专业" prop="major">
          <el-input v-model="formData.major" />
        </el-form-item>
        <el-form-item label="班级" prop="class_name">
          <el-input v-model="formData.class_name" />
        </el-form-item>
        <el-form-item label="入学年份" prop="enrollment_year">
          <el-input-number v-model="formData.enrollment_year" :min="2000" :max="2030" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { studentApi } from '../api'

const router = useRouter()

// 当前用户信息
const currentUser = ref(JSON.parse(localStorage.getItem('user') || '{}'))
const isAdmin = computed(() => currentUser.value.role === 'admin')
const roleText = computed(() => {
  const map = { admin: '管理员', teacher: '教师', student: '学生' }
  return map[currentUser.value.role] || '未知'
})

// 表格数据
const students = ref([])
const tableLoading = ref(false)
const searchKeyword = ref('')
const pagination = reactive({
  page: 1,
  perPage: 10,
  total: 0
})

// 对话框
const dialogVisible = ref(false)
const dialogType = ref('add')
const formRef = ref(null)
const submitLoading = ref(false)

const formData = reactive({
  student_id: '',
  name: '',
  gender: '男',
  college: '',
  major: '',
  class_name: '',
  enrollment_year: 2024
})

const formRules = {
  student_id: [{ required: true, message: '请输入学号', trigger: 'blur' }],
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }]
}

// 获取学生列表
const fetchStudents = async () => {
  tableLoading.value = true
  try {
    const res = await studentApi.getList({
      page: pagination.page,
      per_page: pagination.perPage,
      keyword: searchKeyword.value
    })
    if (res.code === 200) {
      students.value = res.data.list
      pagination.total = res.data.total
    }
  } catch (error) {
    ElMessage.error('获取学生列表失败')
  } finally {
    tableLoading.value = false
  }
}

// 打开对话框
const openDialog = (type, row = null) => {
  dialogType.value = type
  if (type === 'edit' && row) {
    Object.assign(formData, row)
  } else {
    Object.assign(formData, {
      student_id: '',
      name: '',
      gender: '男',
      college: '',
      major: '',
      class_name: '',
      enrollment_year: 2024
    })
  }
  dialogVisible.value = true
}

// 提交表单
const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return

    submitLoading.value = true
    try {
      if (dialogType.value === 'add') {
        const res = await studentApi.create(formData)
        if (res.code === 201) {
          ElMessage.success('学生创建成功')
          dialogVisible.value = false
          fetchStudents()
        } else {
          ElMessage.error(res.message || '创建失败')
        }
      } else {
        const res = await studentApi.update(formData.student_id, formData)
        if (res.code === 200) {
          ElMessage.success('学生信息更新成功')
          dialogVisible.value = false
          fetchStudents()
        } else {
          ElMessage.error(res.message || '更新失败')
        }
      }
    } catch (error) {
      ElMessage.error(error.message || '操作失败')
    } finally {
      submitLoading.value = false
    }
  })
}

// 删除学生
const handleDelete = (row) => {
  ElMessageBox.confirm(`确定要删除学生 ${row.name} (${row.student_id}) 吗？`, '确认删除', {
    type: 'warning'
  }).then(async () => {
    try {
      const res = await studentApi.delete(row.student_id)
      if (res.code === 200) {
        ElMessage.success('删除成功')
        fetchStudents()
      } else {
        ElMessage.error(res.message || '删除失败')
      }
    } catch (error) {
      ElMessage.error('删除失败')
    }
  }).catch(() => {})
}

// 退出登录
const handleLogout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  router.push('/login')
}

onMounted(() => {
  fetchStudents()
})
</script>

<style scoped>
.student-manage {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 16px 20px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-left h2 {
  color: #303133;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-info {
  color: #606266;
  font-size: 14px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding: 16px 20px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.el-table {
  border-radius: 8px;
  overflow: hidden;
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
  padding: 12px 20px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}
</style>
