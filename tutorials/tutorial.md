# perilla 上手教程（从环境到上线）

面向 **Standalone** 仓库新手：覆盖安装、启动、租户与 RBAC、CSRF/XSS、Workflow 与 Agent、回归测试与常见错误。**所有模型与控制面调用经 FastAPI 网关**；请勿绕过网关直连推理引擎。

本教程帮助你完成：**环境安装 → 前后端启动 → 功能验证 → 安全配置 → 回归与上线前自检**。  
迷路时先看 **[README.md](README.md)**（阅读顺序与按 HTTP 状态码跳转）。

**相关文档**

| 文档 | 用途 |
|------|------|
| [README.md](README.md) | 教程目录导航、403/404/429 等问题索引 |
| [tutorial-quickstart.md](tutorial-quickstart.md) | 约 10 分钟极简上手 |
| [tutorial-index.md](tutorial-index.md) | 索引、命令、PowerShell 对照；**控制台模型与账号**见 **§1.1** 与第 **8.1～8.3** 节对照 |
| [tutorial-ops-checklist.md](tutorial-ops-checklist.md) | 发版前短清单 |
| [tutorial-incident-runbook.md](tutorial-incident-runbook.md) | 线上故障卡片 |
| [tutorial-security-baseline.md](tutorial-security-baseline.md) | 安全 MUST 与门禁 |
| [tutorial-glossary-zh-en.md](tutorial-glossary-zh-en.md) / [product](tutorial-glossary-product.md) / [engineering](tutorial-glossary-engineering.md) | 术语表 |

---

## 1. 先理解：这个项目是做什么的

**perilla** 是本地优先的 AI 平台，可概括为：

- **前端控制台**：可视化操作界面（Vue）
- **后端网关**：统一接入模型、工作流、审计、安全治理（FastAPI）
- **能力模块**：Agent、Tool、Skill、Workflow、Image、RAG 等

它不是“单一聊天应用”，而是“可治理的 AI 能力平台”。

当前仓库默认已包含以下生产化能力：

- 多租户隔离（入口强制、API Key–租户绑定、Workflow/会话/知识库/记忆/聊天/VLM/Agent 会话等数据面 **tenant_id** 过滤；MCP 与 Skills 等控制面按中间件租户解析）
- RBAC 鉴权
- API Key 与租户绑定
- 审计与请求追踪
- 限流与防滥用
- 生产护栏（高危配置可阻断启动）

---

## 2. 准备环境（新手必做）

### 2.1 必备软件

- Python `3.11+`
- Node.js `18+`
- Conda（推荐）
- Git

建议先验证：

```bash
python --version
node --version
conda --version
git --version
```

### 2.2 创建 Python 虚拟环境（推荐 Conda）

```bash
conda create -n ai-inference-platform python=3.11 -y
conda activate ai-inference-platform
```

如果你不使用 Conda，也可以用 `venv`，但项目默认流程更偏 Conda。

---

## 3. 获取代码并进入目录

```bash
cd "你的工作目录"
# Standalone 完整分发目录通常为 perilla（或你克隆的本仓库根目录）
cd perilla
```

确认关键目录存在：

- `backend/`
- `frontend/`
- `backend/scripts/`
- `backend/tests/`

---

## 4. 安装依赖（前后端）

### 4.1 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
cd ..
```

说明：

- 当前 `backend/requirements.txt` 会按平台引用子依赖（当前路径默认是 macOS 入口）
- 若安装很慢，建议配置镜像源

### 4.2 安装前端依赖

```bash
cd frontend
npm install
cd ..
```

---

## 5. 配置 `.env`（非常重要）

你可以在 `backend/.env`（或项目根 `.env`）配置运行参数。  
新手建议先从“开发安全模式”开始，再逐步切生产模式。

### 5.1 开发环境建议（便于调试）

```dotenv
DEBUG=true
RBAC_ENABLED=true
RBAC_ENFORCEMENT=true
TENANT_ENFORCEMENT_ENABLED=true
TENANT_API_KEY_BINDING_ENABLED=true
TENANT_API_KEY_TENANTS_JSON={"admin-key":["*"],"dev-key":["tenant-dev"]}
RBAC_ADMIN_API_KEYS=admin-key
RBAC_OPERATOR_API_KEYS=dev-key
SECURITY_GUARDRAILS_STRICT=true
```

### 5.2 生产环境建议（最小安全基线，建议直接复制）

```dotenv
DEBUG=false

RBAC_ENABLED=true
RBAC_ENFORCEMENT=true
RBAC_ADMIN_API_KEYS=admin-key-1
RBAC_OPERATOR_API_KEYS=op-key-1,op-key-2
RBAC_VIEWER_API_KEYS=view-key-1
RBAC_DEFAULT_ROLE=viewer

TENANT_ENFORCEMENT_ENABLED=true
TENANT_HEADER_NAME=X-Tenant-Id
TENANT_API_KEY_BINDING_ENABLED=true
TENANT_API_KEY_TENANTS_JSON={"admin-key-1":["*"],"op-key-1":["tenant-a"],"op-key-2":["tenant-b"]}
API_KEY_SCOPES_JSON={"admin-key-1":["admin","model:write","workflow:write","audit:read"]}

API_RATE_LIMIT_ENABLED=true
API_RATE_LIMIT_REQUESTS=120
API_RATE_LIMIT_WINDOW_SECONDS=60

AUDIT_LOG_ENABLED=true
AUDIT_LOG_PATH_PREFIXES=/api/v1/workflows,/api/system

CORS_ALLOWED_ORIGINS=https://console.example.com
FILE_READ_ALLOWED_ROOTS=/data,/models

TOOL_NET_HTTP_ENABLED=false
TOOL_NET_HTTP_ALLOWED_HOSTS=api.openai.com,*.internal.example.com
TOOL_NET_HTTP_ALLOW_PRIVATE_TARGETS=false
TOOL_NET_WEB_ENABLED=false

AGENT_ALLOW_DANGEROUS_SKILLS=false
AGENT_UPLOAD_MAX_CONCURRENCY=4

SECURITY_GUARDRAILS_STRICT=true
```

### 5.3 新手最易踩坑（必须看）

1. `DEBUG=false` 时，`CSRF_COOKIE_SECURE` 默认会变为 `true`。  
   如果你用 `http://127.0.0.1` 直接调写接口，需要手工回传 `Cookie: csrf_token=...` 与 `X-CSRF-Token`。
