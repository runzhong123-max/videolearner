# VideoLearner

Windows 桌面学习工作台（Python + PySide6 + SQLite）。

## 当前进度
- Phase 0：项目骨架、数据库骨架、主窗口导航壳子、Repository CRUD 骨架
- Phase 0.5：数据库连接生命周期修复、smoke test 全绿
- Phase 1：项目管理 + 学习会话状态机
- Phase 2：Record 按钮触发版（截图记录、灵感记录、时间线展示）
- Phase 3：Prompt 管理与输出配置（Global / Project / Session）
- Phase 3.5：历史浏览与数据管理增强（历史 Session 选择、删除、时间格式化、Record 删除）
- Phase 4：AI 生成笔记闭环（基于当前选中 Session）
- Phase 4.5：AI Provider 抽象层 + 输出 contract 稳定化
- Phase 5：Session / Record / Note 浏览与阅读体验升级
- Phase 5.5：Record 智能对话（text/insight 优先）
- Phase 6：AI Provider 设置中心 + 生成体验增强（基础版）
- Phase 7：快捷键与高效工作流增强（基础版）
- Phase 8：OCR / image 多模态问答（最小闭环）/ 活动窗口优先截图（含 fallback）
- Phase 9：轻量整理增强与可选复盘入口（Note 版本保留 + 复盘附加区）
- Phase P1：Prompt System & Image UX Polish（默认 Prompt 体系 + Image 交互增强）

## Phase 5 ~ 9 已实现
- StudyPage 升级为 Session 浏览区 / Record 时间线区 / 详情预览区
- Session 列表显示：标题、状态、开始时间、Record 数量、是否有 Note
- Record 时间线支持 image 缩略图、text/insight 摘要、北京时间与相对时间
- 详情区支持图片大图预览、文本全文预览、Session Note 概览
- Record 详情区接入 Record 级 AI 对话：开始/继续对话、历史消息展示、输入框发送
- 对话按 `record_id` 持久化到数据库，可再次打开同一 Record 继续追问
- image Record 支持最小可用问答链路（优先 OCR 文本 + 图片元信息 + 历史对话）
- image Record 详情区支持 OCR 状态与 OCR 文本展示，可手动触发 / 重新执行 OCR / 复制 OCR 文本
- OCR 正式支持本地 `local_ocr`（Tesseract + pytesseract），并保留 `mock_ocr` 供离线测试
- CaptureService 支持 `full_screen` / `active_window` / `region(future)` 模式接口
- `active_window` 不可用时自动回退 `full_screen`，并写入 capture metadata
- NotePage 升级为分块阅读（Summary / Inspirations / Expansion / Guidance + 可选模块）
- Note 支持轻量版本保留与版本切换（重新生成不覆盖旧版）
- Note 支持轻量复盘附加区（review_questions / key_points / follow_up_tasks）
- Note 支持轻量标记（加入复习列表 / 标记重点 / 稍后复习）
- 新增 AI Settings 页面：可设置默认 Provider、功能路由、Provider 参数（api_key/base_url/model/timeout）
- 新增最小功能路由：`session_note_provider`、`record_chat_provider`，未配置时回退 `default_provider`
- 新增 Provider 连接测试：mock 离线直通；真实 Provider 走最小请求并返回可读结果
- 新增全局快捷键管理（Windows 优先）和 Shortcuts 配置页面
- Prompt 文件化：`app/prompts/system_prompt.txt`、`note_generation.txt`、`record_chat.txt`、`image_chat.txt`（缺失时自动回退内置默认）
- PromptPage 支持一键恢复 `Reset to VL Default Prompt`
- Image Record 详情区支持：双击全屏查看（滚轮缩放/拖拽平移/ESC 关闭）、拖拽导出到系统、右键菜单（Open Image / Show in Explorer / Copy Image / Copy Path / Delete）

## 快捷键默认值（Phase 7）
- 开始学习：`ctrl+alt+s`
- 暂停学习：`ctrl+alt+p`
- 继续学习：`ctrl+alt+r`
- 结束学习：`ctrl+alt+e`
- 记录截图：`ctrl+alt+c`
- 记录灵感：`ctrl+shift+a`

