# 成绩分析系统全面优化设计文档

## 1. 概述

对现有江苏高考成绩分析系统进行全面优化，分三个阶段推进：基础加固、安全+性能、UI 升级。

**技术栈**（不变）：FastAPI + SQLAlchemy + SQLite + Jinja2 + Bootstrap 5 + ECharts

**使用场景**：教师/教务人员在 PC 桌面浏览器使用

## 2. 现有问题清单

| 类别 | 问题 | 严重程度 |
|------|------|---------|
| Bug | `_get_tier` stub 函数，v1 转换函数不可用 | 高 |
| Deprecated | `db.query(Model).get(id)` 在 SQLAlchemy 2.0 已弃用 | 中 |
| Deprecated | `@app.on_event("startup")` 已弃用 | 中 |
| 安全 | 无认证，任何人可修改数据 | 高 |
| 安全 | 硬编码 secret key | 中 |
| 性能 | N+1 查询（`get_exam_all_totals`、`class_comparison`） | 中 |
| 功能 | 无 API 分页 | 低 |
| 功能 | 前端无错误处理（无 `.catch()`） | 中 |
| 工程 | 无测试 | 高 |
| 工程 | 无 `.gitignore` | 低 |
| 依赖 | `openpyxl` 冗余（pandas 已内置） | 低 |

## 3. 阶段 1：基础加固

### 3.1 项目配置

- 添加 `.gitignore`：覆盖 Python（`__pycache__/`, `*.pyc`, `.venv/`）、SQLite（`*.db`，但保留 `data/` 下的 `.gitkeep`）、IDE（`.vscode/`, `.idea/`）、OS 文件（`.DS_Store`）
- `config.py`：`SECRET_KEY` 改为从环境变量 `GRADE_SECRET_KEY` 读取，保留硬编码默认值用于开发环境
- `requirements.txt`：移除直接列出的 `openpyxl`（pandas 的 `to_excel()` 已自动使用它）

### 3.2 代码 Bug 修复

**conversion_service.py**：
- 删除 `convert_scores_for_subject`（v1）函数及其依赖的 `_get_tier` stub
- 将 `convert_scores_for_subject_v2` 重命名为 `convert_scores_for_subject`（唯一实现）
- 更新所有调用方引用

**全局 SQLAlchemy deprecated API**：
- 搜索所有 `db.query(X).get(id)` 模式，替换为 `db.get(X, id)`
- 涉及文件：`routers/students.py`、`routers/exams.py`、`routers/scores.py`、`services/score_service.py`

**main.py lifespan 迁移**：
- 将 `@app.on_event("startup")` 改为 `lifespan` 上下文管理器
- 在 `FastAPI(lifespan=lifespan)` 中注册

### 3.3 后端测试

**框架**：pytest + pytest-asyncio + httpx

**测试基础设施**：
- `conftest.py`：创建 SQLite 内存数据库的测试 fixture，每个测试用例独立 session
- `TestClient` fixture：基于 httpx.AsyncClient，连接到 FastAPI app

**测试用例**：

```
tests/
├── conftest.py              # fixtures: db session, test client, sample data
├── test_students.py         # 创建/列表/删除学生，班级筛选
├── test_exams.py            # 创建/列表/删除考试，自动生成 9 科
├── test_scores.py           # 成绩录入、批量保存、转换、总分计算
└── test_analysis.py         # 年级统计、班级对比、学科分析 API
```

核心断言：
- 学生创建后可查询到，删除后查不到
- 考试创建后自动生成 9 个 exam_subjects
- 成绩录入后总分计算正确（3 门裸分 + 1 门首选 + 2 门转换分）
- 转换分在 40-100 范围内
- 统计 API 返回的平均分、及格率等数值合理

## 4. 阶段 2：安全 + 性能

### 4.1 简单登录认证

**数据模型**：
```python
class User(Base):
    id: int (PK)
    username: str (unique)
    hashed_password: str
    is_admin: bool (default False)
    created_at: datetime
```

**技术方案**：
- 密码哈希：`passlib[bcrypt]`
- Session 管理：Starlette `SessionMiddleware`（基于 signed cookie，FastAPI 内置支持）
- 登录流程：POST `/api/auth/login` → 验证密码 → 写入 `request.session["user_id"]` → 重定向到首页
- 登出：清除 session
- 依赖注入：`get_current_user()` 函数，从 session 读取 user_id，未登录时重定向到 `/login`

**路由保护**：
- 页面路由：`pages.py` 中所有路由加 `current_user: User = Depends(get_current_user)`
- API 路由：所有 `/api/` 路由加同样的依赖
- `/login` 页面和 `/api/auth/login` 不需要认证

**初始化**：
- 首次启动时，若 users 表为空，自动创建默认管理员 `admin` / `admin123`
- 在首页显示提示："请尽快修改默认密码"

