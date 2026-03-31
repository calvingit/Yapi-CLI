# yapi-cli

YApi 的 Python 命令行工具，遵循 CLI-Anything 规范。可直接在终端或 AI Agent 脚本中查询、查看和维护 YApi 接口，无需启动 MCP 服务。

## 功能

- 接口搜索：按关键字在一个或多个项目中查找接口
- 接口详情：按项目 ID 和接口 ID 获取完整定义
- 接口保存：创建新接口或更新已有接口
- 项目查询：列出当前 Cookie 会话可访问的项目
- 分类查询：列出项目下的分类和接口统计
- 交互模式：无参数启动 REPL，适合探索与调试

## 前置要求

- Python 3.10+
- 已安装 uv
- 可访问的 YApi 实例
- 已登录 YApi 并可获取完整 Cookie

## 安装

在仓库根目录执行：

```bash
uv sync
```

如果你只想安装可执行命令，也可以：

```bash
uv pip install -e .
```

## 配置

通过环境变量配置连接信息：

```bash
export YAPI_BASE_URL=https://your-yapi-domain.com
export _yapi_token='xxxxx'
export _yapi_uid='1234'
```

CLI 会自动读取当前工作目录下的 `.env` 文件（已存在的系统环境变量优先，不会被 `.env` 覆盖）。

推荐使用拆分参数：

- `_yapi_token=...`
- `_yapi_uid=...`

也支持兼容旧写法：

```bash
export YAPI_TOKEN='_yapi_token=xxxxx; _yapi_uid=1234; other_cookie=xxx'
```

不再支持 `projectId:token` 或 `projectId1:token1,projectId2:token2` 格式。

## 快速开始

```bash
# 查看帮助
uv run yapi-cli --help

# 直接用 YApi 页面 URL 获取接口详情（自动解析 project_id 和 api_id）
uv run yapi-cli api get --url "http://dapi.meiyunji.net/project/908/interface/api/921695"

# 搜索接口（跨当前 Cookie 可访问项目）
uv run yapi-cli api search login

# 基于 URL 自动限定项目后搜索
uv run yapi-cli api search approvalRecord --url "http://dapi.meiyunji.net/project/908/interface/api/921695"

# 按接口路径过滤（可用于精确校验）
uv run yapi-cli api search approvalRecord --url "http://dapi.meiyunji.net/project/908/interface/api/921695" --path /dk/unity/chat/im/approval/approvalRecord

# 获取接口详情
uv run yapi-cli api get 12 345

# 列出项目
uv run yapi-cli project list

# 列出分类
uv run yapi-cli category list 12
```

## 常用命令

```bash
# 创建或更新接口
uv run yapi-cli api save \
  --project 12 \
  --cat-id 56 \
  --title "用户登录" \
  --path /user/login \
  --method POST

# 机器可读 JSON 输出
uv run yapi-cli --json api search login

# 启动交互式 REPL
uv run yapi-cli
```

## 参数说明

根命令支持以下全局参数：

- `--base-url`：YApi 基础地址（默认读取 `YAPI_BASE_URL`）
- `--token`：YApi 完整 Cookie 字符串（可选；若配置 `_yapi_token` 和 `_yapi_uid` 则可不传）
- `--json`：输出 JSON，便于脚本或 Agent 消费

`api get` 与 `api search` 支持 `--url` 参数，可从 YApi 页面 URL 自动解析 `project_id`。

## Cookie 获取

1. 登录 YApi
2. 打开浏览器开发者工具（F12）
3. 在任意请求的 Request Headers 里复制完整 Cookie
4. 确认包含 `_yapi_token` 和 `_yapi_uid`

![Token 获取示例](./images/token.png)

## Skill 文件

技能定义文件位于 `skills/SKILL.md`，可被支持 CLI-Anything 技能发现机制的 AI 工具自动识别。
