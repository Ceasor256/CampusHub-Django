"""Platform settings stored in the database (PlatformSetting). Changes are audited."""

from dataclasses import asdict, dataclass, field

from core.models import PlatformSetting
from core.utils import audit


@dataclass
class CommissionSettings:
    # Master switch: off until a verified payment integration is live.
    enabled: bool = False
    # Basis points per module (100 bps = 1%).
    rates: dict = field(default_factory=lambda: {"marketplace": 500, "gigs": 1000})


def get_commissions() -> CommissionSettings:
    row = PlatformSetting.objects.filter(key="commissions").first()
    v = row.value if row else {}
    base = CommissionSettings()
    return CommissionSettings(enabled=bool(v.get("enabled", base.enabled)), rates={**base.rates, **v.get("rates", {})})


def save_commissions(actor, new: CommissionSettings):
    before = asdict(get_commissions())
    PlatformSetting.objects.update_or_create(key="commissions", defaults={"value": asdict(new), "updated_by": actor})
    audit(actor, "settings.commissions.update", "setting", "commissions", {"before": before, "after": asdict(new)})
