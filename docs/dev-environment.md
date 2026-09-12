# 本地开发与调试环境

本文记录离线版（`offline` / v1.2.11）在当前 Windows 机器上的开发调试环境搭建方式、
已验证的可用链路，以及搭建与加固过程中发现并修复的缺陷（第 5 节为环境阻断类问题，
第 6 节为"静态服务与 DEBUG 耦合 + 本机越权"的安全解耦改造，第 7 节为 Electron
桌面登录链路从假登录改为真实 JWT 的修复）。

## 1. 工具链

| 组件 | 版本 | 安装/管理方式 |
| --- | --- | --- |
| fnm | 1.39.0 | `winget install -e --id Schniz.fnm` |
| Node.js | v24.21.0（LTS） | `fnm install lts-latest`（默认版本 `default`） |
| npm | 11.19.0 | 随 Node 分发 |
| Python | 3.13.15 | 系统安装，虚拟环境位于仓库 `.venv\` |
| pip | 26.x | 虚拟环境内 |
| Django | 6.1.1 | `requirements.txt`（`Django>=5.0.3` 解析结果） |
| sqlcipher3 | 0.6.2 | `requirements-sqlcipher.txt`（提供 cp313 win_amd64 轮子） |

一键搭建（幂等，可重复执行）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\dev\setup_env.ps1
```

### 1.1 镜像与 PATH

- Node 发行包镜像通过 `FNM_NODE_DIST_MIRROR=https://npmmirror.com/mirrors/node` 指定。
- npm registry 与 Electron 二进制镜像写在用户级 `~/.npmrc`（不污染仓库）：

  ```ini
  registry=https://registry.npmmirror.com
  electron_mirror=https://npmmirror.com/mirrors/electron/
  electron_builder_binaries_mirror=https://npmmirror.com/mirrors/electron-builder-binaries/
  ```

  注意：npm 11 已不再接受 `npm config set electron_mirror ...`（会报
  `is not a valid npm option`），必须直接写入 `.npmrc` 或设置环境变量
  `ELECTRON_MIRROR`。
- winget 安装的 fnm 位于
  `%LOCALAPPDATA%\Microsoft\WinGet\Packages\Schniz.fnm_Microsoft.Winget.Source_8wekyb3d8bbwe`，
  该目录已写入用户 PATH，但**已打开的终端不会自动刷新**，需重开会话。
- PowerShell profile（`$PROFILE.CurrentUserAllHosts`）已加入 fnm 初始化，
  新终端可直接使用 `node` / `npm`，并在含版本声明文件的目录自动切换：

  ```powershell
  fnm env --use-on-cd --shell power-shell | Out-String | Invoke-Expression
  ```

- 执行策略需为 `RemoteSigned`（`CurrentUser` 作用域），否则 npm 的 `npm.ps1` 无法运行：

  ```powershell
  Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
  ```

### 1.2 已知 fnm 限制

`fnm exec --using=default npm -v` 会失败（`program not found`），因为 fnm 无法直接
spawn `npm.cmd` 批处理入口。绕过方式是显式把 node 安装目录加入 PATH 后调用 `npm.cmd`，
`setup_env.ps1` 已按此实现。

## 2. 配置文件

`.env.example` 列出 settings.py 支持的关键环境变量，复制为 `.env` 使用（`.env` 已被忽略）：

```powershell
Copy-Item .env.example .env
```

要点：

- `DJANGO_SECRET_KEY` 在示例中保持注释状态。写成空值 `DJANGO_SECRET_KEY=` 会覆盖
  settings 的 insecure 默认值，导致启动时报
  `ImproperlyConfigured: The SECRET_KEY setting must not be empty.`（已实测）。
- `DJANGO_DEBUG` 在**桌面/离线模式**下已不再影响静态资源：`heritage_system/urls.py`
  在 `HERITAGE_DESKTOP_MODE=1` 时无条件注册 `serve` 路由提供 `/static/**` 与 `/media/**`，
  不再依赖 `django.conf.urls.static.static()` 的 DEBUG 开关（该函数在 `DEBUG=False`
  时直接返回空列表，见 `django/conf/urls/static.py`）。
  但**非桌面模式**下用 `manage.py runserver` 直接跑网页调试时，仍需要 `DJANGO_DEBUG=1`
  才会经 `static()` 提供 `/static/**`，否则瓦片 404。