2. `/api/system/*` 现在要求：
   - admin API Key
   - 显式 `X-Tenant-Id`
3. 写接口（POST/PUT/PATCH/DELETE）必须通过 CSRF 校验，否则 403。

---

## 6. 启动项目（两种方式）

### 6.1 一键启动（推荐新手）

项目根目录：

- macOS/Linux：`./run-all.sh`
- Windows：`run-all.bat`

### 6.2 手动启动（便于定位问题）

后端：

```bash
cd backend
python main.py
```

前端（新终端）：

```bash
cd frontend
npm run dev
```

默认后端端口一般是 `8000`。

---

## 7. 启动后第一轮自检（新手必须做）

### 7.1 API 探针检查

后端启动后检查：

- `GET /api/health`
- `GET /api/health/live`
- `GET /api/health/ready`

只要其中任何一个持续失败，就不要继续做业务验证，先看日志。

### 7.2 看日志重点

重点看是否出现：

- 数据库初始化失败
- 依赖导入失败
- 安全护栏阻断：`Unsafe production security configuration. Refuse to start.`

---

## 8. 前端界面快速认识

首次登录后，建议按这个顺序体验：

1. **General / Backend Settings**：看系统配置是否生效（界面语言、主题、数据目录，以及 **Backend** 中的 **API Key / 租户** 等；详见 **§8.2**）  
2. **Workflow**：创建一个最小流程并执行  
3. **Models / Images**：验证模型侧能力（磁盘本地模型 **§8.1**、云端注册 **§8.3**，按你的环境）  
4. **Audit / Logs（若开放）**：确认审计与追踪信息

### 8.1 配置本地化大模型（方法与步骤）

推理仍全部由 **FastAPI 网关**调度；前端只做目录、清单与注册信息的维护。常见有两种用法：**磁盘上的本机模型（`backend=local`）**，以及 **本机运行的 Ollama / LM Studio 等 OpenAI 兼容服务**（网关注册后走对应运行时）。

#### A. 先设置模型数据目录（全局）

1. 打开 **Settings（设置）→ General（常规）**。  
2. 找到 **数据目录 / Data directory**（对应系统配置里的 `dataDirectory`），设为存放模型的根路径，默认一般为 `~/.local-ai/models/`。  
3. **保存**。后端扫描器会优先使用该路径（未配置时回落到环境变量/默认 `local_model_directory`）。

#### B. 磁盘本机模型：`model.json` + 权重文件

适用于 GGUF、部分 Torch/其他格式的本地权重；注册后模型在列表中的 **`backend` 为 `local`**，才可使用下文「模型配置页」。

**1）目录布局（与后端 `LocalScanner` 一致）**

在数据目录下为每个模型准备**独立子目录**，目录内必须有 **`model.json`**。可选分层便于分类：

- `…/llm/<模型目录>/model.json`
- `…/vlm/<模型目录>/model.json`
- `…/embedding/`、`…/asr/`、`…/perception/`、`…/image_generation/` 等同理  

也可把模型目录直接放在数据目录根下（平铺），只要该文件夹内含 `model.json` 即可。

**2）`model.json` 要点**

至少需要：`model_id`、`name`、`model_type`（如 `llm` / `vlm`）、`runtime`（如对话常用 `llama.cpp`）、以及 **`path`**（相对于该模型目录的权重相对路径，指向实际文件）。其余字段（能力、量化说明、`metadata` 等）可按模型类型补充；不熟悉时可之后在 UI 里改。

**3）在前端注册与扫描**

1. 打开 **Models（模型库）**（路由一般为 `/models`，可按左侧分类进入 LLM/VLM 等）。  
2. 点击标题栏区域的 **扫描 / 刷新** 按钮（调用 `POST /api/models/scan`），等待扫描结束。  
3. 在列表上用 **「仅本地」** 筛选可只看 `backend=local` 的条目（界面上的「本地」指磁盘注册模型；见下文说明）。  
4. 进入某一模型的 **配置 / Configure**，跳转到 **`/models/<id>/config`**。  
5. 仅 **`backend === local`** 时会出现 **本地模型配置编辑器**：在 **基础信息 / 能力 / 运行时 /（VLM 等）** 各页填写或修正路径、运行时、`model.json` 高级 JSON；保存会写入网关（`PUT /api/models/<id>/manifest`）。  
6. **浏览目录**选权重时，服务端仅在允许的根路径内列出文件；若被拒绝，请在后端 `.env` 中配置 **`FILE_READ_ALLOWED_ROOTS`**，包含你的模型盘路径（生产勿设为 `/`）。

#### C. 本机 Ollama / LM Studio（不在磁盘放 `model.json`）

这类服务在本机端口提供 HTTP API，网关通过扫描或手动注册接入；列表里 **`backend` 多为 `ollama` / `lmstudio` 等**，与磁盘 `local` 不同。

**步骤简述：**

1. 在本机启动 Ollama（默认 `http://127.0.0.1:11434`）或 LM Studio 本地服务器（常见 `http://127.0.0.1:1234`）。  
2. **Models** 页点击 **添加云端模型 / Cloud model**：提供商选 **Ollama** 或 **LM Studio**，**Base URL** 填上述地址（可按需改端口），填写提供商侧的 **模型 ID**、显示名称与（若需要）API Key。  
3. 保存后列表会出现对应条目；亦可依赖网关启动时的自动扫描（若服务已就绪）。  

**说明：** 模型库顶部的「本地 / 云端」筛选里，**Ollama、LM Studio 会被归为「云端」类后端**（实现上是连本机 HTTP），与 **磁盘 `local` 模型**区分；聊天时在头部模型下拉框中选择已注册的模型即可。

#### D. 验证

1. **Models** 列表中能看到目标模型且无报错。  
2. 打开 **Chat**，在模型选择器中选该模型并发一条测试消息。  
3. 若加载失败，结合前端提示与后端日志排查（路径错误、显存不足、运行时未安装等）。

### 8.2 账号与安全相关设置（方法与步骤）

Web 控制台是 **本地优先的控制台**：没有独立的「注册 / 登录密码」流程；与网关交互身份主要由浏览器内保存的 **API Key**、**租户 ID** 以及界面偏好构成。以下路径均以侧边栏 **Settings（设置）** 为入口，默认打开 **`/settings/general`**。

