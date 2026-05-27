# 本地账号、登录跳转与平台角色说明

> 本文档整理自产品问答，说明 **未登录自动跳转登录页**、**管理员如何产生**、**admin / operator / viewer 功能边界**。  
> 与主教程 **[tutorial.md](tutorial.md) 第 8.2 节**、**[tutorial-security-baseline.md](tutorial-security-baseline.md)** 互补；实现以当前代码为准。

---

## 1. 三种身份方式（可并存）

| 方式 | 典型场景 | 环境变量（节选） | 控制台入口 |
|------|----------|------------------|------------|
| **本地账号** | 本机 / 内网多用户 | `LOCAL_AUTH_ENABLED=true` | `/register`、`/login` |
| **企业 IdP（OIDC）** | 内网统一认证 | `OIDC_ENABLED=true`、`OIDC_ISSUER`、… | 登录页 / **Settings → 企业与合规** |
| **API Key + 租户** | 脚本、自动化、与 RBAC 并存 | `RBAC_*`、`API_KEYS_JSON` | **Settings → Backend** |

`./run-backend.sh` 在未覆盖时默认 **`LOCAL_AUTH_ENABLED=true`**、**`LOCAL_AUTH_ALLOW_REGISTRATION=true`**。面向本机/内网，**不提供公网开放注册**。

---

## 2. 未登录时自动跳转到登录页

### 2.1 如何开启

| 层级 | 配置 | 行为 |
|------|------|------|
| **后端** | `AUTH_REQUIRE_LOGIN=true` | 未携带本地 Cookie、OIDC Bearer 或 `X-Api-Key` 的 `/api/*` 返回 **401**（健康检查、`/api/v1/auth/*` 等公开路径除外） |
| **前端** | 读取 `GET /api/v1/auth/session` 的 `require_login` | 为 `true` 且 `authenticated=false` 时，除白名单路由外跳转到 **`/login?redirect=...`** |

**白名单路由**（不强制登录）：`/login`、`/register`、`/auth/callback`。

**推荐环境变量**（写入 `backend/.env` 或启动环境后 **重启后端**）：

```bash
AUTH_REQUIRE_LOGIN=true
LOCAL_AUTH_ENABLED=true
LOCAL_AUTH_ALLOW_REGISTRATION=true   # 若仅允许首个 admin 注册，见下文 §3.2
```

`run-backend.sh` 中亦有注释行 `# export AUTH_REQUIRE_LOGIN=true`，取消注释等效。

### 2.2 前端路由守卫

实现位置：`frontend/src/router/index.ts`。逻辑摘要：

- 访问 `meta.authPage === true` 的页面 → 直接放行；
- 否则请求 `/api/v1/auth/session`；
- 若 `require_login && !authenticated` → `next({ name: 'login', query: { redirect: to.fullPath } })`。

### 2.3 后端 API 门禁

实现位置：`backend/middleware/local_auth_context.py`。在 `auth_require_login=true` 且 `local_auth_enabled` 时，对非公开 `/api/*` 路径要求 `auth_method` 为 `local`、`oidc` 或 `api_key` 之一。

### 2.4 自检命令

```bash
curl -s http://127.0.0.1:8000/api/v1/auth/config | jq .
curl -s http://127.0.0.1:8000/api/v1/auth/session | jq .
```

期望：`config.auth_require_login` 为 `true`；未登录时 `session.authenticated` 为 `false`，`session.require_login` 为 `true`。

---

## 3. 能否注册为管理员？是否有审批？

### 3.1 结论（简短）

- **不能**在注册页自选「注册为管理员」。
- **没有**人工审批、邀请码或管理员「通过注册」流程。
- **规则**：数据库中 **第一个** 本地用户 → **`admin`**；**之后所有** 注册用户 → **`operator`**。

### 3.2 实现依据

逻辑位于 `backend/core/security/local_auth.py` 的 `register_user`：

```text
role = admin   当 platform_users 表用户数为 0
role = operator  否则
```

注册成功后自动创建会话并写入 HttpOnly Cookie **`perilla_session`**（见 `backend/api/auth.py` 的 `/register`、`/login`）。

### 3.3 关闭公开注册

```bash
LOCAL_AUTH_ALLOW_REGISTRATION=false
```

关闭后 **`/register`** 不可用；当前版本 **没有**「管理员在界面创建用户 / 审批待审用户」API。后续加人需自行扩展，或临时改库表 `platform_users`（不推荐生产随意操作）。

### 3.4 将已有用户提升为 admin

当前 **无** Web 用户管理接口。可选方式（运维向）：

- 直接更新数据库 `platform_users.platform_role = 'admin'`；
- 或清空用户表后由目标用户 **第一个** 注册（仅适合初始化环境，**勿**在生产随意使用）。

---

## 4. 平台角色与功能区分

平台角色与 **工作流资源内 ACL**（owner/acl）是 **两套正交机制**。本地账号角色存于 `platform_users.platform_role`；登录后由 `LocalAuthContextMiddleware` 写入 `request.state.platform_role`。

### 4.1 三种角色一览

| 角色 | 典型来源 | 定位 |
|------|----------|------|
| **admin** | 首个本地注册用户；或 `RBAC_ADMIN_API_KEYS`；OIDC 映射（若配置） | 控制面、敏感运维、Eval、备份、MCP 等 |
| **operator** | 第 2 个及以后的本地注册用户；或 `RBAC_OPERATOR_API_KEYS` | 日常对话、工作流、Agent 创建与运行 |
| **viewer** |  mainly `RBAC_VIEWER_API_KEYS` | 只读；在 RBAC  enforcement 下限制写操作 |

