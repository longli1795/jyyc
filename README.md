# 电废经营预测系统

电商业务预测系统 — 基于 Flask 的内部 Web 应用，用于电子废料（"四机一脑"：电视机、电脑、冰箱、空调、洗衣机）回收业务的收入、成本和利润测算。

## 功能概述

- **期初库存上传**：上传 Excel 期初库存文件，自动提取并补全物料代码
- **拆解计算**：匹配产品拆解系数，计算拆解产出，应用扣除规则
- **深加工计算**：对深加工类别物料应用深加工系数
- **销售收益**：可销售物料合并 + 销售价格匹配
- **补贴收入**：按物料描述匹配补贴类别计算补贴
- **成本利润**：材料成本、计件工资、制造费用、期间费用、税金附加 → 利润汇总
- **数据管理**：基础数据（产品、价格、补贴、扣除规则等）的 CRUD 与同步发布
- **多用户**：会话隔离、用户分组、页面级权限控制
- **快照**：工作区快照保存与恢复

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 开发模式
set FLASK_ENV=development
set CLEAR_SESSIONS_ON_STARTUP=1
python app.py

# 生产模式
start_production.bat
```

应用默认运行在 `http://127.0.0.1:8080`（开发）或 `http://0.0.0.0:8080`（生产）。

默认管理员：`admin / admin123`

## 生产部署

```bash
# 开机自启
install_autostart.bat          # 安装
uninstall_autostart.bat        # 卸载

# 防火墙（开放 8080 端口）
open_firewall_8080.bat

# 备份计划任务
install_backup_schedule.bat
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | Flask |
| 数据库 | SQLite（默认）/ PostgreSQL / MySQL |
| 缓存 | Redis |
| 数据处理 | pandas |
| 前端 | Jinja2 模板 + Bootstrap + Chart.js |
| 认证 | Flask-Login |

## 项目结构

```
├── app/
│   ├── api/            # 路由层（蓝图）
│   ├── services/       # 服务层
│   ├── core/           # 核心引擎（拆解、深加工计算）
│   ├── models/         # 数据模型（ORM + 会话管理）
│   └── utils/          # 工具函数
├── data/
│   ├── base_data/      # 基础业务数据
│   ├── persistent/     # 固化库存数据
│   ├── snapshots/      # 工作区快照
│   └── sync_history/   # 同步发布历史
├── static/             # 前端静态资源
├── templates/          # Jinja2 页面模板
├── scripts/            # 运维脚本
├── logs/               # 运行日志
└── docs/               # 文档
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `FLASK_ENV` | 运行环境 | `development` |
| `FLASK_HOST` | 监听地址 | `0.0.0.0` |
| `FLASK_PORT` | 监听端口 | `8080` |
| `DATABASE_TYPE` | 数据库类型 | `sqlite` |
| `REDIS_URL` | Redis 连接串 | `redis://localhost:6379/0` |
| `SECRET_KEY` | 会话密钥 | 需修改 |

## 注意事项

- 仅限 Windows 部署（内网使用），不适合公网暴露
- 生产部署前请修改默认 `SECRET_KEY` 和 `admin` 密码
- AI 分析功能依赖 LM Studio 本地实例（可选）
- 开发模式启动时会清除所有会话数据
