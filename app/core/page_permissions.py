"""
页面权限配置
定义可配置的 page_key、中文名称，以及路由路径到 page_key 的映射规则。
"""

# 顶层模块权限（不含子页面）
TOP_LEVEL_PAGE_PERMISSIONS = [
    ("home", "首页"),
]

# 已废弃的 page_key（读取时迁移为 home）
LEGACY_HOME_PAGE_KEYS = frozenset({"cost_forecast", "revenue_forecast"})

# 首页子模块：(key, 中文名称)
HOME_SUB_PAGES = [
    ("home_profit_summary", "利润测算汇总表"),
    ("home_revenue_forecast", "收入预测"),
    ("home_cost_forecast", "成本预测"),
    ("home_cost_calculation", "成本计算"),
]

# 数据管理子页面：(key, 中文名称, 子分类)，顺序与数据管理 Hub 页卡片一致
DATA_MANAGEMENT_CATEGORY_ORDER = ["收入预测数据", "成本预测数据"]

DATA_MANAGEMENT_SUB_PAGES = [
    # 收入预测数据
    ("data_management_extracted_data", "提取结果编辑", "收入预测数据"),
    ("data_management_deducted_data", "被减扣数据编辑", "收入预测数据"),
    ("data_management_saleable_data", "可销售量数据编辑", "收入预测数据"),
    ("data_management_mapping", "内置映射表", "收入预测数据"),
    ("data_management_deduction", "减扣规则管理", "收入预测数据"),
    ("data_management_deep_processing", "深加工数据管理", "收入预测数据"),
    ("data_management_product", "产品拆解系数管理", "收入预测数据"),
    ("data_management_price", "销售价格", "收入预测数据"),
    ("data_management_subsidy", "基金补贴单价", "收入预测数据"),
    # 成本预测数据
    ("data_management_labor_cost", "计件人工标准数据", "成本预测数据"),
    ("data_management_salary_accounting", "薪酬核算基础数据", "成本预测数据"),
    ("data_management_manufacturing_cost", "制造费用基础数据", "成本预测数据"),
    ("data_management_period_cost", "期间费用基础数据", "成本预测数据"),
    ("data_management_tax_surcharge", "税金及附加基础数据", "成本预测数据"),
]

# 子页面路径前缀 -> page_key（更具体的路径放前面）
_DATA_MGMT_SUB_PATHS = [
    ("/revenue-forecast/data-management/mapping", "data_management_mapping"),
    ("/data-management/mapping", "data_management_mapping"),
    ("/revenue-forecast/data-management/product", "data_management_product"),
    ("/data-management/product", "data_management_product"),
    ("/revenue-forecast/data-management/deduction", "data_management_deduction"),
    ("/data-management/deduction", "data_management_deduction"),
    ("/revenue-forecast/data-management/deep-processing", "data_management_deep_processing"),
    ("/data-management/deep-processing", "data_management_deep_processing"),
    ("/data-management/extracted-data-editor", "data_management_extracted_data"),
    ("/data-management/extracted-data", "data_management_extracted_data"),
    ("/data-management/deducted-data-editor", "data_management_deducted_data"),
    ("/data-management/deducted-data", "data_management_deducted_data"),
    ("/revenue-forecast/data-management/saleable-data-editor", "data_management_saleable_data"),
    ("/revenue-forecast/data-management/price", "data_management_price"),
    ("/data-management/price", "data_management_price"),
    ("/revenue-forecast/data-management/subsidy", "data_management_subsidy"),
    ("/data-management/subsidy", "data_management_subsidy"),
    ("/revenue-forecast/data-management/labor-cost", "data_management_labor_cost"),
    ("/data-management/labor-cost", "data_management_labor_cost"),
    ("/cost-forecast/data-management/salary-accounting", "data_management_salary_accounting"),
    ("/cost-forecast/data-management/manufacturing-cost", "data_management_manufacturing_cost"),
    ("/cost-forecast/data-management/period-cost", "data_management_period_cost"),
    ("/cost-forecast/data-management/tax-surcharge", "data_management_tax_surcharge"),
]

