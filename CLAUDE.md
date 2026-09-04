# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

电商业务预测系统（经营预测系统）— 基于 Flask 的内部 Web 应用，用于电子废料（"四机一脑"：电视机、电脑、冰箱、空调、洗衣机）回收业务的收入、成本和利润测算。原始数据来自 SAP 物料库存报表（每月 4 日 03:00 自动取上个月）或手工上传的 Excel 期初库存，系统通过拆解系数、扣除规则、深加工计算、销售价格匹配和补贴计算，最终生成利润汇总。

## 启动与运行

```bash
# 安装依赖
pip install -r requirements.txt
# 开发模式（单人调试，启动时清除会话）
set FLASK_ENV=development
set CLEAR_SESSIONS_ON_STARTUP=1
python app.py
# 或: restart_app.bat

# 生产模式（多用户内网）
start_production.bat
# 守护进程（崩溃后自动重启）
scripts\run_production_service.bat

# 开机自启（同时安装每月 4 日 03:00 SAP 取数任务；每日备份仍为 02:00）
install_autostart.bat          # 安装登录自启 + SAP 月度取数
uninstall_autostart.bat        # 卸载自启与 SAP 取数任务
status_autostart.bat           # 查看状态

# 防火墙（开放 8080 端口供局域网访问）
open_firewall_8080.bat

# 备份计划任务（每日 02:00，时间不要改去迁就 SAP）
install_backup_schedule.bat    # 创建每日/每周/月清理任务

# SAP 取数（计划任务已包含在 install_autostart.bat；下列为手工补跑/单独维护）
scripts\run_sap_monthly_export.bat --period 2026.08
install_sap_schedule.bat       # 仅重装 SAP 月度任务（一般不必单独跑）
scripts\set_sap_credential.bat
scripts\disable_script_notify.bat
```

应用默认运行在 `http://127.0.0.1:8080`（开发）或 `http://0.0.0.0:8080`（生产）。默认管理员: `admin / admin123`。

## 入口点与启动链

```
app.py                              — 薄封装，入口
  └─ app/main.py:run_app()           — 会话清除、固件库存加载、健康检查
       └─ app/__init__.py:create_app() — Flask 工厂：配置、Redis、DB、蓝图注册
```

`create_app()` 中的关键初始化：
- 数据库迁移：自动为 `users` 表补齐 `is_read_only`、`allowed_pages`、`is_data_maintainer` 列
- 薪酬核算/制造费用数据：首次运行时从 Excel 固化到 `data/base_data/` 的 Python 模块
- `context_processor`：向所有模板注入 `allowed_pages` 列表，前端菜单权限过滤
- Redis 回退：不可用时自动切换到文件系统 Session 存储
- 注册定时任务：清理过期会话（`register_scheduled_tasks`）

## 架构

```
客户端浏览器
  │
  ▼ (Flask :8080)
认证层 (login_required, admin_required, page_permission_required)
  │
  ├─ 路由层 (app/api/ 蓝图)
  │   ├─ main_routes.py                        — 页面渲染 + 导出
  │   ├─ calculation_api.py                    — 计算管道端点
  │   ├─ data_management_api.py                — 基础数据 CRUD + 同步发布
  │   ├─ statistics_api.py                     — 统计/利润分析
  │   ├─ cost_forecast_api.py                  — 成本预测
  │   ├─ disassembly_manufacturing_no_opening.py — 不考虑期初库存的制造费用累加（10 项公式）
  │   ├─ snapshot_api.py                       — 工作区快照
  │   ├─ auth_api.py                           — 登录/注册/个人信息
  │   ├─ admin_api.py                          — 用户管理（管理员）
  │   ├─ sap_api.py                            — SAP 取数手动触发 / 状态 / 本机重载
  │   └─ system_api.py                         — 健康检查 / 系统状态
  │
  ├─ 服务层 (app/services/)
  │   ├─ calculation_service.py    — 编排完整计算管道
  │   ├─ data_service.py           — 数据持久化
  │   ├─ opening_inventory_store.py — 期初库存固化到磁盘
  │   ├─ snapshot_service.py       — 快照管理
  │   ├─ sync_history_service.py   — 基础数据同步发布历史
  │   ├─ ai_analysis_service.py    — LM Studio AI 分析集成
  │   └─ status_service.py         — 系统状态收集
  │
  ├─ SAP GUI 取数 (app/sap_gui/)
  │   ├─ sap_login.py / export_zmmr0010n_y.py / format_export.py — GUI 登录、ZMMR0010N_Y 导出、N301 库位筛选
  │   └─ pipeline.py               — 导出 → 筛选 → 写入期初库存
  │
  ├─ 核心引擎 (app/core/)
  │   ├─ data_processor.py       — 从 Excel 提取，用映射表补全 R3 代码
  │   ├─ calculation_engine.py   — 拆解、深加工、可销售合并、补贴计算
  │   └─ page_permissions.py     — 页面级权限定义与检查
  │
  ├─ 工具层 (app/utils/)
  │   ├─ auth_utils.py          — 认证辅助（密码哈希等）
  │   ├─ data_utils.py          — 安全 JSON 转换等数据通用函数
  │   ├─ excel_utils.py         — Excel 导入导出辅助
  │   └─ deducted_disassembly_align.py — 被减扣数据与拆解数据对齐
  │
  └─ 数据模型 (app/models/)
      ├─ database.py              — User, Group, SessionDataset, CalculationHistory 等 ORM 模型
      ├─ session_data_manager.py  — 按 session_id 隔离会话数据的核心管理器（SessionDataManagerFactory）
      └─ compatibility.py         — 旧版 pickle 单例 AppDataManager 的适配器
```

