<div align="center">

<img src="logo.png" alt="文物综合管理平台离线版" width="120">

# 文物综合管理平台 · 离线版

**不可移动文物保护管理桌面客户端 —— 安装即用、数据本地存储、断网也能工作**

[![GitHub Release](https://img.shields.io/github/v/release/faawdd/heritage_system_offline?style=for-the-badge&logo=github&label=最新版本&color=2ea44f)](https://github.com/faawdd/heritage_system_offline/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/faawdd/heritage_system_offline/total?style=for-the-badge&logo=github&label=下载量&color=blue)](https://github.com/faawdd/heritage_system_offline/releases)
[![Build](https://img.shields.io/github/actions/workflow/status/faawdd/heritage_system_offline/desktop-release.yml?style=for-the-badge&logo=githubactions&logoColor=white&label=构建)](https://github.com/faawdd/heritage_system_offline/actions/workflows/desktop-release.yml)
[![License](https://img.shields.io/badge/License-Apache_2.0-orange?style=for-the-badge&logo=apache&logoColor=white)](https://www.apache.org/licenses/LICENSE-2.0)

[![Windows](https://img.shields.io/badge/Windows-x64-0078D6?style=flat-square&logo=windows11&logoColor=white)](#-下载安装)
[![macOS](https://img.shields.io/badge/macOS-Apple_Silicon-000000?style=flat-square&logo=apple&logoColor=white)](#-下载安装)
[![Linux](https://img.shields.io/badge/Linux-x64_%7C_ARM64-FCC624?style=flat-square&logo=linux&logoColor=black)](#-下载安装)

[![Electron](https://img.shields.io/badge/Electron-32-47848F?style=flat-square&logo=electron&logoColor=white)](https://www.electronjs.org/)
[![Vue](https://img.shields.io/badge/Vue-3-4FC08D?style=flat-square&logo=vuedotjs&logoColor=white)](https://vuejs.org/)
[![Vite](https://img.shields.io/badge/Vite-5-646CFF?style=flat-square&logo=vite&logoColor=white)](https://vitejs.dev/)
[![Element Plus](https://img.shields.io/badge/Element_Plus-2-409EFF?style=flat-square&logo=element&logoColor=white)](https://element-plus.org/)
[![OpenLayers](https://img.shields.io/badge/OpenLayers-10-1F6B75?style=flat-square&logo=openlayers&logoColor=white)](https://openlayers.org/)
[![ECharts](https://img.shields.io/badge/ECharts-5-AA344D?style=flat-square&logo=apacheecharts&logoColor=white)](https://echarts.apache.org/)
[![Django](https://img.shields.io/badge/Django-5%2B-092E20?style=flat-square&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![SQLite](https://img.shields.io/badge/SQLite-本地数据库-003B57?style=flat-square&logo=sqlite&logoColor=white)](https://www.sqlite.org/)

[下载安装](#-下载安装) · [功能特性](#-功能特性) · [快速上手](#-快速上手) · [本地构建](#-本地开发与构建) · [文档](#-文档)

</div>

---

## ✨ 简介

**文物综合管理平台离线版**面向文物保护单位、文物管理部门和现场看护人员，把在线版的核心业务能力打包为跨平台桌面应用。
应用内置本地服务与 SQLite 数据库，**无需另行安装 Python 或数据库**；数据库、上传文件、日志、备份与地图切片全部保存在本机用户数据目录，不依赖在线服务器。

> 离线版不预设任何省、市、县名单，可在全国范围部署使用。首次启动时可填写地区前缀，系统名称会自动组合为“{地区前缀}文物综合管理平台”。

## 🚀 功能特性

| 模块 | 能力 |
| --- | --- |
| 🏛️ **文物档案** | 不可移动文物档案登记、详情查看、分类统计，登记表预览与 Word 导出 |
| 🗺️ **文物一张图** | 基于 OpenLayers 的文物点、保护范围与建设控制地带展示，KML/KMZ 叠加核查，地图测距 |
| 🧭 **离线底图** | 导入 `.mbtiles` 或 XYZ/TMS `.zip` 瓦片，与天地图在线底图一键切换 |
| 📐 **GIS 工具** | KML/KMZ、OVKML、DXF 转换，冲突分析，边界导出，投影坐标导入（需指定中央经线） |
| 🔍 **巡查看护** | 看护员巡查记录上报与追溯，现场照片、位置与问题描述 |
| 🏗️ **基建项目** | 涉文物建设项目登记、县→市→省报审流程、空间安全核验与材料归档 |
| 📥 **四普数据** | 导入完整登记档案，按四普编号关联业务文物点 |
| 📊 **数据看板** | 文物总量、类别、乡镇分布等可视化统计 |
| 🛡️ **系统管理** | 用户、中文用户组与权限条目、统一日志中心（按用户组限定日志可见范围） |

### 🔐 账户安全

- 首次登录必须修改初始密码，并设置 **3 个不同的密码保护问题**（答案仅以哈希形式保存）。
- 连续输错密码 **5 次等待 2 分钟**，累计 **10 次锁定账户**，只能通过保护问题重置解锁。
- 忘记密码可在登录页通过保护问题自助重置。
- 桌面模式仅允许本机访问内置服务。

## 📦 下载安装

前往 **[GitHub Releases](https://github.com/faawdd/heritage_system_offline/releases/latest)** 下载对应平台的安装包：

| 平台 | 架构 | 安装包 |
| --- | --- | --- |
| <img src="https://img.shields.io/badge/-Windows-0078D6?logo=windows11&logoColor=white" alt="Windows"> | x64 | `.exe`（NSIS 安装程序） |
| <img src="https://img.shields.io/badge/-macOS-000000?logo=apple&logoColor=white" alt="macOS"> | Apple 芯片（M 系列） | `.dmg` / `.zip` |
| <img src="https://img.shields.io/badge/-Linux-FCC624?logo=linux&logoColor=black" alt="Linux"> | x86_64 / ARM64 | `.AppImage` / `.deb` / `.rpm` |

### 系统要求

| 项目 | 要求 |
| --- | --- |
| 操作系统 | Windows 10/11（64 位）、macOS 11+（Apple 芯片）、较新的 64 位 Linux 发行版 |
| 内存 | 最低 4 GB，推荐 8 GB 及以上 |
| 磁盘 | 安装约 1 GB，建议预留 5 GB 以上 |
| 网络 | 日常使用无需联网；在线底图、四普导入、AI 等外部服务需联网 |

> [!NOTE]
> 应用在本机 `127.0.0.1` 的 18000 起始端口运行内置服务，请勿被安全软件拦截。

<details>
<summary><b>🍎 macOS 提示“文件已损坏”怎么办？</b></summary>

当前 macOS 安装包未使用 Apple Developer ID 签名和公证，Gatekeeper 可能拦截。**确认安装包来自本仓库 Release 后**，将应用拖入“应用程序”目录并执行：

```sh
xattr -dr com.apple.quarantine "/Applications/文物综合管理平台（离线版）.app"
```

然后从“应用程序”重新打开即可。请勿对来源不明的应用执行此命令。

</details>

## 🧑‍💻 快速上手

1. **安装并启动**应用，首次启动向导中填写地区前缀（可留空），并为默认管理员设置 3 个保护问题。
2. 使用初始账户 `admin` / `admin` 登录，**按提示修改密码**并重新确认保护问题，初始密码随即失效。
3. 在“系统管理”中创建用户组与用户，分配权限。
4. （可选）在“系统管理 → 离线地图切片”导入底图，即可完全断网使用地图。

> [!IMPORTANT]
> 升级安装会自动识别已有数据并执行数据库迁移，不会重复弹出首次配置向导。卸载清理会删除本机数据库、上传文件、备份、日志和配置，**无法撤销**，请提前备份。

## 🔧 本地开发与构建

**环境要求**：Python 3.11、Node.js 20。

```bash
# 1. 前端依赖与构建
npm --prefix frontend ci
npm --prefix frontend run build

# 2. 构建内置后端运行时（PyInstaller）
bash scripts/build_desktop_runtime.sh          # Windows 使用 scripts/build_desktop_runtime.ps1

# 3. 打包桌面应用
cd frontend
npx electron-builder --publish never --linux AppImage deb rpm --x64
# npx electron-builder --publish never --win nsis --x64
# npx electron-builder --publish never --mac dmg zip --arm64
```

### 🤖 自动发布

推送 `v*` 标签即会触发 [Desktop Multi-Platform Release](.github/workflows/desktop-release.yml) 工作流，自动构建 Windows x64、macOS arm64、Linux x64/arm64 安装包，经过运行时冒烟测试后发布到 GitHub Releases：

```bash
git tag v2.2.1
git push heritage v2.2.1
```

## 🧱 技术架构

```text
┌──────────────────────────── Electron 桌面外壳 ────────────────────────────┐
│  Vue 3 · Vite · Pinia · Vue Router · Element Plus · ECharts · OpenLayers   │
│                              │  HTTP（仅 127.0.0.1）                        │
│  内置后端：Django 5+ · DRF · SimpleJWT · Waitress（PyInstaller 打包）       │
│                              │                                             │
│  本地存储：SQLite · 媒体文件 · 日志 · 备份 · 地图切片（Electron userData） │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 📚 文档

| 文档 | 说明 |
| --- | --- |
| [离线桌面版说明](docs/offline-desktop.md) | 首次启动、全国通用配置、地图切片、构建、卸载与离线边界 |
| [项目文档整合](docs/项目文档整合.md) | 开发、部署、升级与功能索引 |
| [前端说明](frontend/README.md) | Vue 前端开发、构建与模块说明 |
| [报告定期生成与 PDF 导出](docs/报告定期生成与PDF导出指南.md) | 报告自动生成与导出 |

## 🌿 分支说明

| 分支 | 用途 | 托管位置 |
| --- | --- | --- |
| `offline2` | 离线桌面版（本仓库默认分支） | GitHub |
| `master` | 在线版主线 | Gitee |

## 🔒 安全提示

- 请勿将 `.env`、数据库、上传文件、备份、密钥或包含明文保护问题答案的临时 JSON 提交到仓库。
- 批量创建看护员时使用的 `--security-questions-file` 含明文答案，用后请立即安全删除。

## 📄 许可证

本项目基于 [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0) 开源。

<div align="center">

**鄯善文保 · 文物综合管理平台离线版**

如果这个项目对你有帮助，欢迎点一个 ⭐ Star

[![Stars](https://img.shields.io/github/stars/faawdd/heritage_system_offline?style=social)](https://github.com/faawdd/heritage_system_offline/stargazers)

</div>
