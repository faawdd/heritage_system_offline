# 离线版（offline 分支）同步与修复手册

> 生成时间：2026-09-12。记录 `offline` 分支与在线版（`origin/master` / `v1.2.12`）的分叉现状、
> 已完成的止血修复，以及阶段 2 合并的**实际执行结果**。
>
> **当前状态：阶段 1 与阶段 2 均已完成。** 阶段 2 合并提交为 `bfd9c67`，
> 全过程与验证结果见第 7 节；第 3、4 节保留为决策依据与背景（其中"未执行"等措辞已过期）。

## 1. 仓库拓扑现状

| 引用 | commit | 日期 | 含义 |
|---|---|---|---|
| `offline`（当前 HEAD） | `bfd9c67` | 2026-09-13 | **阶段 1 + 阶段 2 均已完成**（已合入 v1.2.12） |
| `offline`（阶段 1 末端） | `95e9eef` / tag `v1.2.11` 之后 | 2026-09-12 | 合并前状态，回滚点 |
| `backup/offline-v1.2.4` | `0ff901b` / tag `v1.2.4` | 2026-08-03 | 止血前原始状态（回滚点） |
| `fix/offline-v1.2.11` | `f62028d` | 2026-08-04 | 保护分支，防止悬空标签丢失 |
| `feat/online-v1.2.12-clean` | `66f6f51` | 2026-09-13 | 净化后的在线线（**本次合并的父 2**） |
| `feat/online-v1.2.12` | `fcdb456` | 2026-09-02 | 在线版新功能线原始头（**含敏感文件，勿外发**） |
| `origin/master` | `bee7f24` | 2026-08-03 | 在线版旧头 |

两条线的共同祖先是 `53b1eee`（merge-base）。

**重要历史教训**：v1.2.5–v1.2.12 这些标签此前**不属于任何分支**
（`git branch --contains` 全为空），所以修复长期"存在但没人能拿到"。
现已用 `fix/`、`feat/`、`backup/` 分支固化，请勿删除。

## 2. 阶段 1（已完成）：fast-forward 到 v1.2.11

`git merge --ff-only v1.2.11`，一次性带回以下致命修复：

| 问题 | 修复提交 | 落点 |
|---|---|---|
| 桌面端打开 `/login`、`/dashboard` 直接 404（缺 SPA history 回退路由） | `4e4ce77` | `heritage_system/urls.py` `frontend_spa_fallback` |
| 明文库存在 + sqlcipher 可用 → 永久启动失败 | `4e4ce77` | `maintenance.py` `_is_plain_sqlite_database` / `_convert_plain_sqlite_to_sqlcipher_database` |
| `key.bin` 丢失 → 硬崩溃 | `6f9e55f` | `connection.py` `_should_fallback_without_key` / `_open_plain_sqlite` |
| 配置/密钥写进只读安装目录（Program Files） | `f62028d` | `main.cjs` `userRuntimeRoot` → `app.getPath('userData')`，新增 `HERITAGE_UPLOAD_DIR` / `HERITAGE_BACKUP_DIR` |
| 数据目录被清空后跳过向导 | `0795906` | `main.cjs` `requiresInitialization` 增加 `hasDatabase` 判断 |
| 登录窗被路由守卫重定向 | `0795906` | `main.cjs` `/login?login_window=1` + `router/index.js` `isDesktopLoginWindowRoute` |
| Windows 包名错误导致 `pip install` 失败 | `d61e716` | `requirements-sqlcipher.txt` `sqlcipher3-binary` → `sqlcipher3` |
| 离线瓦片缺失 / 只到 z13 | `536b643` / `dce7aa7` | `static/tiles/tianditu/**`（约 1200 张）、`DEFAULT_ZOOM_MAX = 18`、`scripts/refresh_tianditu_tiles.sh` |
| Electron 下载镜像 | `fdc5bb4` | `scripts/build_desktop_runtime.{ps1,sh}` |

已验证：`python -m py_compile` 通过；`git status` 干净。

## 3. 阶段 1 遗留问题（v1.2.11 未覆盖，需自行修复）

> **状态更新（2026-09-13）**：本节问题 **1、2、3、5、6、7、10 已在 Stage 1 修复并提交**
> （`d9ac9a6` / `202ef2b` / `d3856d1` / `95e9eef`），修复细节见 `docs/dev-environment.md`
> 第 5–7 节。**问题 4（向导密码落盘时序）与问题 9（备份不含 `key.bin` / uploads）仍未处理**，
> 见第 7.6 节。以下内容保留为根因分析依据。

