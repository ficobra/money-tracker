from dataclasses import dataclass, field


@dataclass
class Snapshot:
    year: int
    month: int
    # Maps account name → balance in EUR
    balances: dict[str, float] = field(default_factory=dict)
    id: int | None = None

    @property
    def total(self) -> float:
        return sum(self.balances.values())
