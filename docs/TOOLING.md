# 工具与环境说明

本仓库只包含 JiuZhang-HsAuto 清理项目的原创工具、文档和品牌资源。完整客户端源码
在私有仓库中，不随本仓库分发。

## 公共工具的运行环境

| 项目 | 要求 |
|---|---|
| 操作系统 | Windows 10/11 x64（脚本按 Windows 路径编写） |
| PowerShell | 5.1+ |
| Python | 3.10+；`python` 在 PATH 中，或通过 `HSAUTO_PYTHON` 指定 |
| .NET SDK | 仅当对私有源码构建时需要 .NET 8 SDK |

`tools/build-release.ps1`、`verify-release.ps1`、`verify_release.py`、
`hsbundle.py` 和 `gen_manifest.py` 默认按私有源码树的目录结构工作：

```text
<private-root>/
  core-src/HsAuto.Core.csproj
  src/HsAuto.csproj
  plugin-src/hdt.csproj
  refs/                 # 本机提供的第三方/游戏引用程序集
  release-manifest.json
  assets/
```

这些文件不在本公共仓库中，因此本仓库不能单独构建或运行客户端。

## 私有客户端的环境（摘要）

完整客户端需要：

- Windows 10 1809+ / Windows 11 x64；管理员权限。
- .NET 8 SDK（构建）或 .NET 8 Desktop Runtime（源码运行）。
- Microsoft Edge WebView2 Runtime。
- 炉石传说 + Battle.net 客户端；BepInEx 5.4.x / Doorstop。
- 可选网易炉石盒子 `HSAng.exe`（Box/AI2/AI3 鉴权，不随仓库分发）。
- 本地 `refs/`：WebView2/SignalR/SQLite 等第三方程序集，以及来自本机炉石安装的
  游戏程序集。游戏程序集不可再分发。

## 构建脚本说明

在私有源码树根目录：

```powershell
$env:HSAUTO_OFFICIAL_PACKAGE = "<解包后的官方 0.9.75 目录>"
$env:HSAUTO_INSTALLERS_DIR  = "<WebView2/VC++ 安装包目录>"
$env:HSAUTO_PYTHON = "python"
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\build-release.ps1
```

`build-release.ps1` 会生成 `out/release`，并调用 `verify_release.py` 做严格门禁。
`out/`、`refs/*.dll`、`build-inputs/` 和官方运行包都不应提交或公开。

## 免责声明

本工具不隶属于网易、暴雪或 HsAuto 官方。游戏自动化可能违反服务条款并导致封号；
请只在你有权控制的账号和系统上使用。工具按“现状”提供，不附带任何担保。
