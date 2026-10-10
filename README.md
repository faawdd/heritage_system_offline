# 文物综合管理平台

面向文物保护单位、管理部门和现场看护人员的综合管理平台，提供文物档案、地图展示、巡查记录、项目管理、GIS/KML 分析、移动端接口以及离线桌面版。

> 当前文档以 `master` 与 `offline2` 两个分支的已提交 Markdown 为依据整理。详细的统一说明请阅读：[项目文档整合](docs/项目文档整合.md)。

## 功能概览

- **文物档案管理**：维护不可移动文物完整档案、基础信息、照片和保护范围。
- **文物一张图**：基于 OpenLayers 展示文物点、边界、KML/KMZ 叠加图层和统计信息。
- **巡查管理**：支持看护员现场提交巡查记录、照片和定位信息。
- **项目管理**：管理用地项目、审批流程、项目审计和相关导出文件。
- **四普数据导入**：导入完整登记档案，并按四普编号关联业务文物点，避免仅按名称合并。
- **GIS 工具**：支持 KML/KMZ、OVKML 和 DXF 转换、冲突分析、边界导出及地图测距。
- **系统管理**：提供用户、用户组、权限、登录日志、操作日志和审计日志管理。
- **移动端接口**：提供 `/app-api` FastAPI 网关，供巡查 App 或其他移动客户端使用。
- **离线桌面版**：使用本机 SQLite 保存业务数据、媒体、日志和地图切片，可构建 Windows、macOS 和 Linux 安装包。

## 技术栈

| 层次 | 技术 |
| --- | --- |
| 服务端 | Django 5、Django REST Framework、FastAPI、Uvicorn |
| 前端 | Vue 3、Vite、Pinia、Vue Router、Element Plus、ECharts、OpenLayers |
| 数据处理 | SQLite、Pandas、NumPy、GeoPandas 相关工具、PyProj、Rasterio、ezdxf |
| 文档与导出 | python-docx、docxtpl、Pillow |
| 桌面端 | Electron、PyInstaller、Waitress |

## 快速开始

### 1. 准备环境

建议使用 Python 3.10 及以上版本，并准备 Node.js 和 npm。

```bash
git clone <repository-url>
cd heritage_system
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows PowerShell 可使用：

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. 初始化数据库并启动 Django

```bash
python manage.py migrate
python manage.py runserver
```

默认访问地址为 `http://127.0.0.1:8000/`。生产环境部署前请先备份数据库，并阅读 [统一文档中的部署与升级章节](docs/项目文档整合.md#部署与升级)。

### 3. 启动前端开发服务器

```bash
npm --prefix frontend ci
npm --prefix frontend run dev
```

前端开发服务器默认地址为 `http://localhost:5173/`，API 代理目标为本机后端服务。构建静态资源：

```bash
npm --prefix frontend run build
```

### 4. 启动 FastAPI 移动端网关（按需）

```bash
uvicorn fastapi_server.main:app --host 127.0.0.1 --port 8000
```

生产环境通常由 Django、FastAPI 和 Nginx 共同部署；完整的 systemd、Nginx 和健康检查步骤见 [统一文档](docs/项目文档整合.md#fastapi-移动端网关)。

## 离线桌面版

离线版把数据库、媒体、日志、备份和地图切片保存到 Electron `userData` 目录，不写入安装目录。首次启动会完成本地配置和管理员安全问题设置。

```bash
npm --prefix frontend ci
npm --prefix frontend run build
bash scripts/build_desktop_runtime.sh
cd frontend
npx electron-builder --publish never --linux AppImage deb rpm --x64
```

Windows、macOS 和 ARM Linux 的构建方式、离线地图导入、卸载数据清理和 macOS 未签名应用处理，请阅读 [离线桌面版说明](docs/offline-desktop.md)。

## 数据与安全

- 不要把 `.env`、数据库、上传文件、备份、包含明文安全问题答案的临时 JSON 或密钥文件提交到仓库。
- 生产部署前备份数据库，在项目根目录执行迁移，并确保 Django 与 FastAPI 使用同一个数据库。
- Web 登录使用验证码、账号锁定和 IP 限速；App 登录共享账号锁定和限速策略。
- 反向代理场景下只信任实际代理地址，不要将 Uvicorn 的 `forwarded-allow-ips` 配置为 `*`。
- 离线桌面版初始管理员密码仅用于首次登录，首次登录后必须修改密码并重新确认安全问题。

## 文档

| 文档 | 说明 |
| --- | --- |
| [项目文档整合](docs/项目文档整合.md) | 两个分支文档核对后的统一说明、开发、部署、升级与功能索引 |
| [前端说明](frontend/README.md) | Vue 前端开发、构建和迁移模块说明 |
| [离线桌面版](docs/offline-desktop.md) | 桌面运行、离线地图、构建和卸载说明 |
| [FastAPI 生产部署](fastapi_server/deploy/DEPLOY_PROD.md) | FastAPI、systemd 和 Nginx 部署步骤 |
| [登录问题诊断](LOGIN_FIX_GUIDE.md) | 数据库迁移和用户档案修复 |
| [服务器登录修复清单](SERVER_LOGIN_FIX.md) | 登录、日志、权限和故障排查 |
| [服务器快速修复](SERVER_QUICK_FIX.md) | 服务器登录故障的快速处理流程 |

迁移分析和阶段性实施记录统一收录在 [`docs/migration/`](docs/migration/)。

## 版本与分支

- `master`：在线版主线。
- `offline2`：离线桌面版及其配套能力。
- 分支间存在功能差异时，以实际代码、迁移文件和 [项目文档整合](docs/项目文档整合.md) 中的边界说明为准。

## 许可证

请以仓库中的许可证文件及项目维护者发布的授权说明为准。