这些是**登录不可用的真正根因**，fast-forward 并不能解决：

1. **桌面登录只认硬编码 `test/test`**
   `frontend/electron/main.cjs:26-29` 的 `LOCAL_ADMIN_HASH` 经 scrypt 实测等于 `'test'`，
   `LEGACY_LOCAL_ADMIN_HASH` 等于 `'admin123'`。`verifyLocalAdmin()`（main.cjs:410）
   **与初始化向导里用户设置的超级管理员密码完全无关**。
   → 建议：向导完成后由主进程调用 `POST /api/v1/system/login/` 校验并换取 JWT，
   通过 `preload` 注入渲染进程，删除硬编码哈希。

2. **IPC 登录成功后拿不到 JWT**
   `frontend/src/views/Login.vue:117-140` 仅设置 `sessionStorage.desktop_local_auth='1'`，
   从不调用 `authStore.login()` → `accessToken` 为空 → 所有 `IsAuthenticated` 接口 401。
   功能完整的 `frontend/src/views/system/auth/LoginView.vue`（会真正 `authStore.login()`）
   **当前无任何引用**（`router/index.js:20` 用的是 `views/Login.vue`）。

3. **越权风险 / 遮羞布**
   `core/permissions/api_permissions.py:17-20`：`DEBUG and host in {127.0.0.1, localhost}` 时无条件放行；
   而 `desktop_backend.py:145` 用 `os.environ['DJANGO_DEBUG'] = '1'` **硬赋值**（非 setdefault）。
   → 任意本机进程可无认证读写全部数据。应移除该放行分支，并让 DEBUG 可配置。

4. **向导密码可能被静默丢弃**
   `main.cjs:636` 先把 `bootstrapAdminPassword` 置空落盘，`:668` 才写回；`:938-945` 后端就绪即清空。
   若在此期间崩溃，磁盘密码为空 → `maintenance.py:39-40` 回落到 `Admin@123456`。
   另外 `ensure_roles_and_super_admin`（maintenance.py:132-140）只要已存在任一 superuser 就整体 return，
   后续账号异常无法通过向导修复。

5. **死代码**：`desktop_backend.py:92-112` `_load_admin_bootstrap()`（含 `HERITAGE_OFFLINE_DEBUG`、
   `bootstrap-admin.json`）**从未被调用**，导致 `scripts/start_offline.ps1:54` 的调试开关在打包路径无效。

6. **静态目录冲突**：`settings.py:247-252` 桌面模式下 `STATICFILES_DIRS` 与 `STATIC_ROOT` 同为
   `APP_DIR/static`，一旦执行 `collectstatic` 即 `ImproperlyConfigured`。

7. **HTTPS 默认值**：`settings.py:140` `FORCE_HTTPS` 默认 `'1'`，而 offline 仓库**没有 `.env`**
   （master 才有，内容含 `DJANGO_DEBUG=1` / `DJANGO_FORCE_HTTPS=0`）。任何绕过 `desktop_backend.py`
   直接 `manage.py runserver` 的启动都会被 301 到 https 且 `SESSION_COOKIE_SECURE=True` → 登录不可用。
   → 建议：`DESKTOP_MODE` 下强制 `FORCE_HTTPS=False`，或提交 `.env.example` 并在打包时生成 `.env`。

8. **离线场景不该联网**：`settings.py:295` `DEM_DOWNLOAD_PROXY_ENABLED` 默认 `True`（socks5:10808）；
   `settings.py:283-286` 硬编码 `OPENTOPO_API_KEY`。

9. **备份不含密钥**：`main.cjs:690-802` 备份 zip 只打包 `dataDir` + `logDir` + `desktop-config.json`，
   不含 `config/key.bin`；合并 v1.2.11 后 uploads 移到 `userData/uploads`，备份也不含照片。
   恢复 = 用新 key 打开旧密文库 → 数据不可读。

10. **前端产物与源码不同步（务必注意）**
    `static/frontend/assets/index-BZHQs0e8.js` 内搜 `/static/tiles` → **MISS**，
    `system/admin`、`admin-entry` → **MISS**。即打包进安装包的 JS 是旧版，

## 4. 阶段 2：合并 v1.2.12 在线版功能（已完成，见第 7 节）

### 4.1 当初为何被中止

