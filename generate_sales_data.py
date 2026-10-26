import json
import random
import subprocess
from datetime import datetime, timedelta
from faker import Faker
from simple_salesforce import Salesforce

# 1. Retrieve active authenticated session from Salesforce CLI
try:
    cli_out = subprocess.check_output(
        ["sf", "org", "display", "--target-org", "salesforce_ai", "--json"]
    )
    sf_data = json.loads(cli_out)["result"]
    sf = Salesforce(
        instance_url=sf_data["instanceUrl"],
        session_id=sf_data["accessToken"]
    )
except Exception as e:
    raise SystemExit(f"CRITICAL: Failed to load CLI session: {e}")

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

# 2. Accounts
account_staging = []
account_metadata = []

for _ in range(NUM_ACCOUNTS):
    region = random.choice(list(GEOGRAPHIES.keys()))
    state_code = random.choice(GEOGRAPHIES[region])
    country = "USA" if "North America" in region else state_code

    payload = {
        "Name": fake.company()[:80],
        "Industry": random.choice(["Technology", "Healthcare", "Finance", "Manufacturing", "Retail"]),
        "BillingStreet": fake.street_address(),
        "BillingCity": fake.city(),
        "BillingState": state_code if country == "USA" else "",
        "BillingPostalCode": fake.zipcode() if country == "USA" else fake.postcode()[:20],
        "BillingCountry": country,
        "AnnualRevenue": round(random.uniform(1000000, 80000000), 2),
        "NumberOfEmployees": random.randint(50, 4000),
    }
    account_staging.append(payload)
    account_metadata.append({"region": region, "state": state_code, "country": country})

account_results = sf.bulk.Account.insert(account_staging)

valid_accounts = [
    {"id": res["id"], "region": account_metadata[i]["region"]}
    for i, res in enumerate(account_results)
    if res.get("success")
]

if not valid_accounts:
    raise SystemExit("CRITICAL: Zero accounts created.")

# 3. Opportunities
opportunity_staging = []

for acc in valid_accounts:
    for _ in range(random.randint(*OPPS_PER_ACCOUNT_RANGE)):
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
            f"Region:{acc['region']}|"
            f"Family:{primary_product['family']}|"
            f"Product:{primary_product['name']}|"
            f"Cost:{deal_cost:.2f}|"
            f"Profit:{gross_profit:.2f}|"
            f"Margin:{margin_pct:.2f}%"
        )

        opportunity_staging.append({
            "AccountId": acc["id"],
            "Name": f"{primary_product['name']} - {acc['region']}"[:120],
            "StageName": stage_name,
            "Probability": int(probability * 100),
            "Amount": deal_amount,
            "CloseDate": deal_date.strftime("%Y-%m-%d"),
            "LeadSource": random.choice(["Inbound Web", "Direct Outbound", "Partner Referral", "Field Event"]),
            "Description": description
        })

opp_results = sf.bulk.Opportunity.insert(opportunity_staging)
successful_opps = sum(1 for r in opp_results if r.get("success"))

print(f"Loaded {len(valid_accounts)} Accounts and {successful_opps} Opportunities.")