#### A. 常规偏好（Settings → General）

路由：**`/settings/general`**。

| 能力 | 说明 |
|------|------|
| **离线模式** | 切换后会影响前端对外部依赖的假设（与业务开关一致时保存）。 |
| **界面语言** | 中文 / English；写入 `localStorage`（`platform-language`），并与发往网关的 **`Accept-Language`** 对齐，便于后端错误信息国际化。 |
| **界面主题** | 跟随系统 / 浅色 / 深色；写入 `localStorage`（`platform-theme`）并作用于文档根节点 class。 |
| **数据目录** | 见 **§8.1**；保存至系统配置 `dataDirectory`。 |
| **默认推理相关** | 如默认模型加载器、上下文长度、GPU 层数等（与 **Backend** 页部分项同源，以界面为准）；修改后需点击 **保存** 写入网关侧用户/系统设置。 |

**操作步骤：** 在 General 页调整选项 → 点击右上角 **保存**（部分开关可能自动保存，以界面提示为准）。

#### B. 安全上下文：API Key 与租户（Settings → Backend）

路由：**`/settings/backend`**。向下滚动到 **Security Context** 区块。

| 字段 | 作用 |
|------|------|
| **Admin API Key** | 对应 HTTP 头 **`X-Api-Key`**，用于受 RBAC/租户策略保护的网关接口；保存后存放在浏览器 **`localStorage`** 键 **`ai_platform_api_key`**（界面另有说明）。 |
| **Tenant ID** | 对应 **`X-Tenant-Id`**，须与后端 **`TENANT_API_KEY_TENANTS_JSON`** 等配置一致；默认常用 `default`，保存键为 **`ai_platform_tenant_id`**。 |

**操作步骤：**

1. 打开 **Settings → Backend**（侧栏选 **Backend / 后端**）。  
2. 在 **Security Context** 中填写或粘贴 **API Key**、**Tenant ID**（可用显示/隐藏切换查看 Key）。  
3. 点击 **Save Security Context** 写入浏览器存储；之后 **`apiFetch` 发出的请求会自动带上上述请求头**（与教程 **§9**、**§10** 中的 curl 示例一致）。  
4. 需要重新从存储读取时点击 **Reload**；需在本书签页移除身份时点击 **Clear Security Context**（会清空 Key 与租户并恢复输入框展示）。  

**注意：** Key 与租户仅保存在本机浏览器，**不会**随「General/Backend 保存到服务端配置」而上传到服务器；替换浏览器或清除站点数据后需重新填写。

#### C. 其他设置子页（按需）

同一 **Settings** 侧栏还可进入：`/settings/backup`、`/settings/model-backup`、`/settings/runtime`、`/settings/object-detection`、`/settings/image-generation`、`/settings/asr`、`/settings/mcp` 等，用于数据库/模型备份、运行时、检测与语音等专项配置，与「账号身份」无关时不在此展开。

#### D. 与审计头字段的关系（可选了解）

网关请求还会自动携带 **`X-User-Id`**（默认来自 `localStorage` 键 **`ai_platform_user_id`**，缺省为 `default`）等；当前设置页 **未** 提供独立「用户账号」表单，一般由会话或其它流程写入。若仅用控制台完成配置，重点关注 **§8.2 B** 即可。

### 8.3 配置云端大模型（方法与步骤）

云端模型指通过 **HTTP API**（OpenAI 兼容或厂商原生适配）由网关转发的推理来源；与 **§8.1** 磁盘 `local` 模型不同，权重不在本机目录，而在提供商侧。控制台通过 **「添加云端模型」** 写入注册表（等价网关 **`POST /api/models`**）。

#### A. 前置条件

1. **管理员 API Key**：`POST /api/models` 要求请求携带 **`X-Api-Key`** 且 RBAC 映射为 **管理员（admin）** 角色；否则会 **401/403**。请在 **§8.2** 中把浏览器 **Security Context** 配置为具有管理员权限的 Key。  
2. **CSRF**：该接口为 **POST**，浏览器需已通过同源 **`GET`**（如健康检查）拿到 **`csrf_token` Cookie**，并由前端自动附带 **`X-CSRF-Token`**（项目 `apiFetch` 已处理）；脚本调用见 **§13** / **§20**。  
3. **隐私**：云端 Key 会写入网关侧模型元数据用于推理鉴权；仅在合规前提下配置外部服务商密钥。

#### B. 在前端注册（推荐）

1. 打开 **Models（模型库）**（`/models`）。  
2. 点击标题栏 **添加云端模型 / Cloud model**，打开向导对话框。  
3. **步骤 1 — 选择提供商**：  
   - **OpenAI**、**Gemini**（Google）、**DeepSeek**、**Kimi**（Moonshot）、**LM Studio**、**Ollama**、**自定义（Custom）** 等。  
   - 切换提供商时，**Base URL** 与 **runtime** 会按预设填充（可自行修改）。常见预设包括：`https://api.openai.com/v1`、`https://generativelanguage.googleapis.com/v1beta/openai`、`https://api.deepseek.com`、`https://api.moonshot.cn/v1`、`http://localhost:1234/v1`、`http://localhost:11434` 等（以界面为准）。  
4. **步骤 2 — 模型身份**：  
   - **提供商模型 ID**（`provider_model_id`）：**必填**，即上游接口里的模型名（如 `gpt-4o`、`deepseek-chat`）。  
   - **显示名称**（`name`）：可选，用于列表展示。  
   - **系统 ID**（`id`）：可选；不填时由代码按 `provider:provider_model_id` 等规则生成，须全局唯一。  
5. **步骤 3 — 连接**：  
   - **Base URL**：OpenAI 兼容根地址（无尾斜杠问题以你环境为准，按服务商文档填写）。  
   - **API Key**：对 **OpenAI / Gemini / DeepSeek / Kimi / Custom** 等一般为 **必填**；**LM Studio、Ollama** 在界面上标为 **可选**（本机无鉴权时常为空）。  
   - **描述**：可选备注。  
6. 点击 **注册**。成功后对话框关闭，列表刷新即可看到新条目。  

**界面筛选：** 使用模型库顶部的 **「仅云端」**，可快速只看此类条目（含 **§8.1 C** 所述的本机 Ollama/LM Studio HTTP 通道，它们在后端也归为云端类 **backend**）。

#### C. 注册后微调（侧栏配置）