`git merge --no-commit --no-ff v1.2.12` 产生 **18 个冲突文件 / 约 64 个冲突块**，其中包含
**整段模板级冲突**（`ProjectDetailView.vue` 单块跨 522 行、`ProjectListView.vue` 6 块、
`DataManagementView.vue` add/add 冲突）。当前环境**没有 `node`/`npm`/`.venv`/Django**，
无法构建前端、无法跑 `manage.py check` 与测试，手工改写数百行 Vue 模板属于不可验证的高风险改动，
因此中止合并以保住已验证可用的 v1.2.11 状态。

### 4.2 已验证的冲突解法（可直接照做）

**A. `core/api/urls.py` + `core/api/views.py`（关键：JWT 认证兼容性）**

在线版把项目接口直接指向 `legacy_views.land_project_*_api`，而这些函数带
`@staff_member_required`（**仅 session 认证**）；离线版 Vue 用 **JWT Bearer**，
所以离线版专门写了 `Project*APIView(APIView)` 包装类（`core/api/views.py:358-419`，
用 `_call_legacy_view()` 剥装饰器 + `IsManagementAdmin` 权限）。

→ **必须保留离线版的 DRF 包装类**，并为在线版新增的 5 个端点补同类包装，否则项目管理在离线版全线 403：

```python
# core/api/views.py —— 接在 ProjectControlsAPIView 之后
class ProjectLinkKmlRecordAPIView(APIView):
    permission_classes = [IsManagementAdmin]
    def post(self, request, project_id):
        return _call_legacy_view(legacy_views.land_project_link_kml_record_api, request, project_id)

class ProjectDocumentsArchiveAPIView(APIView):
    permission_classes = [IsManagementAdmin]
    def get(self, request, project_id):
        return _call_legacy_view(legacy_views.land_project_documents_archive_api, request, project_id)

class ProjectDocumentDownloadAPIView(APIView):
    permission_classes = [IsManagementAdmin]
    def get(self, request, project_id, document_id):
        return _call_legacy_view(legacy_views.land_project_document_download_api, request, project_id, document_id)

class ProjectDocumentDeleteAPIView(APIView):
    permission_classes = [IsManagementAdmin]
    def post(self, request, project_id, document_id):
        return _call_legacy_view(legacy_views.land_project_document_delete_api, request, project_id, document_id)

class ProjectGenerateDocumentAPIView(APIView):
    permission_classes = [IsManagementAdmin]
    def post(self, request, project_id):
        return _call_legacy_view(legacy_views.land_project_generate_document_api, request, project_id)
```

HTTP 方法依据 `core/views.py` 上的装饰器：`documents_archive_api` / `document_download_api`
只有 `@staff_member_required`（支持 GET）；`link_kml_record_api`、`document_delete_api`、
`generate_document_api` 带 `@require_POST`（必须 POST）。

同时把这 5 个类名加入 `core/api/urls.py` 的 `from core.api.views import (...)`，
并把 `path('projects/...')` 全部改回 `*APIView.as_view()`（含新增的
`link-kml-record/`、`documents/archive/`、`documents/<int:document_id>/download/`、
`documents/<int:document_id>/delete/`、`documents/generate/`）。

**B. `core/api/views.py` 导入块冲突**：两侧合并即可（`import logging` + `concurrent.futures`
+ `SimpleNamespace` + `Path`）。

**C. `core/views.py`（7 块）**：离线侧新增的函数在在线侧**全部存在**
（对比 `53b1eee..HEAD` 与 `53b1eee..v1.2.12` 的 `^+def|^+class` 集合，离线独有项为 0），
在线侧是超集（+1671 行 vs 离线 +823 行）。→ **冲突块基本取在线版（v1.2.12）**，
但需逐块确认没有丢掉离线专有内容（例如 `_resolve_public_base_url` 里的
`http://127.0.0.1:8000` 兜底不应被替换成生产域名 `beichenhome.top:9081`）。

**D. `frontend/src/router/index.js`（2 块）**：需要**手工融合**，两侧都要：
- 保留离线 `import LoginView from '../views/Login.vue'`（IPC 登录窗）
  或按第 3 节建议改用 `system/auth/LoginView.vue`；
- 加入在线的 `AdminEntryView` + `system/admin` 路由（离线版 Django Admin 入口依赖它）；
- 保留 `system/data-management`、`system/about`、`system/ai-config`。

**E. `frontend/src/api/system/systemApi.js`**：取在线版（新增四普边界导入 + 数据同步
`exportDataSyncPackage` / `importDataSyncPackage` 等），离线侧该处为空。

