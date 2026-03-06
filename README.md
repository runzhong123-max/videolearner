# VideoLearner - Phase 1（项目管理与学习会话状态机）

当前阶段已打通首个可用闭环：
创建项目 -> 选择项目 -> 开始学习 -> 结束学习 -> 查看 Session。

## 1. 本阶段已实现
- ProjectPage 接入 `ProjectService` / `ProjectRepository`：
  - 项目列表展示
  - 新建/编辑/删除
  - 选择当前项目
- StudyPage 接入 `SessionService` / `SessionRepository`：
  - 显示当前选中项目
  - 开始学习（创建 `in_progress` Session）
  - 结束学习（更新为 `finished` 并写入 `ended_at`）
  - 显示会话状态、开始/结束时间、会话列表
- 主窗口维护当前项目状态，并同步到页面
- SQLite 持久化 Project 与 Session（重启后可读取）

## 2. 状态机规则
- `not_started -> in_progress -> finished`
- 同一时刻只允许一个 `in_progress` Session（全局）
- Session 必须绑定 `project_id`
- 已有进行中 Session 时，重复开始会被拦截并提示

## 3. 当前阶段不包含
- 截图
- 全局快捷键
- OCR
- AI 生成
- Prompt 管理逻辑接入

## 4. 目录（与 Phase 1 相关）
```text
app/
  main.py
  db/
    database.py
    migrations.py
  services/
    errors.py
    project_service.py
    session_service.py
    repository_factory.py
  repositories/
    project_repository.py
    session_repository.py
  ui/
    main_window.py
    pages/
      project_page.py
      study_page.py
tests/
  smoke_test.py
  phase1_flow_test.py
```

## 5. 环境准备
```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

## 6. 初始化数据库
```powershell
python -m app.db.init_db
```

## 7. 启动程序
```powershell
python -m app.main
```

## 8. 运行测试
```powershell
python tests/smoke_test.py
python tests/phase1_flow_test.py
python -W error::ResourceWarning tests/smoke_test.py
```

## 9. 手工验证步骤（Phase 1）
1. 进入 `Project` 页面，创建项目（至少填写名称）。
2. 编辑项目字段：`description/source/goal/tags` 并保存。
3. 点击“设为当前项目”。
4. 切到 `Study` 页面，点击“开始学习”。
5. 再次点击“开始学习”，应提示已有进行中会话。
6. 点击“结束学习”，会话状态应变为 `finished` 且有 `ended_at`。
7. 关闭程序后重新打开，项目与 Session 记录仍存在。