在列表中展开某云端模型，点击 **Configure**，右侧打开 **Model Config Sidebar**，可调整展示名、`provider_model_id`、**上下文长度**、温度、`top_p`、**Base URL**、**API Key**（写入模型元数据）等，保存调用 **`PATCH /api/models/{model_id}`**（同样需要管理员权限；前端已封装）。

#### D. 与扫描的关系

网关启动或你在模型库点击 **扫描** 时，会尝试从 **Ollama / LM Studio** 等端点拉取模型列表并 **upsert** 注册表，可能与手动添加重复或互补。**自定义厂商 Key** 通常只能用手动「添加云端模型」完成。

#### E. 验证

1. **Models** 列表中模型状态正常；必要时用 **§8.3 C** 侧栏确认 Base URL 与 Key。  
2. 打开 **Chat**，在模型下拉框中选择该模型并发测试消息。  
3. 若 **403**，核对 **§8.3 A** 管理员 Key；若连接超时或鉴权失败，核对 Base URL、模型 ID 与 Key，并查看后端日志。

---

## 9. 第一个 Workflow（手把手）

### 9.1 准备请求头

你至少需要：

- `X-Api-Key`
- `X-Tenant-Id`

例如：

- `X-Api-Key: dev-key`
- `X-Tenant-Id: tenant-dev`

### 9.2 创建流程

调用：

- `POST /api/v1/workflows`

要点：

- `namespace` 应与 `X-Tenant-Id` 一致（服务端会强制对齐）
- 名称在同 namespace 内需唯一

### 9.3 创建版本并执行

- 创建版本：`POST /api/v1/workflows/{workflow_id}/versions`
- 发起执行：`POST /api/v1/workflows/{workflow_id}/executions`
- 查执行状态：`GET /api/v1/workflows/{workflow_id}/executions/{execution_id}/status`
- 调试视图：`GET /api/v1/workflows/{workflow_id}/executions/{execution_id}/debug`

### 9.4 新手最常见误区

- 403：API Key 权限不足
- 404：租户不匹配（这是安全策略，不一定是数据不存在）
- 429：触发限流

### 9.5 自治编排新增能力（本版本）

在已有租户/RBAC/CSRF 基线之外，本版本工作流与 Agent 路径新增四项关键能力：

1. **插件权限强校验**：插件执行前按声明权限判定，权限不足直接拒绝。  
2. **Agent run 幂等**：`POST /api/v1/agents/{agent_id}/run` 支持 `Idempotency-Key`，避免重试导致重复执行。  
3. **持久化执行队列**：工作流执行队列持久化到数据库，支持 lease 与重启恢复。  
4. **HITL 审批闸门**：存在 `approval` 节点时，执行可进入 `PAUSED` 等待人工批准。

### 9.6 前端交互与性能增强（本版本）

为提升大规模使用场景下的体验，前端新增如下能力：

1. **Workflow 编辑器选择器搜索**：模型/Agent/工具选择支持关键字过滤。  
2. **知识库大列表分页**：文档数 > 50 时自动分页，避免一次性渲染过多行。  
3. **Workflow 大图渲染优化**：节点数 > 50 时启用可视区域渲染优化。  
4. **错误提示可诊断**：模型调用失败时优先显示具体可排查原因（如 OOM、权重损坏、超时等）。

---

## 10. 多租户与权限（必须理解）

### 10.1 三层安全关系

1. **RBAC 角色**：admin/operator/viewer  
2. **API Key-租户绑定**：一个 key 可以访问哪些 tenant  
3. **资源租户隔离**：Workflow、会话、知识库、长短期记忆、治理审计等存储/查询层 **tenant-aware**（具体模块以代码为准）

### 10.2 为什么会出现“看得见创建，看不见查询”

通常是请求头变化导致：

- 创建时 `X-Tenant-Id=tenant-a`
- 查询时 `X-Tenant-Id=tenant-b`

系统会按策略返回 `404`。

### 10.3 快速排查顺序

1. 看请求头 `X-Api-Key` / `X-Tenant-Id`
2. 看 `TENANT_API_KEY_TENANTS_JSON` 是否绑定
3. 看 resource namespace 是否一致

### 10.4 租户强制路径（须显式 `X-Tenant-Id`）

当 **`TENANT_ENFORCEMENT_ENABLED`** 与 **`TENANT_API_KEY_BINDING_ENABLED`** 开启时，命中下列 **URL 前缀**之一即视为受保护路径：请求必须携带 **`TENANT_HEADER_NAME`**（默认 `X-Tenant-Id`），否则可能返回 **400**（如 `tenant id required for protected path`）。**单一事实来源**为后端：

`backend/middleware/tenant_paths.py` → `is_tenant_enforcement_protected_path`

当前前缀包括：`/api/v1/workflows`、`/api/v1/audit`、`/api/system`、`/v1/chat`、`/api/sessions`、`/api/memory`、`/api/knowledge-bases`、`/api/agent-sessions`、`/v1/vlm`（若升级版本后行为变化，以该文件为准）。

### 10.5 租户解析：`resolve_api_tenant_id` 与 `get_effective_tenant_id`

部分路由使用 **`resolve_api_tenant_id`**：仅采用中间件写入的 `request.state.tenant_id`（及默认租户），**不**用请求头覆盖 state，避免头注入绕过。  
另有一些场景使用 **`get_effective_tenant_id`**：在 state 未设置时可回落读取租户头，再回落默认租户（见 `backend/core/utils/tenant_request.py`）。集成第三方客户端时，不要假设「任意路径都可仅靠改头换租户」：须与 Key 绑定及中间件行为一致。

---

## 11. 系统配置接口怎么安全使用

关键接口：

- `POST /api/system/config`
- `POST /api/system/engine/reload`
- `POST /api/system/feature-flags`
- `POST /api/system/kernel/*`

注意：

- 这些写接口已要求管理员权限
- 如果你是 operator/viewer，请求会被拒绝（403）
- **凡命中租户强制前缀**（见 **§10.4**）须显式带 `X-Tenant-Id`，不仅是 `/api/system/*`；未携带可能返回 400

---

## 12. 审计、追踪、限流（可观测性）

### 12.1 请求追踪

每次请求应看到：

- `X-Request-Id`
- `X-Trace-Id`
- `X-Response-Time-Ms`

网关已对 `request_id` 做净化，避免 header 污染。

### 12.2 审计日志

审计日志可记录：

