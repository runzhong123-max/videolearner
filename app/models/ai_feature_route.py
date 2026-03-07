from dataclasses import dataclass
from datetime import datetime


@dataclass
class AIFeatureRoute:
    feature_name: str
    provider: str
    updated_at: datetime
