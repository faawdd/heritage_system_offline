# 离线桌面版

本分支以在线版 Django 模型和迁移为业务数据基线。桌面运行时使用本机 SQLite 数据库；数据库、媒体、日志、备份、DEM 缓存和地图切片保存在 Electron `userData` 目录，不写入应用安装目录。

## 首次启动

首次打开桌面应用时可填写地区前缀；留空时系统名称为“文物综合管理平台”，填写后自动组合为“{地区前缀}文物综合管理平台”。数据库迁移完成后，仅在尚无活动超级管理员的数据库中创建 `admin` 账户，初始密码为 `admin`。首次登录必须修改密码；修改成功后初始密码失效。请勿将初始口令作为日常口令使用。

## 离线地图

系统管理中的“离线地图切片”支持导入：

- QGIS/兼容工具导出的 `.mbtiles` 栅格瓦片数据库；
- 按 `z/x/y.png`、`z/x/y.jpg` 或 `z/x/y.webp` 组织的 XYZ/TMS `.zip`，导入时选择行号方案。

瓦片集写入本机数据目录的 `map-tiles` 子目录。地图右上角可在天地图在线底图和当前选择的离线底图间切换；离线模式必须先导入并选择瓦片集。底图切换会保留文物、KML 和保护区等业务叠加图层。MBTiles 元数据中的范围可用于地图预览定位。

## 本机开发和构建

```sh
npm --prefix frontend ci
npm --prefix frontend run build
bash scripts/build_desktop_runtime.sh
cd frontend && npx electron-builder --publish never --mac dmg zip --arm64
```

Windows 使用 `scripts/build_desktop_runtime.ps1` 和 electron-builder 的 Windows NSIS target；Linux 使用同一 Bash runtime 构建脚本和 AppImage target。GitHub Actions 在推送 `v*` tag 时构建 Windows x64、macOS arm64、Linux x64 和 Linux arm64，并发布构建产物。Electron 安装期间需要下载官方 Electron 运行时，工作流通过镜像配置该下载。macOS、Windows 和 Linux 桌面版均使用旧 offline 分支的 `logo.png` 应用图标。

## macOS 首次打开

当前 macOS 安装包未使用 Apple Developer ID 签名和公证。下载后 Gatekeeper 可能提示“文件已损坏”或阻止打开。这通常是 macOS 隔离属性拦截未签名应用，并不代表应用文件真的损坏。

仅在确认安装包来自本项目可信的 GitHub Release 后操作：将应用拖入“应用程序”目录，打开“终端”执行：

```sh
xattr -dr com.apple.quarantine "/Applications/文物综合管理平台（离线版）.app"
```

如果应用名称或安装位置不同，请将命令中的路径替换为 Finder 中该 `.app` 的实际路径，然后从“应用程序”重新打开。此命令只移除该应用的下载隔离标记，不要对来源不明的应用执行。

正式分发给其他用户前，应使用 Apple Developer ID Application 证书为 macOS 包签名并完成 Apple 公证；这需要在 GitHub Actions 仓库配置证书和公证凭据。当前工作流没有这些凭据，因此生成的是未签名包。

## 离线边界

本机登录、数据库、业务数据、已导入地图瓦片和本地媒体不依赖在线服务器。DEM 缺失时不会自动联网下载；天地图仅在用户主动切换到在线底图时请求网络。四普数据导入和 DeepSeek 等外部服务仍属于需要外部网络或服务端点的集成，不能在完全断网环境中使用；应在后续迁移阶段决定提供本地数据包/本地推理替代，或在离线界面中明确标记为不可用。
