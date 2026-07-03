# heritage_system 离线桌面版（Electron）打包说明

本方案目标：产出可直接运行的桌面可执行程序，终端用户机器不需要额外安装 Python 或 Node/Vue 开发环境。

## 1. 已接入内容

- 前端工程已接入 Electron 主进程与预加载：`frontend/electron/`
- 首次启动初始化向导：自动检测数据目录可写性、日志路径可写性、后端端口占用并保存本机配置
- 初始化向导支持可视化目录选择：可点击“选择目录”分别设置数据目录与日志目录，并即时重跑检测
- Electron 开发联调命令：`npm run desktop:dev`
- Electron 打包命令（Windows portable）：`npm run desktop:pack`
- 后端可执行构建入口：`desktop_backend.py`
- 一键构建后端运行时脚本：
  - Windows: `scripts/build_desktop_runtime.ps1`
  - macOS/Linux: `scripts/build_desktop_runtime.sh`

## 2. 目录约定

Electron 打包前，需要先生成后端运行时目录：

- `desktop_runtime/backend/heritage_backend(.exe)`
- `desktop_runtime/backend/db.sqlite3`
- `desktop_runtime/backend/static/`
- `desktop_runtime/backend/templates/`
- `desktop_runtime/backend/media/`（可选）

`frontend/package.json` 已配置 `extraResources` 自动把该目录打入安装包。

## 3. 本地联调（开发模式）

在项目根目录先准备 Python 依赖，然后执行：

```bash
cd frontend
npm install
npm run desktop:dev
```

该命令会并行拉起：

- Vite：`http://127.0.0.1:5173`
- Django：`http://127.0.0.1:18000`
- Electron 窗口：加载 Vite 页面

## 4. 生成后端运行时

### Windows

```powershell
.\scripts\build_desktop_runtime.ps1
```

### macOS/Linux

```bash
chmod +x ./scripts/build_desktop_runtime.sh
./scripts/build_desktop_runtime.sh
```

## 5. 打包 Electron 可执行文件（Windows Portable）

```bash
cd frontend
npm install
npm run build
npm run desktop:pack
```

输出目录：`frontend/dist-electron/`

## 6. 启动逻辑

- 开发模式：Electron 主进程启动本地 Python Django。
- 打包模式：Electron 主进程启动 `resources/backend/heritage_backend(.exe)`。
- 首次启动（非开发模式）会弹出初始化向导，完成检测与确认后再启动后端。
- 健康检查地址：`/api/v1/health/`。
- 后端日志默认写入初始化向导确认的日志目录，文件名 `backend.log`。

## 7. 注意事项

- 当前后端默认端口为 `18000`，可用环境变量 `BACKEND_PORT` 覆盖。
- 首次启动会自动执行 `migrate --noinput`。
- 若地图瓦片依赖外网服务，离线环境下底图可能不显示，但业务功能可用。
- 如果需要多平台发行（macOS dmg / Linux AppImage），可在 `frontend/package.json` 的 electron-builder 目标中追加。
- 运行中的桌面程序可在菜单“工具 -> 重置初始化向导”一键重置首启状态，程序会自动重启并重新执行初始化检测。

## 8. GitHub Actions 自动发版（Tag触发）

仓库已新增工作流：`.github/workflows/desktop-release.yml`

触发规则：

- 推送 tag（匹配 `v*`）时自动执行。
- 也支持手动触发（`workflow_dispatch`）。

自动构建平台与产物：

- Windows x64：
  - NSIS 安装包（`.exe`）
  - Portable 便携版（`.exe`）
- macOS Apple Silicon（arm64）：
  - `.dmg`
  - `mac-arm64.zip`
- Linux：
  - amd64 AppImage
  - arm64 AppImage

发布行为：

- 所有平台构建完成后，工作流会自动创建/更新对应 GitHub Release。
- 构建产物会自动上传到 Release Assets。

Tag 发布示例：

```bash
git tag v2.2.0
git push origin v2.2.0
```
