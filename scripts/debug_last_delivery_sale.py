from __future__ import annotations

import sys
from pathlib import Path

# Permite ejecutar este script directamente desde /scripts
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import select

from src.admin_app.db import make_engine, make_session_factory
from src.admin_app.models import Delivery, DeliveryZone, Order, Sale
from src.admin_app.repository import get_bcv_rate


def main() -> None:
    engine = make_engine()
    Session = make_session_factory(engine)

    with Session() as session:
        deliveries = (
            session.execute(select(Delivery).order_by(Delivery.id.desc()).limit(20))
            .scalars()
            .all()
        )
        print(f"Last deliveries: {len(deliveries)}")
        for d in deliveries:
            print(
                "DEL",
                d.id,
                "order_id=",
                d.order_id,
                "payment_source=",
                getattr(d, "payment_source", None),
                "amount_bs=",
                getattr(d, "amount_bs", None),
            )

            zone_price = None
            if getattr(d, "zone_id", None):
                zone = session.get(DeliveryZone, d.zone_id)
                zone_price = getattr(zone, "price", None) if zone else None
            rate = get_bcv_rate() or 0.0
            usd_from_amount = (float(getattr(d, "amount_bs", 0.0) or 0.0) / rate) if rate else None
            print("  zone_price_usd=", zone_price, "bcv_rate=", rate or None, "usd_from_amount_bs=", usd_from_amount)
            if not d.order_id:
                continue
            order = session.get(Order, d.order_id)
            print(
                "  order",
                getattr(order, "order_number", None) if order else None,
                "sale_id=",
                getattr(order, "sale_id", None) if order else None,
            )
            if not order or not order.sale_id:
                continue
            sale = session.get(Sale, order.sale_id)
            if not sale:
                continue
            print(
                "  sale",
                sale.id,
                "venta_usd=",
                getattr(sale, "venta_usd", None),
                "delivery_usd=",
                getattr(sale, "delivery_usd", None),
                "abono_usd=",
                getattr(sale, "abono_usd", None),
            )


if __name__ == "__main__":
    main()