**新增依赖**：`passlib[bcrypt]`、`python-multipart`（已有）、`itsdangerous`

### 4.2 N+1 查询修复

**get_exam_all_totals**（`score_service.py`）：
- 当前：遍历每个学生 → 每个科目单独查询 → N*M 次查询
- 优化：单次 JOIN 查询获取所有成绩，Python 端聚合计算总分
- 预期：从 O(N*M) 降为 O(1) 次数据库查询

**class_comparison**（`stats_service.py`）：
- 当前：遍历每个班级 → 每个科目单独查询平均分
- 优化：使用 SQL `GROUP BY class_id, subject` + `AVG()` 聚合
- 预期：从 O(classes * subjects) 降为 O(1) 次查询

### 4.3 API 分页

为列表类 API 添加分页参数：
- `GET /api/students/?skip=0&limit=50` → 返回 `{items: [...], total: N, skip: 0, limit: 50}`
- `GET /api/exams/?skip=0&limit=20` → 同上格式
- 前端列表页面添加分页控件

### 4.4 前端错误处理

- 在 `static/js/utils.js` 中封装 `apiFetch()` 函数：
  - 自动检查 HTTP 状态码
  - 非 2xx 响应自动弹出 Toast 错误提示
  - 网络错误统一处理
- 所有模板中的 `fetch()` 调用替换为 `apiFetch()`
- 添加 Toast 通知组件（基于 Bootstrap Toast）

## 5. 阶段 3：现代仪表盘 UI 升级

### 5.1 布局重构

**侧边栏**：
- 宽度：展开 240px / 折叠 64px
- 配色：深蓝渐变（#1a1a2e → #16213e）
- 内容：Logo + 导航菜单（带图标）+ 底部用户信息
- 交互：悬停展开子菜单，点击折叠按钮

**顶部栏**：
- 左侧：面包屑导航
- 右侧：用户名 + 登出按钮

**主内容区**：
- 背景：#f5f7fa
- 内容使用白色卡片容器，圆角 8px，轻微阴影
- 响应式网格：Bootstrap grid，最小宽度 1200px 适配

### 5.2 Dashboard 首页

**统计卡片区**（4 列）：
- 学生总数（带班级数副标题）
- 考试总数（带最新考试名称）
- 最新考试平均分（带最高/最低分）
- 最新考试及格率（带环形进度指示）

**图表区**（2 列）：
- 左：学科平均分雷达图（所有学科对比）
- 右：班级总分对比柱状图

**快速操作区**：
- 快捷入口卡片：成绩录入、学生管理、考试管理、数据分析

### 5.3 图表升级

- 统一配色方案：主色 #4A90D9（蓝）、辅色 #67C23A（绿）、#E6A23C（橙）、#F56C6C（红）
- 所有图表添加 tooltip 交互
- 成绩分布柱状图：点击柱子弹出该分数段学生列表
- 趋势折线图：数据点悬浮显示详细分数
- 班级雷达图：支持多班级叠加对比，图例可交互显隐

### 5.4 交互优化

**表格增强**：
- 列排序（点击表头）
- 搜索框实时筛选
- 行数选择器（10/25/50/100）

**操作反馈**：
- 删除操作：Bootstrap Modal 确认对话框
- 表单提交：按钮显示 loading 状态
- 成功操作：绿色 Toast 自动消失（3s）
- 错误操作：红色 Toast 手动关闭

**加载状态**：
- 页面加载使用骨架屏（Skeleton）
- API 请求期间显示 spinner

### 5.5 前端代码组织

```
static/
├── css/
│   └── main.css              # 全局样式变量、布局、组件覆盖
├── js/
│   ├── utils.js              # apiFetch、formatScore、showToast 等工具函数
│   └── charts.js             # ECharts 主题配置、通用图表工厂函数
└── img/
    └── logo.svg              # 系统 Logo
```

模板优化：
- `base.html` 引入 `static/css/main.css` 和 `static/js/utils.js`
- 各页面模板只保留页面特定的 JS 逻辑
- 通用组件（Toast、Modal、Skeleton）在 base 中定义

## 6. 依赖变更

### 新增
- `passlib[bcrypt]` — 密码哈希
- `pytest` + `pytest-asyncio` + `httpx` — 测试（dev 依赖）

### 移除
- `openpyxl`（直接依赖）— pandas 已内置

### 不变
- FastAPI, SQLAlchemy, Jinja2, pandas, uvicorn, python-multipart, aiofiles

## 7. 不做的事（YAGNI）

- 不做多角色权限系统（当前只需简单登录保护）
- 不做前端框架迁移（保持 Jinja2 + 原生 JS）
- 不做数据库迁移（保持 SQLite，数据量不大）
- 不做 WebSocket 实时推送
- 不做移动端适配
- 不做国际化