说明：`Tab` 在全局热键场景与系统/输入焦点冲突高，默认未采用；可在 Shortcuts 页面手动改为 `tab`。

## AI Provider
可选 Provider：
- `AI_PROVIDER=mock`（默认）
- `AI_PROVIDER=openai`
- `AI_PROVIDER=deepseek`
- `AI_PROVIDER=glm`

相关环境变量：
- `OPENAI_API_KEY`
- `DEEPSEEK_API_KEY`
- `GLM_API_KEY`

兼容说明：
- 未设置 `AI_PROVIDER` 时，若检测到旧变量 `VIDEOLEARNER_AI_API_URL` / `VIDEOLEARNER_AI_API_KEY`，系统会自动走 OpenAI 兼容 provider。

> 不要把 API Key 写入代码或仓库。

## Provider 统一返回结构（开发者）
Provider 层统一返回 `AIGenerationResult`：
- `content: str`
- `provider: str`
- `model: str | None`
- `raw_response: dict | None`
- `usage: dict | None`
- `metadata: dict | None`

业务层（`AIService/NoteService`）只依赖统一结果，不处理 provider-specific 结构。

## AI 输出 Contract
`AIResponseNormalizer` 固定输出并校验以下 contract：
- `summary`（必填）
- `expansion`（必填）
- `inspirations`（缺失时补空；若当前 Session 要求 insight 则必须非空）
- `guidance`（缺失时补空）

兼容旧业务键：
- `extension` -> `expansion` 的别名
- `insight` -> `inspirations` 的别名

## Mock 模式
- 默认 `AI_PROVIDER=mock`
- 不走网络、无 API 费用
- 适合 smoke test、本地调试、离线开发
- 支持可注入 mock provider 做边界测试（缺字段/非法结构/抛异常）

## AI 异常分类
- `AIConfigurationError`：provider/model/key 配置非法
- `AINetworkError`：请求超时、连接失败等传输错误
- `AIProviderResponseError`：HTTP 非 200、响应结构非法、无 content
- `AIContractError`：输出不满足 sections contract

## 技术栈
- Python 3.12+（已在 3.14 环境验证可运行）
- PySide6
- SQLite（标准库 sqlite3）
- Pillow（截图）
- requests（模型调用）
- keyboard（Windows 全局快捷键）
- pytesseract（本地 OCR）
- Tesseract OCR（系统安装）

## 快速开始
```powershell
py -3 -m venv .venv
.venv\Scripts\activate
py -m pip install -r requirements.txt
py -m app.db.init_db

# 按需配置 AI Provider（开发推荐 mock）
$env:AI_PROVIDER="mock"
# $env:AI_PROVIDER="openai"
# $env:OPENAI_API_KEY="your-openai-key"
# $env:AI_PROVIDER="deepseek"
# $env:DEEPSEEK_API_KEY="your-deepseek-key"
# $env:AI_PROVIDER="glm"
# $env:GLM_API_KEY="your-glm-key"

py -m app.main
```


## 本地 OCR（Tesseract）
- OCR Provider 支持：`mock_ocr`（模拟） / `local_ocr`（本地真实 OCR）
- 推荐默认语言：`chi_sim+eng`
- Windows 默认安装路径常见为：`C:\Program Files\Tesseract-OCR\tesseract.exe`

### Windows 安装步骤
1. 安装 Tesseract（包含中文语言包 `chi_sim`）。
2. 在应用中打开 `AI Settings` 页面，找到 OCR 设置区。
3. 设置：
   - `OCR Provider = local_ocr`
   - `Tesseract Path = C:\Program Files\Tesseract-OCR\tesseract.exe`（按本机实际路径）
   - `OCR Language = chi_sim+eng`
4. 点击 `Test OCR` 验证配置。

### mock_ocr 与 local_ocr 区别
- `mock_ocr`：离线模拟文本，适合测试，不依赖本机安装。
- `local_ocr`：真实本地识别，依赖 `pytesseract + Tesseract`。