# 首页子模块路径前缀 -> page_key（更具体的路径放前面）
_HOME_SUB_PATHS = [
    # 利润汇总 API
    ("/api/statistics/profit-summary", "home_profit_summary"),
    ("/api/statistics/analyze-profit-summary", "home_profit_summary"),
    # 成本计算
    ("/cost-forecast/production-cost-allocation", "home_cost_calculation"),
    ("/cost-forecast/disassembly-product-cost", "home_cost_calculation"),
    ("/cost-forecast/deep-processing-product-cost", "home_cost_calculation"),
    ("/cost-forecast/disassembly-profit-analysis", "home_cost_calculation"),
    # 成本预测
    ("/cost-forecast/material-cost", "home_cost_forecast"),
    ("/cost-forecast/piece-rate-wage", "home_cost_forecast"),
    ("/cost-forecast/manufacturing-cost", "home_cost_forecast"),
    ("/cost-forecast/screen-cost-allocation", "home_cost_forecast"),
    ("/cost-forecast/period-cost", "home_cost_forecast"),
    ("/cost-forecast/tax-surcharge", "home_cost_forecast"),
    ("/cost-forecast", "home_cost_forecast"),
    # 收入预测
    ("/revenue-forecast/sales-revenue", "home_revenue_forecast"),
    ("/revenue-forecast/subsidy-income", "home_revenue_forecast"),
    ("/revenue-forecast/disassembly-product-output-value", "home_revenue_forecast"),
    ("/revenue-forecast/deep-processing-product-output-value", "home_revenue_forecast"),
]

# 路径前缀 -> page_key，按匹配顺序（更具体的放前面）
_PATH_PREFIX_TO_PAGE_KEY = _DATA_MGMT_SUB_PATHS + _HOME_SUB_PATHS + [
    ("/cost-forecast/data-management", "data_management"),
    ("/revenue-forecast/data-management", "data_management"),
    ("/revenue-forecast", "home_revenue_forecast"),
    ("/data-management/", "data_management"),
    ("/data-management", "data_management"),
]

# 兼容旧引用
PAGE_PERMISSIONS = TOP_LEVEL_PAGE_PERMISSIONS + [("data_management", "数据管理")]

HOME_LANDING_PATH = "/"
DATA_MANAGEMENT_LANDING_PATH = "/data-management/"


def _coerce_pages_list(pages):
    """将 allowed_pages 规范为 list。"""
    if pages is None:
        return []
    if isinstance(pages, (str, bytes)):
        import json
        try:
            pages = json.loads(pages) if pages else []
        except (TypeError, ValueError):
            return []
    if hasattr(pages, '__iter__') and not isinstance(pages, (str, bytes)):
        return list(pages)
    return []


def normalize_stored_allowed_pages(pages, *, empty_means_home=False):
    """
    规范化存储的 allowed_pages：
    - 废弃 key cost_forecast/revenue_forecast 合并为 home
    - empty_means_home=True 时，None/[] 视为 ["home"]（用于历史数据迁移）
    """
    raw = _coerce_pages_list(pages)
    if not raw:
        return ["home"] if empty_means_home else []

    result = []
    seen = set()
    has_home = False

    for key in raw:
        if key in LEGACY_HOME_PAGE_KEYS:
            key = "home"
        if key in seen:
            continue
        seen.add(key)
        result.append(key)
        if key == "home":
            has_home = True

    if not has_home and any(k in LEGACY_HOME_PAGE_KEYS for k in raw):
        if "home" not in seen:
            result.insert(0, "home")

    return result


def get_all_home_sub_keys():
    """返回所有首页子模块 page_key 列表。"""
    return [p[0] for p in HOME_SUB_PAGES]


def get_all_data_management_sub_keys():
    """返回所有数据管理子页面 page_key 列表。"""
    return [p[0] for p in DATA_MANAGEMENT_SUB_PAGES]


def get_all_page_keys_with_labels():
    """返回 [(page_key, label), ...]，供后台多选使用（扁平列表，兼容旧逻辑）。"""
    items = list(TOP_LEVEL_PAGE_PERMISSIONS)
    items.extend(HOME_SUB_PAGES)
    items.append(("data_management", "数据管理"))
    items.extend((p[0], p[1]) for p in DATA_MANAGEMENT_SUB_PAGES)
    return items


def get_page_permissions_for_admin():
    """返回分层结构，供后台用户编辑 UI 渲染。"""
    home_children = [
        {"items": [{"key": key, "label": label} for key, label in HOME_SUB_PAGES]}
    ]

    categories = {}
    for key, label, category in DATA_MANAGEMENT_SUB_PAGES:
        categories.setdefault(category, []).append({"key": key, "label": label})

    dm_children = [
        {"category": cat, "items": categories[cat]}
        for cat in DATA_MANAGEMENT_CATEGORY_ORDER
        if cat in categories
    ]

    return [
        {
            "key": "home",
            "label": "首页",
            "type": "group",
            "children": home_children,
        },
        {
            "key": "data_management",
            "label": "数据管理",
            "type": "group",
            "children": dm_children,
        },
    ]


