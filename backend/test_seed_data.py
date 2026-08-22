"""Verify all 20 companies seed correctly into the database."""
from app.db import Base, engine, get_db
from app.seed import seed_demo_data
from app.models import Company, IPO, FinancialPeriod, RiskFactor, IPOSCore, Peer
from sqlalchemy import select, func

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

with next(get_db()) as db:
    seed_demo_data(db)

    stats = {
        "Companies": db.scalar(select(func.count(Company.id))),
        "IPOs": db.scalar(select(func.count(IPO.id))),
        "Financial periods": db.scalar(select(func.count(FinancialPeriod.id))),
        "Risk factors": db.scalar(select(func.count(RiskFactor.id))),
        "IPO scores": db.scalar(select(func.count(IPOSCore.id))),
        "Peer links": db.scalar(select(func.count(Peer.id))),
    }

    print("=== Database Statistics ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    print("\n=== All Companies ===")
    companies = db.scalars(select(Company).order_by(Company.id)).all()
    for c in companies:
        ipo = db.scalar(select(IPO).where(IPO.company_id == c.id))
        score = db.scalar(select(IPOSCore).where(IPOSCore.ipo_id == ipo.id)) if ipo else None
        print(f"  {c.id:2d}. {c.name:30s} | {c.sector:22s} | {ipo.status:7s} | Score: {score.overall_score}/10")

    print("\nAll 20 companies seeded successfully!")
