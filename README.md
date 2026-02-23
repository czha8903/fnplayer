# 飞牛影视- PotPlayer 播放器控制服务

这是一个基于 Flask 的 HTTP 服务，用于远程控制 PotPlayer 播放器。服务会将网络路径映射到本地 UNC 路径，并通过 PotPlayer 播放指定的文件。

## 功能特性

- 🎬 **远程播放控制**：通过 HTTP 请求远程触发播放
- 🔄 **路径映射**：自动将网络文件路径转换为本地 UNC 路径
- 🖥️ **GUI 配置界面**：友好的配置管理工具
- 📊 **健康检查**：提供 /ping 端点检测服务状态

## 系统要求

- Windows 10 或 11
- Python 3.8 或更高版本
- PotPlayer 播放器（[下载地址](https://potplayer.tv/)）
- 篡改猴（[下载地址](http://tampermonkey.net/)）
- 网络连接以访问 NAS/SMB 共享

## 安装

### 1. 克隆或下载项目

```bash
git clone https://github.com/czha8903/fnplayer.git
```

### 2. 安装依赖

```bash
pip install flask
```

### 3. 配置文件设置

编辑 `config.json` 文件，配置以下参数：

```json
{
  "potplayer_exe": "C:/DAUM/PotPlayer/PotPlayerMini64.exe",
  "web_prefix": "存储空间 xx/xxx/video（视频根目录）/",
  "unc_root": "\\\\IP\\video（视频根目录）\\",
  "host": "127.0.0.1",
  "port": （端口）
}
```

| 配置项 | 说明 | 示例 |
|-------|------|------|
| `potplayer_exe` | PotPlayer 可执行文件的完整路径 | `C:/DAUM/PotPlayer/PotPlayerMini64.exe` |
| `web_prefix` | 网络文件的前缀路径 | `存储空间 1/xxx的文件/video/fnvideo` |
| `unc_root` | 对应的 UNC 路径（网络路径） | `\\\\ip\\video\\fnvideo` |
| `host` | 服务器监听的主机地址 | `127.0.0.1` 或 `0.0.0.0` |
| `port` | 服务器监听的端口 | `8080` |

## 使用

### 方式一：运行 GUI 应用（推荐）

```bash
python gui.py #浏览器需要安装油猴和加载tm.js
```

这会启动一个 GUI 界面，你可以：
- 实时配置服务参数
- 启动/停止服务
- 查看服务状态

### 方式二：win直接运行服务

```bash
gui.exe #（打开release下载gui.exe,加载tm.js）
```

服务会在后台启动，默认监听 `http://127.0.0.1:8080`

## API 端点

### 1. 健康检查

**请求：**
```
GET /ping
```

**响应：**
```json
{
  "ok": true
}
```

### 2. 播放文件

**请求：**
```
POST /push
Content-Type: application/json

{
  "url": "http://example.com/video.mp4",
  "path": "存储空间 1/xx 的文件/video/fnvideo/video.mp4",
  "meta": {
    "title": "视频标题",
    "episode": 1
  }
}
```

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `url` | string | ❌ | 原始 URL（仅用于日志记录） |
| `path` | string | ✅ | 文件的网络路径 |
| `meta` | object | ❌ | 元数据信息（仅用于日志记录） |

**响应（成功）：**
```json
{
  "ok": true,
  "mapped": "\\\\IP\\video\\fnvideo\\video.mp4"
}
```

**响应（失败）：**
```json
{
  "ok": false,
  "error": "错误信息",
  "mapped": "\\\\IP\\video\\fnvideo\\video.mp4"
}
```

## 日志

所有请求都会记录到 `recv_logs/received.jsonl` 文件中，每行是一个 JSON 对象。

## 常见问题

### Q: 如何添加白名单访问？

A: 修改 `gui.py` 中的 Flask 路由，添加 IP 白名单检查。

### Q: 服务不能启动？

A: 检查以下内容：
1. 确认 `potplayer_exe` 路径正确
2. 确认 UNC 路径可以访问
3. 确认端口未被占用
4. 检查 Python 输出的错误信息

### Q: 路径映射不正确？

A: 检查 `web_prefix` 和 `unc_root` 的设置是否匹配你的实际文件系统结构。

## 项目结构

```
server/
├── gui.py                    # 主应用文件
├── config.json              # 配置文件
├── tm.js                    # JavaScript 篡改猴脚本
├── README.md               # 本文件
└── recv_logs/
    └── received.jsonl      # 请求日志文件
```



## 许可证

[MIT]

## 联系方式

如有问题或建议，请提交 Issue 或联系开发者。