- `DJANGO_DEBUG` 同样**不再影响 API 鉴权**。历史上 `IsManagementAdmin` 会在
  `DEBUG + 回环地址` 时放行匿名请求，现已改为必须显式设置
  `HERITAGE_DEV_ALLOW_LOCAL_BYPASS=1`（且请求来自回环地址）才生效，默认关闭。
  回归验证见 `scripts/dev/audit_debug_bypass.py`。
- `DJANGO_FORCE_HTTPS` 本地必须 `0`，否则被强制跳转 https。
- 进程内环境变量优先级高于 `.env`（已实测），因此 `desktop_backend.py` 与各调试脚本的
  显式赋值会覆盖 `.env` 中的同名项。

## 3. 日常调试命令

```powershell
# 首次建库（加密库 + config\key.bin + 超级管理员）
.venv\Scripts\python.exe manage.py sqlcipher_bootstrap

# 后端（Web 调试模式，静态资源与瓦片由 runserver 的 finders 提供）
.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000

# 前端热更新（Vite 已代理 /api、/media、/static/tiles 到后端）
cd frontend ; npm run dev

# 桌面（Electron）调试管线
powershell -File scripts\start_offline.ps1 -Mode desktop

# 改完前端源码后必须重建产物，Django 读取的是 static\frontend
cd frontend ; npm run build
```

## 4. 验证脚本

均位于 `scripts\dev\`，用 `.venv\Scripts\python.exe` 执行，全部使用临时目录，
不会污染仓库内的 `data\` / `config\`。

| 脚本 | 作用 |
| --- | --- |
| `verify_python_env.py` | 依赖导入自检，并实测 sqlcipher3 真实加解密（无 key 读取必须失败） |
| `e2e_first_run.py` | 模拟全新安装首启：建库 → 迁移 → 超级管理员初始化 → 校验密文头与密码 |
| `smoke_http.py` | 起真实 Django，验证 SPA 回退、离线瓦片、前端产物、JWT 登录、鉴权拒绝 |
| `smoke_vite_dev.py` | 同时起 Django + Vite，验证热更新开发链路（含瓦片代理） |
| `audit_debug_bypass.py` | 三段式回归：鉴权默认拒绝、DEBUG=0 静态仍可用、显式开关恢复放行 |
| `smoke_desktop_login.py` | 桌面登录链路回归：向导密码登录签发 JWT、解锁收紧接口、refresh 续期、test/test 后门已移除 |

当前实测结果（Django 6.1.1 / Python 3.13.15 / Node 24.21.0）：

```
verify_python_env.py   ALL_PY_CHECKS_PASSED
e2e_first_run.py       IS ENCRYPTED: True / admin groups: ['超级管理员'] /
                       wizard password verifies: True / test/test verifies: False