- 租户、用户、角色
- 方法、路径、状态码
- request_id / trace_id

并支持按租户过滤查询。

### 12.3 限流

核心配置：

- `API_RATE_LIMIT_ENABLED`
- `API_RATE_LIMIT_REQUESTS`
- `API_RATE_LIMIT_WINDOW_SECONDS`

限流返回已去敏，不泄露 API Key。

---

## 13. Web 安全增强（本次重点）

这一节是新手最容易忽略、但上线最容易出事故的部分。你可以直接把它理解成：

- **XSS**：防止页面渲染恶意脚本
- **CSRF**：防止“你已登录时被别的网站偷偷代你发写请求”

### 13.1 前端 XSS 防护已做什么

本项目已完成以下防护链：

1. `frontend/src/utils/markdown.ts` 中 `markdown-it` 已设置 `html: false`  
   - 用户输入的原生 HTML（例如 `<script>...</script>`）不会被当成可执行 HTML 渲染
2. markdown 渲染结果统一经过 `sanitizeHtml(...)` 净化  
   - 由 `frontend/src/utils/security.ts`（DOMPurify）执行白名单过滤
3. Mermaid SVG 渲染也经过净化，且 `securityLevel: 'strict'`  
   - 防止图形渲染链路被注入恶意节点/属性

### 13.2 后端 CSRF 防护已做什么

后端新增了双提交 Cookie 机制（double-submit cookie）：

- 中间件：`backend/middleware/csrf_protection.py`
- 关键行为：
  - `GET/HEAD/OPTIONS/TRACE` 等安全方法会下发 `csrf_token` Cookie 与 `X-CSRF-Token` 响应头
  - `POST/PUT/PATCH/DELETE` 必须提供 `X-CSRF-Token`，且与 Cookie 中 token 一致
  - 不一致或缺失返回 `403`

### 13.3 配置项（后端）

`backend/config/settings.py` 已支持：

- `CSRF_ENABLED`
- `CSRF_HEADER_NAME`（默认 `X-CSRF-Token`）
- `CSRF_COOKIE_NAME`（默认 `csrf_token`）
- `CSRF_COOKIE_PATH`
- `CSRF_COOKIE_SAMESITE`
- `CSRF_COOKIE_SECURE`
- `CSRF_COOKIE_MAX_AGE_SECONDS`

### 13.4 新手常见误区

- 误区 1：只在前端加了 token，后端没校验  
  - 结果：形同虚设
- 误区 2：跨域部署仍用 `CORS_ALLOWED_ORIGINS=*`  
  - 结果：Cookie/凭证策略混乱，浏览器行为不可控
- 误区 3：脚本调用写接口不带 CSRF header  
  - 结果：稳定 403

---

## 14. 生产安全护栏（必读）

### 14.1 自动收敛

当 `DEBUG=false` 时，系统会自动收敛关键开关：

- `RBAC_ENABLED=true`
- `RBAC_ENFORCEMENT=true`
- `TENANT_ENFORCEMENT_ENABLED=true`
- `TENANT_API_KEY_BINDING_ENABLED=true`

### 14.2 启动阻断（Fail-Fast）

命中以下风险会拒绝启动：

- `FILE_READ_ALLOWED_ROOTS="/"`  
- `CORS_ALLOWED_ORIGINS=""`  
- `TOOL_NET_HTTP_ENABLED=true` 且 `TOOL_NET_HTTP_ALLOWED_HOSTS=""`

### 14.3 严格模式开关

- `SECURITY_GUARDRAILS_STRICT=true`：违规直接阻断（默认推荐）
- `SECURITY_GUARDRAILS_STRICT=false`：仅告警继续（仅抢修临时使用）

---

## 15. 测试与回归（上线前必须跑）

你现在有两条回归主线（不要混淆）：

1. **tenant 安全回归**（租户隔离为主）
2. **security 安全回归**（RBAC/Audit/Trace/CSRF/XSS）

### 15.1 tenant 安全回归（后端脚本）

在项目根目录执行：

```bash
backend/scripts/test_tenant_security_regression.sh
```

预期：

- 退出码 `0`
- 输出包含 `regression suite passed`
- 生成摘要（默认）：`backend/test-reports/tenant-security-summary.md`

如需报告文件：

```bash
JUNIT_XML_PATH=test-reports/tenant-security-regression.xml backend/scripts/test_tenant_security_regression.sh
```

### 15.2 security 安全回归（推荐新脚本）

在项目根目录执行：

```bash
python backend/scripts/security_regression.py \
  --base http://127.0.0.1:8000 \
  --api-key "你的-admin-key" \
  --tenant-id default
```

常用参数：

- `--json-output /tmp/security-regression.json`：导出结构化结果
- `--junit-output /tmp/security-regression.xml`：导出 JUnit（CI 用）
- `--suite-name security_regression_staging`：区分环境
- `--quiet`：只输出 summary
- `--fail-fast`：首个失败立即退出

### 15.3 security 安全回归（acceptance 聚合脚本，兼容保留）

在项目根目录执行：

```bash
scripts/acceptance/run_security_regression.sh
```

该脚本会串行执行：

- `scripts/acceptance/run_batch1_rbac.sh`
- `scripts/acceptance/run_batch2_audit.sh`
- `scripts/acceptance/run_batch3_trace.sh`
- `scripts/acceptance/run_batch5_web_security.sh`

并生成摘要：

- `test-reports/security-regression-summary.md`

### 15.4 慢批次阈值告警（本地）

可选设置阈值（秒）：

```bash
SECURITY_SLOW_THRESHOLD_SECONDS=20 scripts/acceptance/run_security_regression.sh
TENANT_SECURITY_SLOW_THRESHOLD_SECONDS=20 backend/scripts/test_tenant_security_regression.sh
```

当超过阈值，摘要会出现 `⚠️` 和 Slow Batches 区块。

### 15.5 Execution Kernel 集成测试（可选 / 重型）

用于本地验证 **Plan 编译**、**节点执行器注册**、`ExecutionKernelAdapter` 初始化等；默认脚本**只跑轻量项**（秒级结束），避免重型 Scheduler + SQLite 组合在你机器上长时间阻塞或触发锁竞争。

**快速入口（日常推荐）：**

```bash
PYTHONPATH=backend python3 backend/scripts/test_execution_kernel_integration.py
```

预期：约 **3 项**通过，退出码 `0`。