**F. `static/frontend/**`（manifest.json、index.html、vendor-vue-*.js 的 rename/rename 冲突）**：
**不要手工解**。合并完成后统一执行 `cd frontend; npm run build` 覆盖产物，再
`git add static/frontend`。

**G. `db.sqlite3`（modify/delete）**：离线版已删除该文件（改用加密库）。
→ `git rm db.sqlite3`，并确认 `.gitignore` 覆盖 `*.sqlite3`。

**H. `.github/workflows/desktop-release.yml`（9 块）**：离线版在 v1.2.2 已**主动移除 macOS 打包**
（`71d8db4`），在线版又加回来了 macOS-arm64。→ 取离线版（HEAD）为主，
再挑拣在线版新增的 `Validate desktop runtime layout` / `Smoke test backend executable` 步骤
（这两步对防止"打包出不可用的包"很有价值）。

    不含 `frontend/src/utils/tianditu.js` 已实现的离线瓦片逻辑 → 离线地图必然空白。
    **任何前端改动后必须 `cd frontend; npm run build` 并提交 `static/frontend`，否则发布包不变。**


### 4.3 迁移文件必须重排（隐性炸弹）

```
HEAD (offline)                              v1.2.12 (online)
0024_rename_..._and_more (no-op)            0024_rename_..._and_more (no-op，内容相同)
0025_rename_..._and_more (11×RenameIndex)   ← 编号撞车 →
                                            0025_landuseprojectapproval_workflow_extra_fields
                                            0026_backfill_involves_kanerjing
                                            0027_heritagesite_body_boundary
                                            0028_sipu_import_job
                                            0029_land_project_kml_record
                                            0030_land_project_document
```

两侧 `0024` 内容一致（都是幂等 no-op），但 `0025` 编号冲突，合并后会出现**两个叶子节点**，
`manage.py migrate` 报冲突提示。

处理方案：把在线的 `0025..0030` 依次重命名为 `0026..0031`，并把
`0026_landuseprojectapproval_workflow_extra_fields` 的 `dependencies` 改为
`('core', '0025_rename_core_heritag_heritag_26948d_idx_core_herita_heritag_634100_idx_and_more')`，
形成单链。注意离线 `0025` 是 `RenameIndex`，若在线 `0026+` 又新建同名索引会二次冲突，
重排后必须跑 `manage.py migrate --plan` 与 `makemigrations --check --dry-run` 验证。

### 4.4 合并后强制验证清单

```bash
# 1) 语法/配置
python manage.py check
python manage.py makemigrations --check --dry-run   # 应输出 No changes detected
python manage.py migrate --plan

# 2) 加密库回归（v1.2.11 带回的测试，core/tests_sqlcipher.py 新增 120 行）
python manage.py test core.tests_sqlcipher

# 3) 前端必须重建并提交产物
cd frontend && npm ci && npm run build && cd .. && git add static/frontend

# 4) 首次启动端到端演练（关键！）
rm -rf data config            # 模拟全新安装
python manage.py sqlcipher_bootstrap
#   → 校验 data/database.db 为加密库、config/key.bin 生成、admin 账号用向导密码可登录
#   → 若第 3 节问题 1 未修，此处会发现只能用 test/test 登录

# 5) 打包冒烟
./scripts/build_desktop_runtime.ps1
cd frontend && npm run desktop:pack
```

## 5. 安全项（合并前必须处理）

`origin/master` 把以下敏感文件提交进了仓库，**合并会把它们带进离线包**：

- `beichenhome.top/1778466805/beichenhome.top.key`（**TLS 私钥**）、`fullchain.crt` 等
- `.env`（含 `DJANGO_SECRET_KEY`）
- `db.sqlite3`、`db.sqlite3.bak_20260303_234321`、`db.sqlite3.local_before_migrate_backup`（真实业务数据）
- `templates/admin/index.html.bak`

→ 合并前先在 `feat/online-v1.2.12` 上删除这些路径并追加一次清理提交；
私钥与 `SECRET_KEY` 应视为已泄露，需轮换。若历史也要清理，用 `git filter-repo`。

## 6. 回滚方式

```bash
git checkout offline
git reset --hard backup/offline-v1.2.4     # 回到止血前（v1.2.4）
git reset --hard v1.2.11                   # 回到阶段 1 完成态
git reset --hard 95e9eef                   # 回到阶段 2 合并前（Stage 1 全部修复）
```