侧栏底部展示当前用户名与角色（`nav.role_admin` / `role_operator` / `role_viewer`）。

### 4.2 日常功能（operator vs viewer）

在 **`RBAC_ENABLED=true`** 且 **`RBAC_ENFORCEMENT=true`** 时，`backend/middleware/rbac_enforcement.py` 对 **viewer** 拦截：

- 对工作流、模型、备份、审计等路径的 **POST / PUT / PATCH / DELETE**；
- 部分敏感只读（如 `/api/events` 的 GET）。

**operator** 不受上述 viewer 限制，可正常使用聊天、工作流、Agent 等。

### 4.3 管理 / 运维功能（偏 admin）

下列能力在代码中多依赖 **`require_platform_admin`** 或 **`require_authenticated_platform_admin`**，例如：

- Eval 回归（`/settings/eval`，`backend/api/eval.py`）；
- 备份、模型备份、MCP 配置、技能平台路由；
- 模型注册 / 扫描 / 加载（`main.py` 中部分路由）；
- 部分系统设置与插件管理（`backend/api/system.py`）；
- 审计相关只读（`role_may_access_audit` 仅 admin）。

详见主教程 **tutorial.md §8.2 C**（`/settings/eval` 等）。

### 4.4 本地 admin 与 Admin API Key（常见误区）

`require_authenticated_platform_admin`（`backend/core/security/deps.py`）在 **非开发放宽** 时仍可能要求请求头 **`X-Api-Key`** 且 Key 映射为 admin。

| 环境 | 本地账号 `platform_role=admin` | 控制面 / Eval 等「要 admin 的 API」 |
|------|-------------------------------|-------------------------------------|
| **DEBUG=true** 且 **未配置** `RBAC_ADMIN_API_KEYS` | 是 | 通常可用（`local_dev_control_plane_unlocked()`） |
| **生产** 或 **已配置** `RBAC_ADMIN_API_KEYS` | 是 | 往往还需 **Settings → Backend** 填写 **Admin API Key** |

侧栏 **「本地开发（管理员）」** 表示 debug 下的放宽，**不等于** 已用本地账号登录且库中角色为 admin。

### 4.5 身份方式与角色来源对照

| 身份方式 | 角色从哪来 |
|----------|------------|
| **本地账号** | 注册时写入 `platform_users.platform_role` |
| **API Key** | `RBAC_ADMIN_API_KEYS` / `RBAC_OPERATOR_API_KEYS` / `RBAC_VIEWER_API_KEYS` |
| **未登录 + DEBUG 放宽** | 界面可能表现为可访问控制面，但 `auth_method` 仍为 `anonymous` |

`AUTH_REQUIRE_LOGIN=true` 时，须至少具备 **本地登录 / OIDC / API Key** 之一，不能长期匿名使用全站 API。

---

## 5. 部署建议对照表

| 目标 | 建议 |
|------|------|
| 内网必须登录才能用 | `AUTH_REQUIRE_LOGIN=true`，重启后端；浏览器访问任意业务页应跳转 `/login` |
| 只要一个超级管理员 | 第一个账号注册后设置 `LOCAL_AUTH_ALLOW_REGISTRATION=false` |
| 防止后来者成为 admin | 已默认满足（仅首用户为 admin）；勿开放公网 `/register` |
| 生产多人 + 严格分工 | `RBAC_ENABLED=true`、`RBAC_ENFORCEMENT=true`，按人用不同 API Key；敏感接口配置 admin Key |
| 需要「管理员审批新用户」 | **当前未实现**；需产品化：邀请码、admin 建号、待审核表等 |

---

## 6. 相关文件索引

| 主题 | 路径 |
|------|------|
| 注册 / 登录 / 会话 API | `backend/api/auth.py` |
| 注册角色分配、密码与会话 | `backend/core/security/local_auth.py` |
| Cookie → `platform_role` | `backend/middleware/local_auth_context.py` |
| 强制登录 API 401 | 同上 + `auth_require_login` |
| 角色枚举与 viewer 路径规则 | `backend/core/security/rbac.py` |
| FastAPI 依赖（admin / write / audit） | `backend/core/security/deps.py` |
| 用户表 ORM | `backend/core/data/models/platform_user.py` |
| 配置项 | `backend/config/settings.py`、`backend/.env.example`、`run-backend.sh` |
| 登录 / 注册页 | `frontend/src/views/LoginView.vue`、`RegisterView.vue` |
| 路由守卫 | `frontend/src/router/index.ts` |
| 侧栏登录入口与会话展示 | `frontend/src/components/layout/NavigationSidebar.vue` |

---

## 7. 快速操作清单

1. 打开 **`http://127.0.0.1:5173/register`**，创建 **首个** 用户（自动 **admin**）。  
2. 打开 **`http://127.0.0.1:5173/login`** 登录；会话 Cookie 名 **`perilla_session`**。  
3. 需要全员必须先登录：设置 **`AUTH_REQUIRE_LOGIN=true`** 并重启后端。  
4. 不需要再有人自助注册：设置 **`LOCAL_AUTH_ALLOW_REGISTRATION=false`**。  
5. 生产使用 Eval / MCP / 备份：配置 **admin API Key**（**Settings → Backend**），并阅读 **tutorial-security-baseline.md**。

---

*文档版本：与仓库本地账号 / `AUTH_REQUIRE_LOGIN` 实现同步整理；若行为变更请以代码与 OpenAPI 为准。*