## 核心计算管道

1. **数据提取** — `DataProcessor.extract_data_auto()`: 从 Excel 读取期初库存 → 筛选"旧机"类别 → 用映射表补全物料代码（R3 码）
2. **拆解计算** — `CalculationEngine.calculate_disassembly_auto()`: 匹配产品拆解系数 → 计算 `库存(台) × 单台重量(kg/台) × 投入产出比 × 拆解系数` → 应用扣除规则 → 产出"扣除后数据""原始未扣除数据""扣除数据"
3. **深加工** — `CalculationEngine.calculate_deep_processing_auto()`: 对匹配深加工类别的物料应用深加工系数
4. **可销售合并** — `CalculationEngine.merge_saleable_data()`: 合并扣除后数据 + 深加工数据 → 匹配销售价格 → 计算销售收益
5. **补贴收入** — `CalculationEngine.calculate_subsidy_income()`: 按物料描述匹配补贴类别 → 计算补贴收入
6. **成本与利润** — 材料成本（kg 单价匹配）、计件工资（`labor_cost_data`）、制造费用（`manufacturing_cost_data`）、期间费用（`period_cost_data`）、税金附加（`tax_surcharge_data`） → 利润汇总

### 拆解物原料成本公式

在 `cost_forecast_api.py:calculate_material_cost()` 中统一计算所有旧机类别行：

```
材料成本差异 = 本期计划采购数量 × 计划采购单价 × 0.005530417
单位投料成本 = (价值 + 本期计划采购数量 × 计划采购单价) ÷ (初始数据 + 本期计划采购数量)
             + 材料成本差异 ÷ 本期实际投产数量
拆解物原料成本 = 本期实际投产数量 × 单位投料成本
```

其中"本期实际投产数量"对应"非限制使用的库存"字段，"价值"来自提取结果手工 sheet。

### 制造费用（不考虑期初库存口径）

`app/api/disassembly_manufacturing_no_opening.py` 实现了独立的 10 项公式，用于拆解收益分析表中不考虑期初库存和库存结余的制造费用累加逻辑。

## 多用户会话模型

每个浏览器会话有唯一的 `session_id`（UUID）。`SessionDataManagerFactory` 按会话隔离管理数据实例（通过 `get_session_data_manager()` 获取），存储在 SQLite（`SessionDataset` 表）+ Redis 缓存。上传的期初库存固化到 `data/persistent/`，启动时加载到全局会话。`app/models/compatibility.py` 为旧式单例 `AppDataManager` 提供适配器以保证向后兼容。

## 权限系统

三层体系：登录认证 → 管理员角色 → 页面级权限（`app/core/page_permissions.py`）。管理员可为非管理员用户分配：首页权限（含子模块）、数据管理权限（含子页面）、只读权限、数据维护员权限。`path_to_page_key()` 将 URL 路径映射到权限键，`user_has_page_access()` 执行检查。`expand_allowed_pages()` 将权限自动展开包含子页面。

## 基础数据

`data/base_data/` 目录包含固化的业务参考数据（Python 模块 + JSON），在应用启动时加载为模块常量，计算时通过 pandas DataFrame 查询匹配：

**收入预测相关：**
- `mapping_data.py` — ERP 物料代码到外部代码的映射（R3 码补全）
- `product_data.py` / `product_disassembly.json` — 产品拆解系数（JSON + Python 双格式）
- `deduction_data.py` — 不可销售物料扣除规则
- `price_data.py` — 含税/不含税销售价格
- `subsidy_data.py` — 政府补贴单价
- `deep_processing_data.py` / `deep_processing_coefficients.json` — 深加工系数
- `saleable_data.py` — 可销售物料数据