**重型入口（额外跑 Scheduler + 独立临时库）：**

```bash
PYTHONPATH=backend python3 backend/scripts/test_execution_kernel_integration_heavy.py
```

与在主脚本前设置 `EXEC_KERNEL_RUN_HEAVY_INTEGRATION=1` 等价。

**排障：卡住、无输出或迟迟不结束**

要知道：`Scheduler.start_instance()` 会**一直等到整张图跑完**才返回；若调度或数据库侧阻塞，看起来像「挂住」。

可配合：

- `EXEC_KERNEL_INTEGRATION_DIAG=1`：约每 **5 秒**打印一次快照（图实例状态、各节点 pending/running 分布、调度器在跑任务数等）。
- `EXEC_KERNEL_START_INSTANCE_TIMEOUT_SEC`：限制 `start_instance` 最长等待秒数（默认 **`90`**）；超时后会尝试取消实例并抛出带说明的错误，而不是无限等下去。

示例（重型 + 诊断 + 超时）：

```bash
EXEC_KERNEL_RUN_HEAVY_INTEGRATION=1 \
EXEC_KERNEL_INTEGRATION_DIAG=1 \
EXEC_KERNEL_START_INSTANCE_TIMEOUT_SEC=90 \
PYTHONPATH=backend python3 backend/scripts/test_execution_kernel_integration.py
```

此外，Execution Kernel 还有独立回归脚本 `backend/scripts/test_execution_kernel_regression.py`；若启用了敏感路由鉴权，可按脚本内说明配置 `RBAC_TEST_ADMIN_API_KEY`、`RBAC_TEST_TENANT_ID` 等，避免系统 API 冒烟用例被跳过。

---

## 16. CI 流水线说明（你当前已接好）

工作流：

- `.github/workflows/tenant-security-regression.yml`
- `.github/workflows/security-regression.yml`

能力：

- PR / push（含路径过滤 + docs 变更忽略）
- 并发去重（新任务取消旧任务）
- `workflow_dispatch` 手动触发
- 结果双输出：Step Summary + Artifact
- 手动触发可设置 `slow_threshold_seconds`
- 输入校验：必须是正整数（非法输入会 fail-fast 并在 Summary 给出示例）

### 16.1 两条工作流如何分工

- `tenant-security-regression.yml`  
  - 聚焦：租户隔离
  - 主入口脚本：`backend/scripts/test_tenant_security_regression.sh`
- `security-regression.yml`  
  - 聚焦：RBAC/Audit/Trace/CSRF/XSS
  - 主入口脚本：`scripts/acceptance/run_security_regression.sh`

---

## 16.2 Agent 并行编排与记忆（新能力）

当你使用 `plan_based` 智能体时，可以通过 agent 配置开启图执行并行与记忆增强：

- `execution_strategy=parallel_kernel`：启用 Agent Graph + Execution Kernel 并行调度
- `max_parallel_nodes=<N>`：限制单次执行并发节点数（建议先 2~4）
- `execution_strategy=serial`：强制串行 **PlanBasedExecutor**（灰度、排障或与 Kernel 解耦）
- 未设置 `execution_strategy` 时：按 `use_execution_kernel`（Agent 级）与全局 `USE_EXECUTION_KERNEL` 推导（与运行时 `_resolve_execution_strategy` 一致）
- Kernel 执行失败时：运行时会**自动降级**为串行 `PlanBasedExecutor`，单次对话仍尽量完成（错误写入日志与指标）

**HTTP API（创建/更新 Agent）** 已支持同名字段（管理员接口 `PUT/POST /api/agents` 的 JSON body）：

- `execution_strategy`：`"serial"` | `"parallel_kernel"` | `null`（null 表示交给推导逻辑）
- `max_parallel_nodes`：整数或 `null`（null 表示使用内核默认并发）

也可仅在 `model_params` 里写 `execution_strategy` / `max_parallel_nodes`；**运行时优先读顶字段 `AgentDefinition.execution_strategy`，为空时才读 `model_params`**（见 `v2/runtime.py`）。若在**顶字段与 `model_params` 两处同时写了不同取值**，创建/更新接口会返回 **400**（避免 silent shadow）。

事件驱动编排与调试：

- Kernel 执行会写入事件流（可用 `/api/events/instance/{instance_id}` 回放）
- 已支持按会话聚合查询：`/api/events/agent-session/{session_id}`

记忆增强行为：

- 执行前自动注入长期记忆（受 memory 配置开关控制）
- 执行后自动提取并持久化记忆（失败不阻断主链路）

灰度建议：

1. 先给少量 agent 开 `parallel_kernel`
2. 观察事件流中的失败链路与回退次数
3. 再逐步提升 `max_parallel_nodes`

---

## 17. 常见错误与解决方案（新手高频）

### 17.1 启动失败：Unsafe production security configuration

处理：

1. `FILE_READ_ALLOWED_ROOTS` 不要是 `/`
2. `CORS_ALLOWED_ORIGINS` 不要为空
3. 若开启 HTTP 工具，配置 `TOOL_NET_HTTP_ALLOWED_HOSTS`

### 17.2 403（权限问题）

处理：

1. 检查 API Key 是否存在
2. 检查 RBAC 角色映射
3. 检查是否调用了 admin-only 接口

### 17.3 404（跨租户）

处理：

1. 检查 `X-Tenant-Id`
2. 检查 API Key 的 tenant 绑定
3. 检查 workflow namespace

### 17.4 429（限流）

处理：

1. 提高限流阈值（谨慎）
2. 降低轮询频率
3. 合并批量请求

### 17.5 全量 pytest 因三方依赖失败

可能出现 `numpy/sklearn/transformers` 二进制兼容问题。  
优先执行项目稳定回归脚本，不要被无关依赖阻断主线验证。

### 17.6 写接口 403：CSRF token validation failed

处理顺序：

1. 先请求一次 `GET /api/health`，确保拿到 `csrf_token` Cookie
2. 写请求带 `X-CSRF-Token` 且值等于 Cookie 中 token
3. 检查反向代理是否剥离了 `X-CSRF-Token` 头

### 17.7 前端渲染异常怀疑 XSS 清洗导致

处理顺序：

1. 检查是否依赖了原生 HTML 渲染（现在 `html: false`）
2. 检查内容是否被 DOMPurify 合法过滤（脚本/危险属性会被去掉）
3. 对需要保留的展示能力，走白名单扩展，不要临时禁用净化

