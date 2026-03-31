# yapi-cli

YApi 的 Python 命令行工具，可直接在终端或 AI Agent 脚本中查询 YApi 接口。

## 前置要求

- Python 3.10+
- 已安装 uv
- 可访问的 YApi 实例
- 已登录 YApi 并可获取完整 Cookie

## 安装

```bash
uv sync
```

## 配置

通过环境变量配置连接信息：

```bash
export YAPI_BASE_URL=https://your-yapi-domain.com
export _yapi_token='xxxxx'
export _yapi_uid='1234'
```

CLI 会自动读取当前工作目录下的 `.env` 文件（已存在的系统环境变量优先）。

也支持完整 Cookie 字符串：

```bash
export YAPI_TOKEN='_yapi_token=xxxxx; _yapi_uid=1234; other_cookie=xxx'
```

| 环境变量 | 说明 | 默认值 |
|---|---|---|
| `YAPI_BASE_URL` | YApi 实例地址 | `http://localhost:3000` |
| `_yapi_token` | Cookie 中的 Token | *(无)* |
| `_yapi_uid` | Cookie 中的 uid | *(无)* |
| `YAPI_TOKEN` | 完整 Cookie 字符串（备用） | *(无)* |
| `YAPI_TIMEOUT` | HTTP 请求超时（秒） | `15` |

## 快速开始

```bash
# 查看帮助
uv run yapi --help

# 通过 API ID 获取接口详情
uv run yapi api get --api_id 49325

# 通过 YApi 页面 URL 自动解析
uv run yapi api get --url "http://yapi.example.com/project/12/interface/api/345"

# 加 --pure 只返回关键字段（过滤网关参数）
uv run yapi api get --api_id 49325 --pure

# 列出指定项目下所有接口
uv run yapi api list --project 251

# 按路径过滤
uv run yapi api list --path /user/login

# 按分类过滤（需指定 --project）
uv run yapi api list --cat 56 --project 12
```

## 命令参考

### 全局选项

| 参数 | 说明 |
|---|---|
| `--base-url TEXT` | YApi 地址（覆盖 `YAPI_BASE_URL`） |
| `--token TEXT` | 完整 Cookie 字符串（覆盖 `YAPI_TOKEN`） |
| `--json` / `--no-json` | 输出 JSON，便于脚本或 Agent 消费 |
| `--version` | 显示版本号 |

### `yapi api get`

获取单个接口详情。API ID 全局唯一，无需项目 ID。

| 参数 | 说明 |
|---|---|
| `--api_id TEXT` | 接口 ID |
| `--url TEXT` | YApi 页面 URL，自动解析 api_id |
| `--pure` | 过滤网关参数，只返回关键字段 |

```bash
yapi api get --api_id 49325
yapi api get --url "http://yapi.example.com/project/12/interface/api/345"
yapi api get --api_id 49325 --pure
```

### `yapi api list`

列出接口列表，支持多种过滤方式。

| 参数 | 说明 |
|---|---|
| `--project TEXT` | 限定项目 ID（不指定则自动发现所有可访项目） |
| `--path TEXT` | 按接口路径过滤 |
| `--cat TEXT` | 按分类 ID 过滤（需配合 `--project`） |
| `--page INT` | 页码（默认1） |
| `--limit INT` | 每页条数（默认20） |

```bash
# 列出项目下所有接口
yapi api list --project 251

# 按路径搜索（自动跨项目）
yapi api list --path /save

# 跨项目搜索并限定路径
yapi api list --project 251 --path /user

# 按分类过滤
yapi api list --cat 56 --project 12
```

## JSON 模式

加 `--json` 输出机器可读的 JSON：

```bash
uv run yapi --json api get --api_id 49325 | jq '.path'
uv run yapi --json api list --project 251 | jq '.[].title'
```

## Cookie 获取

1. 登录 YApi
2. 打开浏览器开发者工具（F12）
3. 在任意请求的 Request Headers 里复制完整 Cookie
4. 确认包含 `_yapi_token` 和 `_yapi_uid`