### 常见提示
- 若未安装 Tesseract 或路径错误，会提示：未找到 Tesseract 可执行文件或路径不存在。
- 若 provider 为 `mock_ocr`，UI 会明确显示这是模拟 OCR 结果。
## 自动化测试
```powershell
py -m unittest tests.smoke_test -v
py -m unittest tests.phase1_flow_test -v
py -m unittest tests.phase2_record_test -v
py -m unittest tests.phase3_prompt_output_test -v
py -m unittest tests.phase35_history_management_test -v
py -m unittest tests.phase4_ai_note_generation_test -v
py -m unittest tests.phase45_ai_contract_test -v
py -m unittest tests.phase5_workspace_view_test -v
py -m unittest tests.phase55_record_chat_test -v
py -m unittest tests.phase6_ai_settings_test -v
py -m unittest tests.phase7_shortcut_workflow_test -v
py -m unittest tests.phase8_ocr_image_multimodal_test -v
py -m unittest tests.phase8_local_ocr_integration_test -v
py -m unittest tests.phase9_note_lightweight_test -v
py -m unittest tests.phasep1_prompt_image_ux_test -v
py -m unittest tests.packaging_runtime_paths_test -v
py -W error::ResourceWarning -m unittest tests.smoke_test -v
```

## 存储策略
- SQLite：Project / Session / Record / Note / PromptTemplate / OutputProfile / app_settings / ai_provider_configs / ai_feature_routes / record_ocr_results
- 文件系统：截图文件与导出文件

截图路径约定：
- `data/projects/project_{project_id}/assets/session_{session_id}/session_{session_id}_shot_XXX.png`

OCR 结果：
- `record_ocr_results` 以 `record_id` 关联 image Record，持久化 `ocr_text / ocr_status / ocr_error / processed_at`

## 目录结构
```text
app/
  db/
  models/
  repositories/
  services/
    ai_providers/
  ui/
  utils/
tests/
assets/
exports/
docs/
```



## Windows 打包（Packaging P1）

### 打包前准备
```powershell
.venv\Scripts\activate
py -m pip install pyinstaller
```

图标文件路径（默认约定）：
- `assets/icons/videolearner.ico`

> 若你要替换图标，直接覆盖同名 `.ico` 文件即可。

### 使用 spec 打包（推荐 onedir）
```powershell
py -m PyInstaller --clean packaging/pyinstaller/VideoLearner.spec
```

### 输出目录说明
- `build/VideoLearner/`：PyInstaller 中间构建目录
- `dist/VideoLearner/`：可分发目录（onedir）
  - 主程序：`dist/VideoLearner/VideoLearner.exe`
  - prompts 资源：`dist/VideoLearner/app/prompts/`
  - 图标资源：`dist/VideoLearner/assets/icons/videolearner.ico`

### 打包后运行
```powershell
.\dist\VideoLearner\VideoLearner.exe
```

### 资源路径兼容机制
项目已统一通过 `app/utils/runtime_paths.py` 处理运行时路径：
- 源码模式：按仓库目录读取资源
- PyInstaller 模式：优先从 bundle 目录（`_MEIPASS`）读取资源
- 可写数据目录：
  - 源码模式：仓库根目录
  - 打包模式：`%LOCALAPPDATA%\VideoLearner`（可通过 `VIDEOLEARNER_HOME` 覆盖）

### OCR（Tesseract）外部依赖说明
- 本阶段不把 Tesseract 打进安装包。
- OCR 仍是可选增强能力：
  - `mock_ocr`：无需安装 Tesseract，可离线使用
  - `local_ocr`：需本机安装 Tesseract 并在 GUI 中配置路径
- 未安装 Tesseract 时，程序主流程可正常启动，OCR 会给出友好错误提示。

### 常见排查
1. 打包后 Prompt 读取异常：
   - 检查 `dist/VideoLearner/app/prompts/` 是否存在
   - 检查是否用的是 `packaging/pyinstaller/VideoLearner.spec`
2. 图标未生效：
   - 检查 `assets/icons/videolearner.ico` 是否存在且为有效 `.ico`
   - 重新执行 `--clean` 打包
3. 数据写入权限问题：
   - 设置环境变量 `VIDEOLEARNER_HOME` 指向可写目录

### Inno Setup 脚本雏形（可选）
已预留：
- `packaging/installer/VideoLearner.iss`

用于下一阶段正式安装包制作，当前为最小框架版本。


