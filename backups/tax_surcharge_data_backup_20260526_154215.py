# 税金及附加基础数据 - 内置数据

import pandas as pd

# 完整的税金及附加基础数据
TAX_SURCHARGE_DATA = [
    {"项目": "土地使用税", "金额": 21424.3, "备注": "月均数据，含库房组分摊的90%"},
    {"项目": "印花税、环保税、城建税及教育费附加", "金额": "0.77%", "备注": "费率，与收入相关"},

]


def get_tax_surcharge_dataframe():
    """获取税金及附加基础数据DataFrame"""
    return pd.DataFrame(TAX_SURCHARGE_DATA)
