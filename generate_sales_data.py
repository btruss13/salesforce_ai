import os
import random
from datetime import datetime, timedelta
from faker import Faker
from simple_salesforce import Salesforce

fake = Faker()

sf = Salesforce(
    username=os.getenv("SF_USERNAME"),
    password=os.getenv("SF_PASSWORD"),
    security_token=os.getenv("SF_SECURITY_TOKEN"),
    domain="login"  # Developer Edition uses login.salesforce.com
)

# Configuration
NUM_ACCOUNTS = 40
OPPS_PER_ACCOUNT_RANGE = (2, 6)
START_DATE = datetime.now() - timedelta(days=3 * 365)  # 3-year history
END_DATE = datetime.now()

# Geographic Regions with State Mapping
GEOGRAPHIES = {
    "North America - East": ["NY", "MA", "PA", "NJ", "FL", "GA"],
    "North America - Central": ["IL", "OH", "MI", "TX", "MN", "WI"],
    "North America - West": ["CA", "WA", "OR", "CO", "AZ", "UT"],
    "Europe": ["GB", "DE", "FR", "NL", "IE"],
}

# Product Catalog with Base Unit Costs and Price Ranges
PRODUCT_CATALOG = [
    {"family": "Software", "name": "Cloud Analytics Platform", "base_cost": 12000, "price_range": (18000, 30000)},
    {"family": "Software", "name": "Enterprise Connector Suite", "base_cost": 4000, "price_range": (7000, 15000)},
    {"family": "Hardware", "name": "Edge Compute Gateway", "base_cost": 2500, "price_range": (3500, 6000)},
    {"family": "Hardware", "name": "Telemetry Sensor Pack", "base_cost": 800, "price_range": (1200, 2200)},
    {"family": "Services", "name": "Implementation Retainer", "base_cost": 15000, "price_range": (20000, 35000)},
    {"family": "Services", "name": "Managed Operations SLA", "base_cost": 6000, "price_range": (9000, 18000)},
]

STAGES = [
    ("Prospecting", 0.10, False, False),
    ("Qualification", 0.25, False, False),
    ("Proposal/Price Quote", 0.75, False, False),
    ("Closed Won", 1.00, True, True),
    ("Closed Lost", 0.00, True, False),
]

created_accounts = []

print(f"Generating {NUM_ACCOUNTS} diversified accounts...")

for _ in range(NUM_ACCOUNTS):
    region = random.choice(list(GEOGRAPHIES.keys()))
    state_code = random.choice(GEOGRAPHIES[region])
    country = "USA" if "North America" in region else state_code

    account_payload = {
        "Name": fake.company(),
        "Industry": random.choice(["Technology", "Healthcare", "Finance", "Manufacturing", "Retail"]),
        "BillingStreet": fake.street_address(),
        "BillingCity": fake.city(),
        "BillingState": state_code if country == "USA" else "",
        "BillingPostalCode": fake.zipcode() if country == "USA" else fake.postcode(),
        "BillingCountry": country,
        "AnnualRevenue": round(random.uniform(1000000, 80000000), 2),
        "NumberOfEmployees": random.randint(50, 4000),
    }

    res = sf.Account.create(account_payload)
    if res.get("success"):
        created_accounts.append({
            "id": res.get("id"),
            "region": region,
            "state": state_code,
            "country": country
        })

print(f"Created {len(created_accounts)} accounts. Generating 3-year multi-product opportunities...")

total_opps = 0

for acc in created_accounts:
    num_opps = random.randint(*OPPS_PER_ACCOUNT_RANGE)
    for _ in range(num_opps):
        # Pick 1-3 distinct products for this transaction
        selected_products = random.sample(PRODUCT_CATALOG, k=random.randint(1, 3))
        
        deal_amount = 0.0
        deal_cost = 0.0
        
        for prod in selected_products:
            unit_price = random.uniform(*prod["price_range"])
            unit_cost = prod["base_cost"] * random.uniform(0.9, 1.1)  # small cost variance
            qty = random.randint(1, 4)
            deal_amount += (unit_price * qty)
            deal_cost += (unit_cost * qty)

        deal_amount = round(deal_amount, 2)
        deal_cost = round(deal_cost, 2)
        gross_profit = round(deal_amount - deal_cost, 2)
        margin_pct = round((gross_profit / deal_amount) * 100, 2)

        # Distribute randomly over the past 3 years
        random_seconds = random.randint(0, int((END_DATE - START_DATE).total_seconds()))
        deal_date = START_DATE + timedelta(seconds=random_seconds)

        # Older deals are resolved; recent deals may be open
        if deal_date < (datetime.now() - timedelta(days=60)):
            stage_name, probability, is_closed, is_won = random.choice([
                ("Closed Won", 1.00, True, True),
                ("Closed Won", 1.00, True, True),  # Weight towards Won
                ("Closed Lost", 0.00, True, False)
            ])
        else:
            stage_name, probability, is_closed, is_won = random.choice(STAGES)

        primary_product = selected_products[0]

        opp_payload = {
            "AccountId": acc["id"],
            "Name": f"{primary_product['name']} - {acc['region']}",
            "StageName": stage_name,
            "Probability": int(probability * 100),
            "Amount": deal_amount,
            "CloseDate": deal_date.strftime("%Y-%m-%d"),
            "LeadSource": random.choice(["Inbound Web", "Direct Outbound", "Partner Referral", "Field Event"]),
            # Store granular margin & product details in standard Description field for BigQuery parsing
            "Description": (
                f"Product Family: {primary_product['family']} | "
                f"Primary Product: {primary_product['name']} | "
                f"Cost: {deal_cost} | "
                f"Gross Profit: {gross_profit} | "
                f"Margin Pct: {margin_pct}% | "
                f"Region: {acc['region']}"
            )
        }

        res = sf.Opportunity.create(opp_payload)
        if res.get("success"):
            total_opps += 1

print(f"Complete. Created {len(created_accounts)} accounts and {total_opps} opportunities spanning 3 years.")