smoke_http.py          SMOKE SUMMARY: 10/10 passed
smoke_vite_dev.py      DEV-SMOKE SUMMARY: 4/4 passed
audit_debug_bypass.py  AUDIT SUMMARY: 13/13 passed
smoke_desktop_login.py DESKTOP-LOGIN SUMMARY: 12/12 passed
manage.py check        no issues（非桌面模式）
manage.py check        no issues (1 silenced)（HERITAGE_DESKTOP_MODE=1）
manage.py test core    Ran 15 tests ... OK
manage.py makemigrations --check --dry-run   No changes detected
```

## 5. 搭建过程中发现并修复的缺陷

### 5.1 sqlcipher 后端与 Django 6.1 不兼容（阻断首次建库）

`heritage_system\db\backends\sqlcipher\base.py` 复用 Django 的 sqlite3 后端，但
sqlcipher3 的连接对象是 C 扩展类型（**不可 monkeypatch**），缺少标准库
`sqlite3.Connection.getlimit()`。Django 6.1 起（实测 6.0.8 尚无此调用）
`DatabaseOperations._quote_params_for_last_executed_query()` 会调用该方法，而该路径位于
DEBUG 模式的 SQL 日志包装器内，桌面版 `desktop_backend.py` 又硬编码 `DJANGO_DEBUG='1'`，
于是首次 `migrate` 在第一条带参数的 INSERT 上抛
`AttributeError: 'sqlcipher3.dbapi2.Connection' object has no attribute 'getlimit'`，
并被包装成 `TransactionManagementError`，表现为**装好依赖后依然无法启动**。

修复：新增 `SqlCipherDatabaseOperations`，按 SQLite 默认上限分批实现该方法
（与 Django 5.x 行为一致），并通过 `ops_class` 注入。已分别在 Django
5.2.17 / 6.0.8 / 6.1.1 上验证端到端建库通过。

### 5.2 桌面模式 `manage.py check` 失败（阻断 CI 与自检）

`DESKTOP_MODE` 下 `STATIC_ROOT` 与 `STATICFILES_DIRS[0]` 同为 `APP_DIR/static`，
触发 `staticfiles.E002` ERROR。

修复：仅在桌面模式 `SILENCED_SYSTEM_CHECKS = ['staticfiles.E002']`。
这里刻意**不**清空 `STATICFILES_DIRS`：实测清空后 `runserver` 的
`StaticFilesHandler` 无法经 finders 命中，`/static/tiles/**` 与前端产物会 404，
反而破坏开发调试。桌面版不执行 `collectstatic`，该告警在此确属误报。

### 5.3 Vite 开发服务器缺少瓦片代理（离线地图无法调试）

`vite.config.js` 的 `server.proxy` 只转发 `/api` 与 `/media`，而 Vite 的 `base` 为
`/static/frontend/`，不会代理 `/static/tiles/**`，导致 `npm run dev` 下请求离线瓦片
一律 404。已补充 `/static/tiles` 与 `/static/dem_tiles` 两条代理规则，
`smoke_vite_dev.py` 验证通过。

## 6. 静态服务与 DEBUG 解耦 + 鉴权收紧（原遗留风险，已修复）

### 6.1 问题

`core\permissions\api_permissions.py` 的 `IsManagementAdmin` 曾在
`settings.DEBUG and host in {127.0.0.1, localhost}` 时对匿名请求直接放行；
而 `desktop_backend.py` 硬编码 `DJANGO_DEBUG='1'`，等于出厂即带此绕过。
`audit_debug_bypass.py` 实测确认下列接口可被本机任意进程无 token 读取：

```
/api/v1/heritage/map-points/
/api/v1/heritage/classification-stats/
/api/v1/heritage/sites/
/api/v1/heritage/immovable/
/api/v1/system/version/
```

但 DEBUG 不能直接关掉：桌面模式的 `/static/**` 此前依赖
`django.conf.urls.static.static()`，而该函数在 `DEBUG=False` 时返回空列表，
关掉 DEBUG 会让打包版整站静态资源与离线瓦片 404。二者必须同时改。

### 6.2 修复（方案 A：显式路由兜底）

1. `heritage_system/urls.py`：在 `settings.DESKTOP_MODE` 为真时，无条件追加
   `re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT})`
   与对应的 `^media/` 路由，使静态服务与 DEBUG 彻底解耦。
   线上部署（`DESKTOP_MODE=0`）不新增路由，保持既有契约。
   `static/` 已覆盖 `frontend/`、`tiles/`、`admin/`、`app_showcase/`；
   `dem_tiles` 位于 `static/` 之外且只被服务端 rasterio 读取，不经 HTTP 暴露，故无需路由。
2. `core/permissions/api_permissions.py`：删除 `settings.DEBUG` 隐式放行，
   改为显式开关 `HERITAGE_DEV_ALLOW_LOCAL_BYPASS=1` + 回环地址才放行；默认关闭。
3. `desktop_backend.py`：`DJANGO_DEBUG` 由硬编码 `'1'` 改为
   `'1' if OFFLINE_DEBUG_MODE else '0'`（即仅 `HERITAGE_OFFLINE_DEBUG=1` 时开启）。
   打包版不设置该变量，因此默认 DEBUG=0。
4. `frontend/electron/dev-runner.cjs`：桌面开发模式仍走 `runserver`（非桌面模式），
   保留 `DJANGO_DEBUG=1` 以提供静态资源，同时显式注入
   `HERITAGE_DEV_ALLOW_LOCAL_BYPASS=1` 维持免登录调试体验。
5. `core/api/views.py`：`_resolve_public_base_url()` 的本地回落条件由
   `if settings.DEBUG` 改为 `if settings.DEBUG or settings.DESKTOP_MODE`，
   避免桌面版 DEBUG=0 后把资源 URL 误指向生产域名。

### 6.3 验证

`scripts/dev/audit_debug_bypass.py` 已升级为三段式回归测试，实测 13/13 通过：

- A：`DEBUG=1` 且未设开关时，7 个管理接口对匿名本机请求全部返回 401；
- B：`DEBUG=0` 桌面模式下，离线瓦片、前端产物、SPA 回退、JWT 登录、
  带 token 的管理接口全部正常（证明解耦成立）；
- C：显式设 `HERITAGE_DEV_ALLOW_LOCAL_BYPASS=1` 时，本机匿名请求恢复 200
  （证明开发便利仍可用，只是改为显式 opt-in）。

真实 `desktop_backend.py`（waitress）实测：默认 DEBUG=0 下
`/static/tiles/...` 200、`/login` 200、`/api/v1/heritage/sites/` 401；
设 `HERITAGE_OFFLINE_DEBUG=1` 后瓦片仍 200。

> 安全边界说明：新增的 `serve` 路由会暴露 `STATIC_ROOT` 全目录。已核查
> `static/` 下 1303 个文件仅含前端产物、瓦片与 Django admin 静态资源，
> 不含密钥/数据库/环境文件（`key.bin` 在 `config/`、库在 `data/`，均不在其中）。

## 7. Electron 桌面登录链路修复

### 7.1 问题

鉴权收紧后，桌面端仍走"假登录"，导致登录后拿不到 JWT、所有管理接口 401：

- `frontend/electron/main.cjs` 的 `auth:login` IPC 用硬编码 scrypt 比对
  `test/test`（`LOCAL_ADMIN_HASH`）与遗留 `admin/admin123`，**从不调用后端**，
  因此永远不签发 JWT。
- `frontend/src/views/Login.vue` 登录成功后只在 `sessionStorage` 写
  `desktop_local_auth=1`，并跳 `/dashboard?desktop_auth=1`。
- `frontend/src/router/index.js` 的 `isDesktopAuthorized()` 把该标记当作"已登录"，
  **绕过全部鉴权**，渲染进程始终没有 token。

### 7.2 修复

1. `main.cjs`：删除 `crypto` 依赖、`LOCAL_ADMIN_*` 常量、`derivePasswordHash` /
   `safeCompareHash` / `verifyLocalAdmin`，以及 `auth:login` IPC。主进程不再接触
   用户名/密码。新增 `auth:login-succeeded` IPC，仅做窗口切换（开主窗、关登录窗）。
   `desktopLoginPassed` 改为 `loginWindowAuthenticated`，只用于决定"关闭登录窗时是否退出"，
   不参与任何权限判定。主窗入口路由去掉 `?desktop_auth=1`。
2. `preload.cjs`：`electronAPI.login(username,password)` 替换为
   `electronAPI.notifyLoginSucceeded()`。
3. `Login.vue`：`handleLogin` 改为调用 `authStore.login()`（真实
   `POST /api/v1/system/login/`），成功后写 localStorage，再按 `login_window` 决定
   是通知主进程切窗还是按 `redirect` 路由。移除 `desktop_local_auth` 标记与
   `?desktop_auth=1` 兜底跳转；用户名占位符由"例如：test"改为"请输入用户名"。
4. `router/index.js`：删除 `DESKTOP_AUTH_KEY` / `getDesktopAuthStorage` /
   `isDesktopAuthorized` 及 `beforeEach` 中的 `desktop_auth` 绕过分支。登录态一律由
   `authStore.isAuthenticated`（即 localStorage 中的 JWT）判定。仅保留
   `isDesktopLoginWindowRoute` 放行登录小窗本身，避免与鉴权重定向死循环。
5. `authStore.js`：`clearAuth` 仍清理历史遗留的 `desktop_local_auth`（一次性迁移），
   但不再有任何写入路径。

登录窗口与主窗口同源、共享默认 session（无 `partition` 隔离），故登录窗写入的
localStorage 令牌对主窗口可见。

### 7.3 验证

`scripts/dev/smoke_desktop_login.py`（DEBUG=0 桌面模式）实测 12/12：
向导密码 `admin` 登录返回 access/refresh → 令牌解锁 `system/version`、
`heritage/sites` → refresh 续期成功 → `test/test`、`admin/test` 均 401 →
匿名请求 401。前端 `npm run build` 通过，新 bundle 已不含 `desktop_auth` 绕过、
保留 `/api/v1/system/login/`。

## 8. 仍待处理

v1.2.12 合并与迁移编号重排仍按 `docs/offline-sync-playbook.md` 推进。
本次登录链路修复未触碰 `system/auth/LoginView.vue`（该组件当前未被路由引用，
属孤儿文件；如需启用可后续将其接入 `/login`）。