### 17.8 返回 400：`tenant id required for protected path`

适用于所有 **租户强制路径**（见 **§10.4**，含 `/api/system/*`、`/v1/chat`、`/api/sessions` 等），不单是 system 接口。

处理顺序：

1. 确认请求头里显式带了 `X-Tenant-Id`（名称与 `TENANT_HEADER_NAME` 一致）
2. 确认 key 与 tenant 绑定关系允许该租户
3. 确认前端 Security Context / `localStorage` 中租户已保存并与请求一致

### 17.9 Agent 上传报错 413 / 429

- `413`：文件超单文件/总量限制（默认单文件 20MB、总量 100MB）
- `429`：并发上传超过 `AGENT_UPLOAD_MAX_CONCURRENCY`

处理：

1. 分片或压缩上传文件
2. 降低前端并发上传数量
3. 按需调整服务端阈值（谨慎）

### 17.10 409（Idempotency-Key 冲突）

典型场景：

- 同一个 `Idempotency-Key` 被复用到**不同请求体**；
- 前一次同 key 请求仍处于 processing，中途再次提交。

处理顺序：

1. 确认同一业务动作是否稳定复用同一个 key；
2. 若请求体变化，必须更换新的 `Idempotency-Key`；
3. 若是重试，保持 key 与请求体一致，并等待前一次完成后再查询结果。

### 17.11 Workflow 状态停在 `PAUSED`

典型场景：

- 工作流版本中包含 `approval` 节点；
- 审批任务尚未通过，执行被门控暂停。

处理顺序：

1. 查询执行对应审批任务列表；
2. 由有权限的操作者调用 approve/reject；
3. 确认通过后执行转回 `PENDING`/继续运行，或拒绝后转 `FAILED`。

### 17.12 知识库文档很多时列表卡顿

说明：

- 当前版本在文档数超过 50 时会自动分页（每页 20）。

排查顺序：

1. 确认文档总数是否超过分页阈值；
2. 使用分页按钮切换，避免一次加载过多行；
3. 若仍卡顿，检查浏览器扩展或 DevTools 性能开销。

### 17.13 Workflow 节点很多时画布拖拽卡顿

说明：

- 当前版本在节点数超过 50 时会启用可视区域渲染优化，并保留网格吸附与拖拽后自动对齐。

排查顺序：

1. 确认节点数量是否达到大图阈值；
2. 优先缩放到局部区域编辑，减少同时可视节点；
3. 检查是否有大量浏览器标签页占用 GPU/内存。

### 17.14 模型调用失败但提示不清晰

当前前端会将常见错误映射为可诊断文案，重点包括：

- 显存不足（OOM）
- 模型权重文件损坏
- 请求超时
- 网络/连接异常
- 权限不足或鉴权失效

若仍无法定位，请结合后端日志关键字（OOM/timeout/connection/permission）进一步确认。

---

## 18. 新手上线前最终检查（建议打印执行）

1. 后端/前端可启动  
2. 健康探针全部通过  
3. 一个 workflow 从创建到执行全流程通过  
4. 错租户访问被拒绝（404/403）  
5. system 写接口非 admin 被拒绝  
6. 跑完 tenant + security 两条回归  
7. CI 绿灯 + Step Summary 可读 + artifact 可下载  
8. 抽样验证 CSRF（写接口）与 XSS（消息渲染）  
9. 生产 `.env` 安全项复核完成

---

## 19. 你下一步该读什么

完成本教程后，建议继续读：

- `tutorial-ops-checklist.md`：发版前超短清单  
- `tutorial-incident-runbook.md`：线上故障 3 分钟卡片  
- `tutorial-security-baseline.md`：安全与审计规范（制度层）

如果你是团队负责人，建议把 `tutorial-index.md` 设为内部入口首页。

---

## 20. 附录：可直接复制执行的 API 示例（curl）

下面示例默认：

- 后端地址：`http://127.0.0.1:8000`
- 管理员 key：`admin-key`
- 操作员 key：`dev-key`
- 租户：`tenant-dev`

你可以先设置环境变量，避免重复输入：

```bash
export BASE_URL="http://127.0.0.1:8000"
export ADMIN_KEY="admin-key"
export OP_KEY="dev-key"
export TENANT_ID="tenant-dev"
```

### 20.1 健康探针

```bash
curl -s "${BASE_URL}/api/health" | jq .
curl -s "${BASE_URL}/api/health/live" | jq .
curl -s "${BASE_URL}/api/health/ready" | jq .
```

预期：返回 `healthy/alive/ready` 相关字段，HTTP 状态码 `200`。

### 20.2 读取系统配置（只读接口）

```bash
curl -s "${BASE_URL}/api/system/config" | jq .
```

### 20.3 获取 CSRF Token（写请求前）

```bash
# 保存 cookie，并拿到响应头中的 X-CSRF-Token
curl -i -s -c /tmp/ov_cookie.txt "${BASE_URL}/api/health" | tee /tmp/ov_health_headers.txt
export CSRF_TOKEN="$(rg "X-CSRF-Token:" /tmp/ov_health_headers.txt -i | awk '{print $2}' | tr -d '\r')"
echo "${CSRF_TOKEN}"
```

如果你的环境拿不到响应头 token，也可以从 cookie 中提取后回填 header。

### 20.4 更新系统配置（管理员写接口，含 CSRF）

```bash
curl -s -X POST "${BASE_URL}/api/system/config" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: ${ADMIN_KEY}" \
  -H "X-Tenant-Id: ${TENANT_ID}" \
  -H "X-CSRF-Token: ${CSRF_TOKEN}" \
  -b /tmp/ov_cookie.txt \
  -d '{
    "runtimeAutoReleaseEnabled": true,
    "runtimeReleaseIdleTtlSeconds": 300
  }' | jq .
```

预期：`{"success": true}`。  
如果你用 operator/viewer key，预期 `403`。

### 20.5 创建 Workflow（租户内）

```bash
curl -s -X POST "${BASE_URL}/api/v1/workflows" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: ${OP_KEY}" \
  -H "X-Tenant-Id: ${TENANT_ID}" \
  -H "X-CSRF-Token: ${CSRF_TOKEN}" \
  -b /tmp/ov_cookie.txt \
  -d '{
    "namespace": "'"${TENANT_ID}"'",
    "name": "hello-workflow",
    "description": "first workflow",
    "tags": ["demo"],
    "metadata": {}
  }' | tee /tmp/wf-create.json | jq .
```

