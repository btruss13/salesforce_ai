import csv
import json
import random
import uuid
from datetime import datetime, timedelta
from faker import Faker

fake = Faker()

NUM_ACCOUNTS = 500
OPPS_PER_ACCOUNT_RANGE = (8, 16)

# 3-Year Historical Window
END_DATE = datetime.now()
START_DATE = END_DATE - timedelta(days=3 * 365)
TOTAL_DAYS = (END_DATE - START_DATE).days

GEOGRAPHIES = {
    "North America - East": ["NY", "MA", "PA", "NJ", "FL", "GA"],
    "North America - Central": ["IL", "OH", "MI", "TX", "MN", "WI"],
    "North America - West": ["CA", "WA", "OR", "CO", "AZ", "UT"],
    "Europe": ["GB", "DE", "FR", "NL", "IE"],
}

INDUSTRIES = [
    "Technology", "Healthcare", "Finance", "Manufacturing", 
    "Retail", "Telecommunications", "Energy", "Transportation"
]

PRODUCT_CATALOG = [
    {"family": "Software", "name": "Cloud Analytics Platform", "base_cost": 12000.0, "price_range": (18000.0, 32000.0)},
    {"family": "Software", "name": "Enterprise Connector Suite", "base_cost": 4000.0, "price_range": (6500.0, 14000.0)},
    {"family": "Hardware", "name": "Edge Compute Gateway", "base_cost": 2500.0, "price_range": (3800.0, 6200.0)},
    {"family": "Hardware", "name": "Telemetry Sensor Pack", "base_cost": 800.0, "price_range": (1200.0, 2400.0)},
    {"family": "Services", "name": "Implementation Retainer", "base_cost": 15000.0, "price_range": (20000.0, 38000.0)},
    {"family": "Services", "name": "Managed Operations SLA", "base_cost": 6000.0, "price_range": (8500.0, 17500.0)},
]

STAGES = [
    ("Prospecting", 0.10),
    ("Qualification", 0.25),
    ("Needs Analysis", 0.40),
    ("Value Proposition", 0.50),
    ("Proposal/Price Quote", 0.75),
    ("Negotiation/Review", 0.90),
    ("Closed Won", 1.00),
    ("Closed Lost", 0.00),
]

LEAD_SOURCES = ["Inbound Web", "Direct Outbound", "Partner Referral", "Field Event", "Organic Search"]

accounts = []
opportunities = []

print(f"Generating 3 years of dimensional sales data ({NUM_ACCOUNTS} accounts)...")

for i in range(NUM_ACCOUNTS):
    account_id = f"001{uuid.uuid4().hex[:15]}"
    region = random.choice(list(GEOGRAPHIES.keys()))
    state_code = random.choice(GEOGRAPHIES[region])
    country = "USA" if "North America" in region else state_code

    # Stagger account onboard dates across the 3-year timeline
    account_created_offset = random.randint(0, int(TOTAL_DAYS * 0.7))
    account_created_date = START_DATE + timedelta(days=account_created_offset)

    account_row = {
        "id": account_id,
        "name": fake.company()[:80],
        "industry": random.choice(INDUSTRIES),
        "billing_street": fake.street_address(),
        "billing_city": fake.city(),
        "billing_state": state_code if country == "USA" else "",
        "billing_postal_code": fake.zipcode() if country == "USA" else fake.postcode()[:20],
        "billing_country": country,
        "annual_revenue": round(random.uniform(750000, 120000000), 2),
        "number_of_employees": random.randint(25, 8000),
        "created_date": account_created_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "_fivetran_synced": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    accounts.append(account_row)

    num_opps = random.randint(*OPPS_PER_ACCOUNT_RANGE)
    remaining_days = (END_DATE - account_created_date).days

    for _ in range(num_opps):
        opp_id = f"006{uuid.uuid4().hex[:15]}"
        
        # Select 1 to 3 catalog items to compose deal
        selected_products = random.sample(PRODUCT_CATALOG, k=random.randint(1, 3))
        deal_amount = 0.0
        deal_cost = 0.0

        for prod in selected_products:
            unit_price = random.uniform(*prod["price_range"])
            unit_cost = prod["base_cost"] * random.uniform(0.88, 1.12)
            qty = random.randint(1, 5)
            deal_amount += (unit_price * qty)
            deal_cost += (unit_cost * qty)

        deal_amount = max(round(deal_amount, 2), 100.0)
        deal_cost = round(deal_cost, 2)
        gross_profit = round(deal_amount - deal_cost, 2)
        margin_pct = round((gross_profit / deal_amount) * 100, 2)

        # Distribute opportunities across the account's active lifespan
        day_offset = random.randint(0, max(remaining_days, 1))
        deal_date = account_created_date + timedelta(days=day_offset)

        # Stage logic: Older deals resolve to Won/Lost; recent deals may still be open
        days_ago = (END_DATE - deal_date).days
        if days_ago > 90:
            stage_name, probability = random.choices(
                [("Closed Won", 1.00), ("Closed Lost", 0.00)],
                weights=[0.68, 0.32],
                k=1
            )[0]
        else:
            stage_name, probability = random.choices(
                STAGES,
                weights=[0.08, 0.12, 0.15, 0.15, 0.15, 0.10, 0.20, 0.05],
                k=1
            )[0]

        primary_product = selected_products[0]

        # Exact regex delimiter structure expected by Dataform
        description = (
            f"Region:{region}|"
            f"Family:{primary_product['family']}|"
            f"Product:{primary_product['name']}|"
            f"Cost:{deal_cost:.2f}|"
            f"Profit:{gross_profit:.2f}|"
            f"Margin:{margin_pct:.2f}%"
        )

        opportunities.append({
            "id": opp_id,
            "account_id": account_id,
            "name": f"{primary_product['name']} - {region}"[:120],
            "stage_name": stage_name,
            "probability": int(probability * 100),
            "amount": deal_amount,
            "close_date": deal_date.strftime("%Y-%m-%d"),
            "lead_source": random.choice(LEAD_SOURCES),
            "description": description,
            "created_date": deal_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "_fivetran_synced": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        })

# Export NDJSON for BigQuery load
with open("salesforce_account.ndjson", "w", encoding="utf-8") as f:
    for row in accounts:
        f.write(json.dumps(row) + "\n")

with open("salesforce_opportunity.ndjson", "w", encoding="utf-8") as f:
    for row in opportunities:
        f.write(json.dumps(row) + "\n")

# Export CSV backup
with open("salesforce_account.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=accounts[0].keys())
    writer.writeheader()
    writer.writerows(accounts)

with open("salesforce_opportunity.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=opportunities[0].keys())
    writer.writeheader()
    writer.writerows(opportunities)

print(f"\nGeneration Complete:")
print(f"- Accounts: {len(accounts):,}")
print(f"- Opportunities: {len(opportunities):,}")
print(f"- Date Range: {START_DATE.strftime('%Y-%m-%d')} to {END_DATE.strftime('%Y-%m-%d')}")