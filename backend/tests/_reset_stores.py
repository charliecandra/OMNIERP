"""Reset all store credentials/status to pristine seeded state."""
import sys
sys.path.insert(0, "/app/backend")
from database import SessionLocal
from models import Store

TOKENS = {1: "sh_main_token", 2: "sh_out_token", 3: "tt_flag_token", 4: "tt_live_token"}
db = SessionLocal()
for s in db.query(Store).all():
    s.partner_id = None
    s.partner_key = None
    s.shop_id = None
    s.connection_status = "disconnected"
    s.last_verified_at = None
    if s.id in TOKENS:
        s.access_token = TOKENS[s.id]
db.commit()
for s in db.query(Store).all():
    print(s.id, s.platform_name, s.partner_id, s.shop_id, s.connection_status, s.access_token)
db.close()
