import sys
sys.path.insert(0, '.')

from app.core.database import SessionLocal
from app.models.models import ContentItem

db = SessionLocal()
items = db.query(ContentItem).limit(15).all()
print("Content items with confidence:")
for item in items:
    print(f"  title={item.title[:40]}, confidence={repr(item.confidence)}, direction={repr(item.direction)}")

# Also check if API returns these values correctly
from app.schemas.schemas import ContentItemResponse
from app.models.models import Confidence
print("\nConfidence enum values:")
for c in Confidence:
    print(f"  {c.name} = {c.value}")
db.close()
