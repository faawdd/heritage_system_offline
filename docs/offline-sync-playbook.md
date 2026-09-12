# 离线版（offline 分支）同步与修复手册

> 生成时间：2026-09-12。记录 `offline` 分支与在线版（`origin/master` / `v1.2.12`）的分叉现状、
> 已完成的止血修复，以及尚未执行的阶段 2 合并方案。

## 1. 仓库拓扑现状

| 引用 | commit | 日期 | 含义 |
|---|---|---|---|
| `offline`（当前 HEAD） | `f62028d` / tag `v1.2.11` | 2026-08-04 | **已完成阶段 1 止血** |
| `backup/offline-v1.2.4` | `0ff901b` / tag `v1.2.4` | 2026-08-03 | 止血前原始状态（回滚点） |
| `fix/offline-v1.2.11` | `f62028d` | 2026-08-04 | 保护分支，防止悬空标签丢失 |
| `feat/online-v1.2.12` | `fcdb456` | 2026-09-02 | 在线版新功能线（含 `origin/master` 全部提交） |
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

## 4. 阶段 2（未执行）：合并 v1.2.12 在线版功能

### 4.1 为什么被中止

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
git reset --hard v1.2.11                   # 回到当前已验证状态
```

