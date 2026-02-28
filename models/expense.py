from dataclasses import dataclass


@dataclass
class FixedExpense:
    name: str
    amount: float       # EUR
    day_of_month: int   # 1–31, the day it is due each month
    id: int | None = None
