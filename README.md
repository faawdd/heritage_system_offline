<div align="center">

<img src="./logo.png" alt="基层文物管理系统 Logo" width="108" />

# 基层文物管理系统（离线版）

面向基层文保业务的离线桌面系统，聚焦本地运行、数据私有留存与跨平台发布。

![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-2563EB)
![Frontend](https://img.shields.io/badge/Frontend-Vue%203%20%2B%20Vite-0F766E)
![Backend](https://img.shields.io/badge/Backend-Django%20%2B%20DRF-166534)
![Desktop](https://img.shields.io/badge/Desktop-Electron-334155)
![Architecture](https://img.shields.io/badge/Architecture-Offline%20First-B45309)

</div>

## 目录

- [基层文物管理系统（离线版）](#基层文物管理系统离线版)
  - [目录](#目录)
  - [项目亮点](#项目亮点)
  - [技术栈](#技术栈)
  - [目录结构](#目录结构)
  - [快速开始](#快速开始)
    - [1. 后端启动](#1-后端启动)
    - [2. 前端启动](#2-前端启动)
  - [桌面打包](#桌面打包)
    - [1. 构建后端运行时](#1-构建后端运行时)
    - [2. 打包桌面客户端](#2-打包桌面客户端)
  - [自动发布](#自动发布)
  - [数据与隐私](#数据与隐私)
  - [管理员密码恢复](#管理员密码恢复)
  - [版权信息](#版权信息)
  - [许可证](#许可证)

## 项目亮点

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

## 目录结构

```text
heritage_system/
  frontend/                # Vue + Electron 前端工程
  heritage_system/         # Django 配置
  core/                    # 核心业务
  system/                  # 系统管理模块
  scripts/                 # 运行时构建脚本
  desktop_backend.py       # 桌面后端启动入口
```

打包后运行时目录：

```text
runtime/
  app/                     # 程序文件
  data/                    # 用户私有数据
  config/                  # 用户配置
```

## 快速开始

### 1. 后端启动

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

### 2. 前端启动

```bash
cd frontend
npm install
npm run dev
```

## 桌面打包

### 1. 构建后端运行时

macOS/Linux：

```bash
chmod +x ./scripts/build_desktop_runtime.sh
./scripts/build_desktop_runtime.sh
```

Windows：

```powershell
.\scripts\build_desktop_runtime.ps1
```

### 2. 打包桌面客户端

```bash
cd frontend
npm install
npm run build
npm run desktop:pack
```

应用图标使用根目录 logo.png，并在 electron-builder 配置中统一到 Windows/macOS/Linux。

## 自动发布

仓库已配置 Tag 触发自动构建与发布。

- 触发方式：推送 v* 标签
- 产物：
  - Windows：安装版（NSIS）+ 便携版（Portable）
  - macOS：arm64（Apple Silicon）
  - Linux：AppImage（amd64 + arm64）

示例：

```bash
git tag v1.0.0
git push heritage v1.0.0
```

## 数据与隐私

- 数据库、日志、用户上传文件等私有数据不应提交到仓库
- 请保持 .gitignore 中的数据与配置忽略规则有效

## 管理员密码恢复

如果忘记超级管理员密码，可直接使用管理命令或离线启动脚本重置。

```bash
python manage.py reset_super_admin_password --username admin --password NewPassword123 --create-if-missing
```

离线启动脚本也支持同样的重置参数：

```bash
./scripts/start_offline.sh --super-admin-username admin --super-admin-password NewPassword123 --super-admin-create-if-missing
```

打包后的桌面后端还支持通过环境变量强制重置：

```bash
HERITAGE_FORCE_RESET_SUPER_ADMIN_PASSWORD=1 HERITAGE_BOOTSTRAP_ADMIN_PASSWORD=NewPassword123
```

## 离线地图瓦片（开发阶段准备）

为避免 GitHub Actions 在发布阶段在线下载天地图瓦片导致卡住，离线瓦片改为开发阶段预下载并提交到仓库。

执行脚本（macOS/Linux）：

```bash
chmod +x ./scripts/refresh_tianditu_tiles.sh
./scripts/refresh_tianditu_tiles.sh --commit --push
```

说明：

- 该脚本会调用 `scripts/prefetch_tianditu_tiles.py` 下载吐鲁番范围瓦片到 `static/tiles/tianditu`
- `--commit` 会自动 `git add` 并生成提交
- `--push` 会将当前分支推送到默认远端
- 可通过 `TDT_TK` 或 `VITE_TDT_TK` 环境变量覆盖天地图 key

发布流程现在会在 CI 中校验 `static/tiles/tianditu` 是否已存在且非空；若不存在会直接失败，避免在线下载。

## 版权信息

- 版权所有：北辰
- 作者：北辰
- 联系邮箱：1443469207@qq.com
- 联系电话：13899665458

## macOS 安装后提示“已损坏，无法打开”

该提示通常与 Gatekeeper 隔离属性或未公证安装包有关，不代表安装包内容损坏。可按以下步骤修复：

1. 执行一键修复脚本（推荐）

```bash
chmod +x ./scripts/macos_fix_damaged_app.sh
./scripts/macos_fix_damaged_app.sh "/Applications/基层文物管理系统（离线版）.app"
```

2. 手工执行（等效）

```bash
xattr -rd com.apple.quarantine "/Applications/基层文物管理系统（离线版）.app"
codesign --force --deep --sign - "/Applications/基层文物管理系统（离线版）.app"
```

3. 若仍被拦截，可在“系统设置 -> 隐私与安全性”中允许该应用后再次打开。

长期方案建议：发布版本接入 Apple Developer 签名与 notarization（公证），可从源头避免该提示。

## 许可证

如需商用或二次分发，请按项目实际授权策略执行。