**成本预测相关：**
- `labor_cost_data.py` — 计件工资/人工成本数据
- `manufacturing_cost_data.py` — 制造费用数据
- `period_cost_data.py` — 期间费用数据
- `salary_accounting_data.py` — 薪酬核算基础数据
- `tax_surcharge_data.py` — 税金及附加数据

**同步发布机制：** 基础数据维护员（`is_data_maintainer`）可编辑映射、价格、扣除规则等数据并通过「发布同步」将修改广播到所有在线会话。发布历史记录在 `data/sync_history/`，由 `sync_history_service.py` 管理。

## 环境变量

关键环境变量（`scripts/production_env.bat` 中有完整生产配置）：

| 变量 | 说明 | 默认值 |
|---|---|---|
| `FLASK_ENV` | `development` / `production` / `testing` | `development` |
| `FLASK_DEBUG` | 调试模式 | `False` |
| `FLASK_HOST` | 监听地址 | `0.0.0.0` |
| `FLASK_PORT` | 监听端口 | `8080` |
| `SECRET_KEY` | Flask 会话签名密钥 | 硬编码默认值（需修改） |
| `DATABASE_TYPE` | `sqlite` / `mysql` / `postgresql` | `sqlite`（base Config），`postgresql`（ProductionConfig） |
| `REDIS_URL` | Redis 连接串 | `redis://localhost:6379/0` |
| `CLEAR_SESSIONS_ON_STARTUP` | 启动时清除所有会话数据 | 开发 `1`，生产 `0` |
| `SESSION_COOKIE_SECURE` | HTTPS only cookie | 生产默认 `false`（HTTP 内网） |
| `AI_MODEL_BASE_URL` | LM Studio 地址 | `http://10.30.5.32:1234` |

`app/config.py` 中的 `Config` 类定义了所有配置项及其默认值。`DevelopmentConfig` / `ProductionConfig` 按 `FLASK_ENV` 选择，继承自 `Config`。

## 存储

- **SQLite**（默认 `data_storage/business_forecast.db`）— 用户、分组、会话、数据集。支持 PostgreSQL/MySQL（通过 `DATABASE_TYPE` 环境变量切换）
- **Redis** — 会话缓存（不可用时回退到文件系统 `data_storage/sessions/`）
- **文件系统** — `data/persistent/`（期初库存固化）、`data/snapshots/`（用户工作区快照）、`data/backups/`（备份）、`data/sap_exports/`（SAP 原始/筛选导出）、`uploads/`（上传临时文件）

## SAP 期初库存取数

在已授权 Windows 机上用 SAP GUI 740 登录 PRD，导出 `ZMMR0010N_Y`（公司代码 N300、上个月），筛选工厂 `N301` 与库位（成品库 / 屏项目-成品 / 危废库 / 原料库），写入 `data/persistent/opening_inventory.xlsx`。手工「期初库存文件上传」仍可用，可覆盖 SAP 结果。取数成功后**不会**自动跑计算管道。

- 凭据：环境变量 `SAP_USER`/`SAP_PASSWORD` → `secrets.ini`（不入库）→ Windows 凭据管理器。复制 `secrets.example.ini` 为 `secrets.ini`，或运行 `scripts\set_sap_credential.bat`
- 首次：`scripts\disable_script_notify.bat` 后完全退出 SAP 再开
- 手工验证：`scripts\run_sap_monthly_export.bat --period 2026.08`
- 定时任务随 `install_autostart.bat` 一起安装（每月 4 日 03:00，本机时区即北京时间，导出上个月）。单独重装可用 `install_sap_schedule.bat`
- 每日备份任务仍为 02:00，安装自启/SAP 任务不会改备份时间
- 不能跑在无界面服务账号下；2/3 点执行时 Windows 用户会话必须在（锁屏通常可以，断开的远程桌面经常不行）

## 关键注意事项

- 仅限 Windows 部署（所有运维脚本为 `.bat`），内网使用，Flask 内置服务器（`threaded=True`），不适合公网暴露
- 无自动化测试框架，scripts/ 下有临时验证脚本（`validate_*.py`、`test_*.py`、`debug_*.py`）
- 硬编码的 `SECRET_KEY` 和默认管理员密码 `admin/admin123` 需在生产部署前修改
- 数据库文件通过 Git LFS 追踪（`.gitattributes`）；`data/persistent/` 和 `logs/` 已在 `.gitignore` 排除
- AI 分析功能通过 LM Studio 本地实例（`http://10.30.5.32:1234`）可选集成，默认模型 `google/gemma-4-26b-a4b`
- `app/session_interface_fix.py` 为 Werkzeug 3+ / flask-session 0.5 的 bytes/string 兼容补丁
- 生产部署详见 `docs/运行模式说明.md`（模式对比、进程管理、定时备份恢复、FAQ）
- 操作手册在 `docs/operation_manual/index.html`（含 66 张截图）