提取 `workflow_id`：

```bash
export WORKFLOW_ID="$(jq -r '.id' /tmp/wf-create.json)"
echo "${WORKFLOW_ID}"
```

### 20.6 查询 Workflow

```bash
curl -s "${BASE_URL}/api/v1/workflows/${WORKFLOW_ID}" \
  -H "X-Api-Key: ${OP_KEY}" \
  -H "X-Tenant-Id: ${TENANT_ID}" | jq .
```

### 20.7 创建版本（最小 DAG 示例）

```bash
curl -s -X POST "${BASE_URL}/api/v1/workflows/${WORKFLOW_ID}/versions" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: ${OP_KEY}" \
  -H "X-Tenant-Id: ${TENANT_ID}" \
  -H "X-CSRF-Token: ${CSRF_TOKEN}" \
  -b /tmp/ov_cookie.txt \
  -d '{
    "description": "v1",
    "dag": {
      "nodes": [
        {
          "id": "n1",
          "type": "start",
          "label": "start",
          "config": {}
        }
      ],
      "edges": []
    }
  }' | tee /tmp/wf-version.json | jq .
```

提取 `version_id`：

```bash
export VERSION_ID="$(jq -r '.version_id' /tmp/wf-version.json)"
echo "${VERSION_ID}"
```

### 20.8 发起执行

```bash
curl -s -X POST "${BASE_URL}/api/v1/workflows/${WORKFLOW_ID}/executions" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: ${OP_KEY}" \
  -H "X-Tenant-Id: ${TENANT_ID}" \
  -H "X-CSRF-Token: ${CSRF_TOKEN}" \
  -b /tmp/ov_cookie.txt \
  -d '{
    "workflow_id": "'"${WORKFLOW_ID}"'",
    "version_id": "'"${VERSION_ID}"'",
    "input_data": {}
  }' | tee /tmp/wf-exec.json | jq .
```

提取 `execution_id`：

```bash
export EXECUTION_ID="$(jq -r '.execution_id' /tmp/wf-exec.json)"
echo "${EXECUTION_ID}"
```

### 20.9 查询执行状态

```bash
curl -s "${BASE_URL}/api/v1/workflows/${WORKFLOW_ID}/executions/${EXECUTION_ID}/status" \
  -H "X-Api-Key: ${OP_KEY}" \
  -H "X-Tenant-Id: ${TENANT_ID}" | jq .
```

### 20.10 跨租户访问验证（应失败）

```bash
curl -i -s "${BASE_URL}/api/v1/workflows/${WORKFLOW_ID}" \
  -H "X-Api-Key: ${OP_KEY}" \
  -H "X-Tenant-Id: tenant-other"
```

预期：`403` 或 `404`（取决于防护链路命中位置），总之不应返回资源内容。

### 20.11 管理员权限验证（非管理员调用 system 写接口）

```bash
curl -i -s -X POST "${BASE_URL}/api/system/engine/reload" \
  -H "X-Api-Key: ${OP_KEY}" \
  -H "X-Tenant-Id: ${TENANT_ID}" \
  -H "X-CSRF-Token: ${CSRF_TOKEN}" \
  -b /tmp/ov_cookie.txt
```

预期：`403`。

### 20.12 审计日志查询（管理员）

```bash
curl -s "${BASE_URL}/api/v1/audit/logs?limit=20&offset=0" \
  -H "X-Api-Key: ${ADMIN_KEY}" \
  -H "X-Tenant-Id: ${TENANT_ID}" | jq .
```

### 20.13 一键安全回归脚本

```bash
cd perilla
python backend/scripts/security_regression.py \
  --base http://127.0.0.1:8000 \
  --api-key "${ADMIN_KEY}" \
  --tenant-id "${TENANT_ID}" \
  --json-output /tmp/security-regression.json \
  --junit-output /tmp/security-regression.xml \
  --suite-name security_regression_local

backend/scripts/test_tenant_security_regression.sh
scripts/acceptance/run_security_regression.sh
```

生成 JUnit 报告：

```bash
cd perilla
JUNIT_XML_PATH=test-reports/tenant-security-regression.xml backend/scripts/test_tenant_security_regression.sh
```

### 20.14 手动触发 CI（可选）

在 GitHub Actions 页面选择：

- `tenant-security-regression` 或 `security-regression`
- 点击 `Run workflow`
- 可选输入：`slow_threshold_seconds`（正整数）

### 20.15 清理临时变量（可选）

```bash
unset BASE_URL ADMIN_KEY OP_KEY TENANT_ID CSRF_TOKEN WORKFLOW_ID VERSION_ID EXECUTION_ID
rm -f /tmp/wf-create.json /tmp/wf-version.json /tmp/wf-exec.json /tmp/ov_cookie.txt /tmp/ov_health_headers.txt
```

### 20.16 Agent Run 幂等请求示例

```bash
export IDEM_KEY="agent-run-$(date +%s)"
curl -s -X POST "${BASE_URL}/api/v1/agents/YOUR_AGENT_ID/run" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: ${OP_KEY}" \
  -H "X-Tenant-Id: ${TENANT_ID}" \
  -H "X-CSRF-Token: ${CSRF_TOKEN}" \
  -H "Idempotency-Key: ${IDEM_KEY}" \
  -b /tmp/ov_cookie.txt \
  -d '{"input":"hello"}' | jq .
```

说明：

- 重试时保持 `Idempotency-Key` 与请求体一致；
- 若同 key 改了请求体，预期返回 `409`。

### 20.17 Workflow 审批任务查询（新格式/兼容格式）

```bash
# 新结构化格式（默认）
curl -s "${BASE_URL}/api/v1/workflows/${WORKFLOW_ID}/executions/${EXECUTION_ID}/approvals" \
  -H "X-Api-Key: ${OP_KEY}" \
  -H "X-Tenant-Id: ${TENANT_ID}" | jq .

# 兼容旧格式（含弃用提示头）
curl -i -s "${BASE_URL}/api/v1/workflows/${WORKFLOW_ID}/executions/${EXECUTION_ID}/approvals?legacy=true" \
  -H "X-Api-Key: ${OP_KEY}" \
  -H "X-Tenant-Id: ${TENANT_ID}"
```