## 7. 阶段 2 实际执行记录（2026-09-13 完成）

### 7.1 提交拓扑

| 项 | 值 |
|---|---|
| 合并提交 | `bfd9c67`（`offline` 当前 HEAD） |
| 父 1 | `95e9eef` — 离线 Stage 1 末端（真实登录链前端重建） |
| 父 2 | `66f6f51` — `feat/online-v1.2.12-clean`（净化后的在线线） |
| 在线原始头 | `fcdb456` / tag `v1.2.12` |
| merge-base | `53b1eee` |
| 变更规模 | 40 个文件（含 `static/frontend/**` 重建产物） |

Stage 1 的四个提交：`d9ac9a6`（Django 6.1 SQLCipher 兼容 + 静态检查 + Vite 瓦片代理 +
DEBUG/静态/鉴权解耦）、`202ef2b`（前端重建）、`d3856d1`（Electron 假登录改真实后端 JWT）、
`95e9eef`（登录链前端重建）。

### 7.2 净化分支 `feat/online-v1.2.12-clean`

从 `v1.2.12` 切出，用一次清理提交（`66f6f51`）从跟踪中移除：

- `.env`（含 `DJANGO_SECRET_KEY`）
- `beichenhome.top/1778466805/` 下 TLS 私钥与证书（`.key` / `.crt` / `fullchain.crt` / `issuer_certificate.crt`）
- `db.sqlite3` 及两个 `.bak` / `local_before_migrate_backup`
- `config/key.bin`、`data/database.db` ← **最高危**：在线新增，若合入会随离线安装包分发
- `templates/admin/index.html.bak`

> ⚠️ **这只是"新提交中删除"，原始在线历史仍含全部敏感文件。**
> TLS 私钥与 `DJANGO_SECRET_KEY` 必须视为已泄露并轮换；若要对外分享在线历史，
> 需 `git filter-repo` 重写。详见第 7.6 节。

### 7.3 迁移重排（已落地）

在线 `0025..0030` → `0026..0031`，并把 `0026` 的 dependency 指向离线 `0025`，
形成单一主干：

```
core.0024_rename_..._and_more
  └─ core.0025_rename_..._and_more            (offline, 11×RenameIndex)
       └─ core.0026_landuseprojectapproval_workflow_extra_fields
            └─ core.0027_backfill_involves_kanerjing
                 └─ core.0028_heritagesite_body_boundary
                      └─ core.0029_sipu_import_job
                           └─ core.0030_land_project_kml_record
                                └─ core.0031_land_project_document
```

验证：`migrate --plan` 单链无分叉；`makemigrations --check --dry-run` → `No changes detected`。
第 4.3 节担心的"离线 `0025` 是 RenameIndex、在线 `0026+` 新建同名索引二次冲突"未发生。

### 7.4 冲突解决实际落点

第 4.2 节的 A–H 方案全部按原计划执行，其中三处与预案有出入：

| 文件 | 预案 | 实际 |
|---|---|---|
| `core/api/views.py` | 补 5 个包装类 | ✅ 照做，`smoke_project_api.py` 已验证 |
| `core/views.py` | 取在线算法超集 | ✅ 并复核离线专用函数全部保留 |
| `core/land_project_services.py` | 取在线版 | ✅ 额外清除自动合并产生的**重复常量** |
| `router/index.js` | 保留离线 Login + 在线路由 | ✅ 并恢复 `AdminEntryView` → `/system/admin` |
| `systemApi.js` | 取在线版 | ✅ 额外**恢复 `enterDjangoAdmin()`**（在线版没有） |
| `AppLayout.vue` | 合并菜单 | ✅ 额外把 `DJANGO_ADMIN_URL` 重定义为 `/system/admin`，消除未定义常量与生产 URL 泄漏 |
| `ProjectDetailView.vue` | 手工融合 | ⚠️ **改为整体取在线版**：后端已返回在线 `guide`/`todos`/`documents` 结构，离线 step-nav 属不兼容死代码，手工融合只会留下永不执行的分支 |
| `DataManagementView.vue` | add/add 择一 | ⚠️ **手工三方合并**：离线 CSV 导入 + 桌面备份恢复 与在线 DataSyncPanel + Sipu 边界导入属互补功能，全部保留 |
| `desktop-release.yml` | 离线为主 + 挑拣在线步骤 | ✅ 保留无 macOS 矩阵，移除在线引入的 macOS 死步骤，保留 `Validate desktop runtime layout` / `Smoke test backend executable` |
| `core/tests.py` | — | ⚠️ **计划外**：合并后 `heritage_classification_stats_api` 改用 `IsManagementAdmin`，测试用户需加入「管理员」组 |

