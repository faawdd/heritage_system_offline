# 基层文物管理系统（离线版）

基层文物管理系统（离线版）是一个面向基层文保场景的离线桌面系统，支持文物台账管理、巡查记录、项目管理和 KML 地图工具，强调本地运行与私有数据留存。

## 核心特性

- 离线桌面运行：Electron 封装，用户端无需单独安装 Python/Node 开发环境
- 首次启动引导：自动检测并配置数据目录、日志目录、端口（支持手动指定）
- 数据与程序分离：
  - app：程序代码与运行组件
  - data：用户私有数据（数据库、上传文件）
  - config：本地配置
- 自动建库：首次启动若无数据库，自动执行迁移并初始化
- 多平台发布：Windows/macOS/Linux 自动构建与 Release 上传

## 技术栈

- 前端：Vue 3 + Vite + Element Plus
- 后端：Django + DRF
- 桌面端：Electron + electron-builder

## 目录结构（关键）

```text
heritage_system/
  frontend/                # Vue + Electron 前端工程
  heritage_system/         # Django 配置
  core/                    # 核心业务
  system/                  # 系统管理模块
  scripts/                 # 运行时构建脚本
  desktop_backend.py       # 桌面后端启动入口
```

运行时目录（打包后）：

```text
runtime/
  app/                     # 程序文件
  data/                    # 用户私有数据
  config/                  # 用户配置
```

## 本地开发

### 1. 后端

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

## 桌面打包

### 1. 构建后端运行时

- macOS/Linux：

```bash
chmod +x ./scripts/build_desktop_runtime.sh
./scripts/build_desktop_runtime.sh
```

- Windows：

```powershell
.\scripts\build_desktop_runtime.ps1
```

### 2. 打包桌面端

```bash
cd frontend
npm install
npm run build
npm run desktop:pack
```

## GitHub Actions 自动发布

仓库已配置 Tag 触发自动构建与发布：

- 触发方式：推送 `v*` 标签
- 产物：
  - Windows：安装版（NSIS）+ 便携版（Portable）
  - macOS：arm64（Apple Silicon）
  - Linux：AppImage（amd64 + arm64）

示例：

```bash
git tag v1.0.0
git push heritage v1.0.0
```

## 数据与隐私说明

- 数据库、日志、用户上传文件等私有数据不应提交到仓库
- 请保持 `.gitignore` 中的数据与配置忽略规则有效

## 许可证

如需商用或二次分发，请按项目实际授权策略执行。
