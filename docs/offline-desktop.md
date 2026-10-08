# 离线桌面版

本分支以在线版 Django 模型和迁移为业务数据基线。桌面运行时使用本机 SQLite 数据库；数据库、媒体、日志、备份、DEM 缓存和地图切片保存在 Electron `userData` 目录，不写入应用安装目录。

## 首次启动

首次打开桌面应用时可填写地区前缀；留空时系统名称为“文物综合管理平台”，填写后自动组合为“{地区前缀}文物综合管理平台”。数据库迁移完成后，仅在尚无活动超级管理员的数据库中创建 `admin` 账户，初始密码为 `admin`。首次登录必须修改密码；修改成功后初始密码失效。请勿将初始口令作为日常口令使用。

## 离线地图

系统管理中的“离线地图切片”支持导入：

- QGIS/兼容工具导出的 `.mbtiles` 栅格瓦片数据库；
- 按 `z/x/y.png`、`z/x/y.jpg` 或 `z/x/y.webp` 组织的 XYZ/TMS `.zip`，导入时选择行号方案。

瓦片集写入本机数据目录的 `map-tiles` 子目录。可在管理页选择默认底图；桌面地图不会在没有本地瓦片时回退到天地图在线服务。MBTiles 元数据中的范围可用于地图预览定位。

## 本机开发和构建

```sh
npm --prefix frontend ci
npm --prefix frontend run build
bash scripts/build_desktop_runtime.sh
cd frontend && npx electron-builder --publish never --mac dmg zip --arm64
```

Windows 使用 `scripts/build_desktop_runtime.ps1` 和 electron-builder 的 Windows NSIS target；Linux 使用同一 Bash runtime 构建脚本和 AppImage target。GitHub Actions 在推送 `v*` tag 时构建 Windows x64、macOS arm64、Linux x64 和 Linux arm64，并发布构建产物。Electron 安装期间需要下载官方 Electron 运行时，工作流通过镜像配置该下载。

## 离线边界

本机登录、数据库、业务数据、已导入地图瓦片和本地媒体不依赖在线服务器。天地图及 DEM 在线回退已在桌面模式禁用。四普数据导入和 DeepSeek 等外部服务仍属于需要外部网络或服务端点的集成，不能在完全断网环境中使用；应在后续迁移阶段决定提供本地数据包/本地推理替代，或在离线界面中明确标记为不可用。