`system/urls.py`、`system/views.py`、`requirements.txt` 未列入原冲突清单，但自动合并结果需复核：
在线新增（`DeepSeekConfigAPIView`、`_mask_secret`、`openai>=1.35.0`）与离线新增
（`_ensure_system_roles`、`_normalize_admin_only_group_ids`、`SystemPublicConfigAPIView`、
`keyring`、`cryptography`、`waitress`）**双方均完整保留**，无覆盖丢失。

### 7.5 验证矩阵（全部在合并后重跑）

| 验证项 | 命令 | 结果 |
|---|---|---|
| 配置检查 | `manage.py check`（普通 + `HERITAGE_DESKTOP_MODE=1`） | 0 issues |
| 迁移一致性 | `makemigrations --check --dry-run` | No changes detected |
| 迁移链 | `migrate --plan` | 单主干 0024→0031 |
| 单元/加密回归 | `manage.py test core` | 15 passed |
| 首次启动端到端 | `scripts/dev/e2e_first_run.py` | 加密库 + `key.bin` + 角色组 + 向导密码 OK；`test/test` 登录 = False；错误密钥读取被拒 |
| 越权审计 | `scripts/dev/audit_debug_bypass.py` | 13/13 |
| 桌面登录链 | `scripts/dev/smoke_desktop_login.py` | 12/12 |
| HTTP 冒烟 | `scripts/dev/smoke_http.py` | 10/10 |
| Vite 开发代理 | `scripts/dev/smoke_vite_dev.py` | 4/4 |
| **在线端点 JWT 可用性** | `scripts/dev/smoke_project_api.py`（本次新增） | 11/11 |
| Electron IPC 契约 | 脚本比对 main.cjs / preload.cjs / 调用方 | 10 通道双向匹配，无后门残留 |
| 前端产物新鲜度 | 源文件 mtime vs `static/frontend/index.html` | 0 个更新源文件 |

`smoke_project_api.py` 是本次为验证第 4.2-A 节而新增的常驻脚本，覆盖：
`projects/create/`、`documents/archive/`、`controls/`、项目详情、`link-kml-record/`、
`documents/generate/`、`data-sync/options/`、`sipu-boundary-import/status/` 在 **JWT Bearer**
下不被 401/403 拦截且路由确已注册（区分业务层 JSON 404 与 Django 路由 HTML 404），
匿名访问仍为 401。

> 踩坑记录：该脚本首版把 `land_project_create_api` 的返回当成嵌套 `data.id` 解析，
> 实际是**顶层** `project_id`（`core/views.py:2229`）。pid 取空后所有断言打在空 URL 上得到
> 404，而"非 403 即通过"的判据把这种假阳性全放过了。现已改为 pid 取不到即硬失败，
> 并校验 content-type。

### 7.6 遗留安全与运维事项

1. **轮换密钥**：`beichenhome.top` TLS 私钥、`DJANGO_SECRET_KEY`、历史中出现过的 DB 凭据与管理员口令。
2. **历史清理决策**：`feat/online-v1.2.12-clean` 只保证"新提交无敏感文件"，
   `feat/online-v1.2.12` / `origin/master` / `v1.2.12` 标签的历史 blob 仍含私钥。
   对外分享前需 `git filter-repo` 或仅推送净化分支与 `offline`。
3. **Electron GUI 无法在无头环境验证**，仍需人工桌面冒烟（见第 7.7 节）。
4. 第 3 节问题 4（向导密码落盘时序）、问题 9（备份不含 `key.bin` 与 uploads）**尚未处理**，
   属独立于本次合并的离线缺陷。

### 7.7 待人工执行的桌面冒烟

```powershell
powershell -File scripts\start_offline.ps1 -Mode desktop
```

逐项确认：首次向导建加密库与 `key.bin`；向导设置的口令可登录且 `test/test` 不可登录；
JWT 落 localStorage 并被 axios 携带；离线天地图瓦片出图；`/system/admin` 可进 Django Admin；
数据管理页四组功能并存（CSV 导入 / 桌面备份恢复 / DataSyncPanel / 四普边界导入）；
退出登录回到登录窗并清 token。

