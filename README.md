# VideoLearner

Windows 桌面学习工作台（Python + PySide6 + SQLite）。

目标：在看视频学习时低打扰记录截图与灵感文本，并逐步沉淀为结构化学习资产。

## 当前进度
- Phase 0：项目骨架、数据库骨架、主窗口导航壳子、Repository CRUD 骨架
- Phase 0.5：SQLite 连接生命周期修复、smoke test 全绿
- Phase 1：项目管理 + 学习会话状态机
- Phase 2：Record 记录系统（按钮触发版：截图记录 + 灵感文本记录 + 时间线）

## 已实现功能（截至 Phase 2）
- Project 管理：创建、编辑、删除、选择当前项目
- Session 管理：开始学习 / 结束学习
- Session 状态机：`not_started -> in_progress -> finished`
- 全局约束：同一时刻仅允许一个 `in_progress` Session
- Record 记录（按钮触发版）：
  - 记录截图（落盘 + 数据库存路径）
  - 记录灵感文本
  - StudyPage 时间线按时间顺序展示

## 暂未实现（本阶段明确不做）
- 全局快捷键
- Prompt 管理接入
- AI 自动总结
- OCR / 视觉模型

## 技术栈
- Python 3.12
- PySide6
- SQLite（`sqlite3`）
- Pillow（截图）

## 快速开始
```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m app.db.init_db
python -m app.main
```

## 测试
```powershell
python tests/smoke_test.py
python tests/phase1_flow_test.py
python tests/phase2_record_test.py
python -W error::ResourceWarning tests/smoke_test.py
```

## 手工验证（Phase 2）
1. 在 `Project` 页面创建项目并设为当前项目
2. 在 `Study` 页面点击“开始学习”
3. 点击“记录灵感”输入文本
4. 点击“记录截图”
5. 确认时间线出现 text/image 记录
6. 点击“结束学习”
7. 再次记录应被拦截并提示
8. 重启后确认 Project / Session / Record 仍可读取

## 数据存储策略
- SQLite：结构化数据（Project / Session / Record / Note / PromptTemplate）
- 文件系统：图片与导出文件
- 截图路径约定：
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

## 下一步方向（未实现）
- 全局快捷键触发记录
- Prompt 模板分层管理
- Session 结束后 AI 结构化输出
- 导出与回顾增强
