# VideoLearner

Windows 桌面学习工作台（Python + PySide6 + SQLite）。

## 当前进度
- Phase 0：项目骨架、数据库骨架、主窗口导航壳子、Repository CRUD 骨架
- Phase 0.5：数据库连接生命周期修复、smoke test 全绿
- Phase 1：项目管理 + 学习会话状态机
- Phase 2：Record 按钮触发版（截图记录、灵感记录、时间线展示）
- Phase 3：Prompt 管理与输出配置（不接入真实 AI）
- Phase 3.5：历史浏览与数据管理增强（Session/Record 删除、北京时间显示）

## Phase 3.5 已实现
- StudyPage 支持自由选择并查看当前项目任意历史 Session
- 支持删除 finished Session（禁止删除 in_progress）
- 删除 Session 时清理：
  - 数据库中的 Session 本身
  - 关联 Record / Note（通过外键级联）
  - 会话资源目录与图片文件（缺失文件只告警，不阻塞删除）
- 支持删除单条 Record：
  - text：删除数据库记录
  - image：先尝试删除文件，再删除数据库记录
- UI 时间显示统一为北京时间中文格式：
  - Session：`YYYY年M月D日 HH:MM`
  - Record 时间线：`HH:MM:SS`

## 本阶段明确不包含
- AI 请求
- 全局快捷键
- OCR / 视觉模型

## 技术栈
- Python 3.12
- PySide6
- SQLite（标准库 sqlite3）
- Pillow（截图，仅 Phase 2 使用）

## 快速开始
```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m app.db.init_db
python -m app.main
```

## 自动化测试
```powershell
python tests/smoke_test.py
python tests/phase1_flow_test.py
python tests/phase2_record_test.py
python tests/phase3_prompt_output_test.py
python tests/phase35_history_management_test.py
python -W error::ResourceWarning tests/smoke_test.py
```

## 存储策略
- SQLite：Project / Session / Record / Note / PromptTemplate / OutputProfile
- 文件系统：截图文件与导出文件

截图路径约定：
- `data/projects/project_{project_id}/assets/session_{session_id}/`

## 目录结构
```text
app/
  db/
  models/
  repositories/
  services/
  ui/
  utils/
tests/
assets/
exports/
docs/
```
