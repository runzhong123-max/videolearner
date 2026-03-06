# VideoLearner - Phase 2（Record 记录系统：按钮触发版）

当前阶段已实现：
- Phase 0：项目骨架 + 数据库骨架
- Phase 0.5：数据库连接生命周期修复
- Phase 1：项目管理 + 学习会话状态机
- Phase 2：Record 记录系统（截图记录 + 灵感文本记录）

## 1. Phase 2 范围
已实现：
- StudyPage 新增“记录截图”“记录灵感”按钮
- 记录写入 `records` 表
- 当前 Session 的 Record 时间线展示
- 图片写入本地文件系统，数据库仅存路径/元数据

明确不包含：
- 全局快捷键
- Prompt 管理
- AI 生成
- OCR

## 2. 记录规则
- `record_type` 当前支持：`image`、`text`
- 预留后续扩展：`image_text`
- `timestamp_offset` 记录相对 Session 开始时间（秒）
- Record 必须绑定当前 `in_progress` Session
- Session 已 `finished` 后禁止继续记录

## 3. 文件系统与数据库分工
- 图片文件保存路径：
  - `data/projects/project_{project_id}/assets/session_{session_id}/`
- 数据库 `records` 表保存：
  - `session_id`
  - `record_type`
  - `content`（文本记录内容）
  - `file_path`（图片相对路径）
  - `timestamp_offset`
  - `created_at`
  - `metadata_json`
  - `is_inspiration`

## 4. 环境与运行
```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m app.db.init_db
python -m app.main
```

## 5. 自动化测试
```powershell
python tests/smoke_test.py
python tests/phase1_flow_test.py
python tests/phase2_record_test.py
python -W error::ResourceWarning tests/smoke_test.py
```

## 6. Phase 2 手工验证
1. 在 `Project` 页面创建并选择当前项目。
2. 在 `Study` 页面点击“开始学习”。
3. 点击“记录灵感”，输入文本后确认。
4. 点击“记录截图”。
5. 查看时间线，按时间顺序出现 text/image 记录。
6. 点击“结束学习”。
7. 再次点击记录按钮，应提示当前无进行中会话。
8. 重启应用，确认项目、Session、Record 仍可读取。
