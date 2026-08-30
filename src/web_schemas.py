"""JSON API 的 Pydantic 请求模型。

校验规则与页面表单共用 web_services 里的同一套函数，
保证两个入口对合法数据的定义一致。
"""

from datetime import date

from pydantic import BaseModel, field_validator

import web_services as services


class ExpenseCreate(BaseModel):
    expense_date: date
    category: str
    amount: str
    merchant: str = ""
    description: str = ""

    @field_validator("category")
    @classmethod
    def category_must_exist(cls, value: str) -> str:
        value = value.strip()
        if value not in services.EXPENSE_CATEGORIES:
            raise ValueError("请选择有效的消费类别。")
        return value

    @field_validator("amount")
    @classmethod
    def amount_must_be_money(cls, value: str) -> str:
        return str(services.parse_amount(str(value)))

    @field_validator("merchant")
    @classmethod
    def merchant_length(cls, value: str) -> str:
        value = value.strip()
        if len(value) > 120:
            raise ValueError("商户名称不能超过120个字符。")
        return value

    @field_validator("description")
    @classmethod
    def description_length(cls, value: str) -> str:
        value = value.strip()
        if len(value) > 1000:
            raise ValueError("说明不能超过1000个字符。")
        return value
