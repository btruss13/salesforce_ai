import csv
import json
import random
import uuid
from datetime import datetime, timedelta
from faker import Faker

fake = Faker()

NUM_ACCOUNTS = 40
OPPS_PER_ACCOUNT_RANGE = (2, 5)
START_DATE = datetime.now() - timedelta(days=3 * 365)
END_DATE = datetime.now()
TIME_SPAN_SECONDS = int((END_DATE - START_DATE).total_seconds())

GEOGRAPHIES = {
    "North America - East": ["NY", "MA", "PA", "NJ", "FL", "GA"],
    "North America - Central": ["IL", "OH", "MI", "TX", "MN", "WI"],
    "North America - West": ["CA", "WA", "OR", "CO", "AZ", "UT"],
    "Europe": ["GB", "DE", "FR", "NL", "IE"],
}

PRODUCT_CATALOG = [
    {"family": "Software", "name": "Cloud Analytics Platform", "base_cost": 12000.0, "price_range": (18000.0, 30000.0)},
    {"family": "Software", "name": "Enterprise Connector Suite", "base_cost": 4000.0, "price_range": (7000.0, 15000.0)},
    {"family": "Hardware", "name": "Edge Compute Gateway", "base_cost": 2500.0, "price_range": (3500.0, 6000.0)},
    {"family": "Hardware", "name": "Telemetry Sensor Pack", "base_cost": 800.0, "price_range": (1200.0, 2200.0)},
    {"family": "Services", "name": "Implementation Retainer", "base_cost": 15000.0, "price_range": (20000.0, 35000.0)},
    {"family": "Services", "name": "Managed Operations SLA", "base_cost": 6000.0, "price_range": (9000.0, 18000.0)},
]

STAGES = [
    ("Prospecting", 0.10),
    ("Qualification", 0.25),
    ("Proposal/Price Quote", 0.75),
    ("Closed Won", 1.00),
]

accounts = []
opportunities = []

print("Generating synthetic Accounts and Opportunities...")

for _ in range(NUM_ACCOUNTS):
    account_id = f"001{uuid.uuid4().hex[:15]}"
    region = random.choice(list(GEOGRAPHIES.keys()))
    state_code = random.choice(GEOGRAPHIES[region])
    country = "USA" if "North America" in region else state_code

    account_row = {
        "id": account_id,
        "name": fake.company()[:80],
        "industry": random.choice(["Technology", "Healthcare", "Finance", "Manufacturing", "Retail"]),
        "billing_street": fake.street_address(),
        "billing_city": fake.city(),
        "billing_state": state_code if country == "USA" else "",
        "billing_postal_code": fake.zipcode() if country == "USA" else fake.postcode()[:20],
        "billing_country": country,
        "annual_revenue": round(random.uniform(1000000, 80000000), 2),
        "number_of_employees": random.randint(50, 4000),
        "created_date": START_DATE.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "_fivetran_synced": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    accounts.append(account_row)

    for _ in range(random.randint(*OPPS_PER_ACCOUNT_RANGE)):
        opp_id = f"006{uuid.uuid4().hex[:15]}"
        selected_products = random.sample(PRODUCT_CATALOG, k=random.randint(1, 3))
        deal_amount = 0.0
        deal_cost = 0.0

        for prod in selected_products:
            unit_price = random.uniform(*prod["price_range"])
            unit_cost = prod["base_cost"] * random.uniform(0.9, 1.1)
            qty = random.randint(1, 4)
            deal_amount += (unit_price * qty)
            deal_cost += (unit_cost * qty)

        deal_amount = max(round(deal_amount, 2), 1.0)
        deal_cost = round(deal_cost, 2)
        gross_profit = round(deal_amount - deal_cost, 2)
        margin_pct = round((gross_profit / deal_amount) * 100, 2)

        deal_date = START_DATE + timedelta(seconds=random.randint(0, TIME_SPAN_SECONDS))

        if deal_date < (datetime.now() - timedelta(days=60)):
            stage_name, probability = ("Closed Won", 1.00)
        else:
            stage_name, probability = random.choice(STAGES)

        primary_product = selected_products[0]

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
            "lead_source": random.choice(["Inbound Web", "Direct Outbound", "Partner Referral", "Field Event"]),
            "description": description,
            "created_date": deal_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "_fivetran_synced": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        })

# Export to CSV
with open("salesforce_account.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=accounts[0].keys())
    writer.writeheader()
    writer.writerows(accounts)

with open("salesforce_opportunity.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=opportunities[0].keys())
    writer.writeheader()
    writer.writerows(opportunities)

# Export to NDJSON for BigQuery load
with open("salesforce_account.ndjson", "w", encoding="utf-8") as f:
    for row in accounts:
        f.write(json.dumps(row) + "\n")

with open("salesforce_opportunity.ndjson", "w", encoding="utf-8") as f:
    for row in opportunities:
        f.write(json.dumps(row) + "\n")

print(f"Generated {len(accounts)} Accounts and {len(opportunities)} Opportunities.")
print("Created files: salesforce_account.csv, salesforce_opportunity.csv, salesforce_account.ndjson, salesforce_opportunity.ndjson")