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
- Phase 5.5：Record 智能对话（text/insight 优先，image 预留 stub）
- Phase 6：AI Provider 设置中心 + 生成体验增强（基础版）

## Phase 5 ~ 6 已实现
- StudyPage 升级为 Session 浏览区 / Record 时间线区 / 详情预览区
- Session 列表显示：标题、状态、开始时间、Record 数量、是否有 Note
- Record 时间线支持 image 缩略图、text/insight 摘要、北京时间与相对时间
- 详情区支持图片大图预览、文本全文预览、Session Note 概览
- Record 详情区接入 Record 级 AI 对话：开始/继续对话、历史消息展示、输入框发送
- 对话按 `record_id` 持久化到数据库，可再次打开同一 Record 继续追问
- image Record 本阶段提供明确占位回复（stub），为后续多模态问答预留接口
- NotePage 升级为分块阅读（Summary / Inspirations / Expansion / Guidance + 可选模块）
- 新增 AI Settings 页面：可设置默认 Provider、功能路由、Provider 参数（api_key/base_url/model/timeout）
- 新增最小功能路由：`session_note_provider`、`record_chat_provider`，未配置时回退 `default_provider`
- 新增 Provider 连接测试：mock 离线直通；真实 Provider 走最小请求并返回可读结果
- 配置持久化到 SQLite（`app_settings` / `ai_provider_configs` / `ai_feature_routes`），重启后可读取
- Note 生成与 Record Chat 成功提示中展示 provider/model

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
- Python 3.12+
- PySide6
- SQLite（标准库 sqlite3）
- Pillow（截图）
- requests（模型调用）

## 快速开始
```powershell
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m app.db.init_db

# 按需配置 AI Provider（开发推荐 mock）
$env:AI_PROVIDER="mock"
# $env:AI_PROVIDER="openai"
# $env:OPENAI_API_KEY="your-openai-key"
# $env:AI_PROVIDER="deepseek"
# $env:DEEPSEEK_API_KEY="your-deepseek-key"
# $env:AI_PROVIDER="glm"
# $env:GLM_API_KEY="your-glm-key"

python -m app.main
```


## 自动化测试
```powershell
python -m unittest tests.smoke_test -v
python -m unittest tests.phase1_flow_test -v
python -m unittest tests.phase2_record_test -v
python -m unittest tests.phase3_prompt_output_test -v
python -m unittest tests.phase35_history_management_test -v
python -m unittest tests.phase4_ai_note_generation_test -v
python -m unittest tests.phase45_ai_contract_test -v
python -m unittest tests.phase5_workspace_view_test -v
python -m unittest tests.phase55_record_chat_test -v
python -m unittest tests.phase6_ai_settings_test -v
python -W error::ResourceWarning -m unittest tests.smoke_test -v
```

## 存储策略
- SQLite：Project / Session / Record / Note / PromptTemplate / OutputProfile / app_settings / ai_provider_configs / ai_feature_routes
- 文件系统：截图文件与导出文件

截图路径约定：
- `data/projects/project_{project_id}/assets/session_{session_id}/session_{session_id}_shot_XXX.png`

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