def expand_allowed_pages(pages):
    """
    将 allowed_pages 展开为完整权限集合（用于前端展示过滤）。
    home 展开为全部首页子模块；有任一首页子模块时补充 home hub 键。
    data_management 同理。
    """
    pages = normalize_stored_allowed_pages(pages)
    if not pages:
        return []
    result = set(pages)

    home_sub_keys = get_all_home_sub_keys()
    if "home" in result:
        result.update(home_sub_keys)
    elif any(k in result for k in home_sub_keys):
        result.add("home")

    dm_sub_keys = get_all_data_management_sub_keys()
    if "data_management" in result:
        result.update(dm_sub_keys)
    elif any(k in result for k in dm_sub_keys):
        result.add("data_management")

    return list(result)


def user_has_page_access(allowed, page_key):
    """判断用户是否拥有指定 page_key 的访问权限。"""
    if not page_key:
        return True
    allowed = normalize_stored_allowed_pages(allowed)
    allowed_set = set(allowed or [])
    if page_key in allowed_set:
        return True

    home_sub_keys = get_all_home_sub_keys()
    dm_sub_keys = get_all_data_management_sub_keys()

    # legacy：home 授予全部首页子模块
    if page_key in home_sub_keys and "home" in allowed_set:
        return True
    # 首页 hub：有任一首页子模块权限即可
    if page_key == "home":
        if "home" in allowed_set:
            return True
        return any(k in allowed_set for k in home_sub_keys)

    # legacy：data_management 授予全部子页面
    if page_key in dm_sub_keys and "data_management" in allowed_set:
        return True
    # 数据管理 hub：有任一子页面权限即可
    if page_key == "data_management":
        if "data_management" in allowed_set:
            return True
        return any(k in allowed_set for k in dm_sub_keys)

    return False


def user_has_home_access(allowed, is_admin=False):
    """判断用户是否有首页访问权限。"""
    if is_admin:
        return True
    allowed = normalize_stored_allowed_pages(allowed)
    if "home" in (allowed or []):
        return True
    home_sub_keys = get_all_home_sub_keys()
    return any(k in (allowed or []) for k in home_sub_keys)


def user_has_data_management_access(allowed, is_admin=False):
    """判断用户是否有基础数据管理访问权限。"""
    if is_admin:
        return True
    allowed = normalize_stored_allowed_pages(allowed)
    return user_has_page_access(allowed, "data_management")


def user_can_login_with_pages(allowed, is_admin=False):
    """管理员，或拥有首页/数据管理权限之一，才允许登录。"""
    if is_admin:
        return True
    allowed = normalize_stored_allowed_pages(allowed)
    return user_has_home_access(allowed) or user_has_data_management_access(allowed)


def get_user_landing_path(allowed, is_admin=False):
    """返回用户登录或无权限时的默认落地路径。"""
    if is_admin or user_has_home_access(allowed, is_admin):
        return HOME_LANDING_PATH
    if user_has_data_management_access(allowed, is_admin):
        return DATA_MANAGEMENT_LANDING_PATH
    return HOME_LANDING_PATH


def user_can_access_path(allowed, path, is_admin=False):
    """判断用户是否可访问指定路径（用于 next 跳转校验）。"""
    if is_admin:
        return True
    allowed = normalize_stored_allowed_pages(allowed)
    page_key = path_to_page_key(path)
    if page_key is None:
        return True
    return user_has_page_access(allowed, page_key)


def path_to_page_key(path):
    """
    根据请求路径解析出对应的 page_key。
    若路径不属于任何需权限控制的业务页，返回 None。
    """
    if not path:
        return None
    path = path.rstrip("/") or "/"
    if path == "/":
        return "home"
    for prefix, key in _PATH_PREFIX_TO_PAGE_KEY:
        if path == prefix or path.startswith(prefix + "/"):
            return key
    return None


def get_all_page_keys():
    """返回所有 page_key 列表（用于管理员“全部权限”等）。"""
    keys = [p[0] for p in TOP_LEVEL_PAGE_PERMISSIONS]
    keys.extend(get_all_home_sub_keys())
    keys.append("data_management")
    keys.extend(get_all_data_management_sub_keys())
    return keys
