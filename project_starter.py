import pandas as pd
import numpy as np
import os
import re
import sys
import time
import dotenv
import ast
from sqlalchemy.sql import text
from datetime import datetime, timedelta
from typing import Dict, List, Union
from sqlalchemy import create_engine, Engine

# Regex to strip ANSI escape codes (colors, bold, etc.) from text
ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*m|\x1b\[[\d;]*[A-Za-z]')


class TeeOutput:
    """Writes to both terminal (with colors) and a clean log file (no ANSI codes)."""
    def __init__(self, log_path):
        self.terminal = sys.stdout
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        self.log_file = open(log_path, "w", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        clean = ANSI_ESCAPE.sub("", message)
        self.log_file.write(clean)
        self.log_file.flush()

    def flush(self):
        self.terminal.flush()
        self.log_file.flush()

    def close(self):
        self.log_file.close()
        sys.stdout = self.terminal

# Create an SQLite database
db_engine = create_engine("sqlite:///munder_difflin.db")

# List containing the different kinds of papers 
paper_supplies = [
    # Paper Types (priced per sheet unless specified)
    {"item_name": "A4 paper",                         "category": "paper",        "unit_price": 0.05},
    {"item_name": "Letter-sized paper",              "category": "paper",        "unit_price": 0.06},
    {"item_name": "Cardstock",                        "category": "paper",        "unit_price": 0.15},
    {"item_name": "Colored paper",                    "category": "paper",        "unit_price": 0.10},
    {"item_name": "Glossy paper",                     "category": "paper",        "unit_price": 0.20},
    {"item_name": "Matte paper",                      "category": "paper",        "unit_price": 0.18},
    {"item_name": "Recycled paper",                   "category": "paper",        "unit_price": 0.08},
    {"item_name": "Eco-friendly paper",               "category": "paper",        "unit_price": 0.12},
    {"item_name": "Poster paper",                     "category": "paper",        "unit_price": 0.25},
    {"item_name": "Banner paper",                     "category": "paper",        "unit_price": 0.30},
    {"item_name": "Kraft paper",                      "category": "paper",        "unit_price": 0.10},
    {"item_name": "Construction paper",               "category": "paper",        "unit_price": 0.07},
    {"item_name": "Wrapping paper",                   "category": "paper",        "unit_price": 0.15},
    {"item_name": "Glitter paper",                    "category": "paper",        "unit_price": 0.22},
    {"item_name": "Decorative paper",                 "category": "paper",        "unit_price": 0.18},
    {"item_name": "Letterhead paper",                 "category": "paper",        "unit_price": 0.12},
    {"item_name": "Legal-size paper",                 "category": "paper",        "unit_price": 0.08},
    {"item_name": "Crepe paper",                      "category": "paper",        "unit_price": 0.05},
    {"item_name": "Photo paper",                      "category": "paper",        "unit_price": 0.25},
    {"item_name": "Uncoated paper",                   "category": "paper",        "unit_price": 0.06},
    {"item_name": "Butcher paper",                    "category": "paper",        "unit_price": 0.10},
    {"item_name": "Heavyweight paper",                "category": "paper",        "unit_price": 0.20},
    {"item_name": "Standard copy paper",              "category": "paper",        "unit_price": 0.04},
    {"item_name": "Bright-colored paper",             "category": "paper",        "unit_price": 0.12},
    {"item_name": "Patterned paper",                  "category": "paper",        "unit_price": 0.15},

    # Product Types (priced per unit)
    {"item_name": "Paper plates",                     "category": "product",      "unit_price": 0.10},  # per plate
    {"item_name": "Paper cups",                       "category": "product",      "unit_price": 0.08},  # per cup
    {"item_name": "Paper napkins",                    "category": "product",      "unit_price": 0.02},  # per napkin
    {"item_name": "Disposable cups",                  "category": "product",      "unit_price": 0.10},  # per cup
    {"item_name": "Table covers",                     "category": "product",      "unit_price": 1.50},  # per cover
    {"item_name": "Envelopes",                        "category": "product",      "unit_price": 0.05},  # per envelope
    {"item_name": "Sticky notes",                     "category": "product",      "unit_price": 0.03},  # per sheet
    {"item_name": "Notepads",                         "category": "product",      "unit_price": 2.00},  # per pad
    {"item_name": "Invitation cards",                 "category": "product",      "unit_price": 0.50},  # per card
    {"item_name": "Flyers",                           "category": "product",      "unit_price": 0.15},  # per flyer
    {"item_name": "Party streamers",                  "category": "product",      "unit_price": 0.05},  # per roll
    {"item_name": "Decorative adhesive tape (washi tape)", "category": "product", "unit_price": 0.20},  # per roll
    {"item_name": "Paper party bags",                 "category": "product",      "unit_price": 0.25},  # per bag
    {"item_name": "Name tags with lanyards",          "category": "product",      "unit_price": 0.75},  # per tag
    {"item_name": "Presentation folders",             "category": "product",      "unit_price": 0.50},  # per folder

    # Large-format items (priced per unit)
    {"item_name": "Large poster paper (24x36 inches)", "category": "large_format", "unit_price": 1.00},
    {"item_name": "Rolls of banner paper (36-inch width)", "category": "large_format", "unit_price": 2.50},

    # Specialty papers
    {"item_name": "100 lb cover stock",               "category": "specialty",    "unit_price": 0.50},
    {"item_name": "80 lb text paper",                 "category": "specialty",    "unit_price": 0.40},
    {"item_name": "250 gsm cardstock",                "category": "specialty",    "unit_price": 0.30},
    {"item_name": "220 gsm poster paper",             "category": "specialty",    "unit_price": 0.35},
]

# Given below are some utility functions you can use to implement your multi-agent system

def generate_sample_inventory(paper_supplies: list, coverage: float = 0.4, seed: int = 137) -> pd.DataFrame:
    """
    Generate inventory for exactly a specified percentage of items from the full paper supply list.

    This function randomly selects exactly `coverage` × N items from the `paper_supplies` list,
    and assigns each selected item:
    - a random stock quantity between 200 and 800,
    - a minimum stock level between 50 and 150.

    The random seed ensures reproducibility of selection and stock levels.

    Args:
        paper_supplies (list): A list of dictionaries, each representing a paper item with
                               keys 'item_name', 'category', and 'unit_price'.
        coverage (float, optional): Fraction of items to include in the inventory (default is 0.4, or 40%).
        seed (int, optional): Random seed for reproducibility (default is 137).

    Returns:
        pd.DataFrame: A DataFrame with the selected items and assigned inventory values, including:
                      - item_name
                      - category
                      - unit_price
                      - current_stock
                      - min_stock_level
    """
    # Ensure reproducible random output
    np.random.seed(seed)

    # Calculate number of items to include based on coverage
    num_items = int(len(paper_supplies) * coverage)

    # Randomly select item indices without replacement
    selected_indices = np.random.choice(
        range(len(paper_supplies)),
        size=num_items,
        replace=False
    )

    # Extract selected items from paper_supplies list
    selected_items = [paper_supplies[i] for i in selected_indices]

    # Construct inventory records
    inventory = []
    for item in selected_items:
        inventory.append({
            "item_name": item["item_name"],
            "category": item["category"],
            "unit_price": item["unit_price"],
            "current_stock": np.random.randint(200, 800),  # Realistic stock range
            "min_stock_level": np.random.randint(50, 150)  # Reasonable threshold for reordering
        })

    # Return inventory as a pandas DataFrame
    return pd.DataFrame(inventory)

def init_database(db_engine: Engine, seed: int = 137) -> Engine:    
    """
    Set up the Munder Difflin database with all required tables and initial records.

    This function performs the following tasks:
    - Creates the 'transactions' table for logging stock orders and sales
    - Loads customer inquiries from 'quote_requests.csv' into a 'quote_requests' table
    - Loads previous quotes from 'quotes.csv' into a 'quotes' table, extracting useful metadata
    - Generates a random subset of paper inventory using `generate_sample_inventory`
    - Inserts initial financial records including available cash and starting stock levels

    Args:
        db_engine (Engine): A SQLAlchemy engine connected to the SQLite database.
        seed (int, optional): A random seed used to control reproducibility of inventory stock levels.
                              Default is 137.

    Returns:
        Engine: The same SQLAlchemy engine, after initializing all necessary tables and records.

    Raises:
        Exception: If an error occurs during setup, the exception is printed and raised.
    """
    try:
        # ----------------------------
        # 1. Create an empty 'transactions' table schema
        # ----------------------------
        transactions_schema = pd.DataFrame({
            "id": [],
            "item_name": [],
            "transaction_type": [],  # 'stock_orders' or 'sales'
            "units": [],             # Quantity involved
            "price": [],             # Total price for the transaction
            "transaction_date": [],  # ISO-formatted date
        })
        transactions_schema.to_sql("transactions", db_engine, if_exists="replace", index=False)

        # Set a consistent starting date
        initial_date = datetime(2025, 1, 1).isoformat()

        # ----------------------------
        # 2. Load and initialize 'quote_requests' table
        # ----------------------------
        quote_requests_df = pd.read_csv("quote_requests.csv")
        quote_requests_df["id"] = range(1, len(quote_requests_df) + 1)
        quote_requests_df.to_sql("quote_requests", db_engine, if_exists="replace", index=False)

        # ----------------------------
        # 3. Load and transform 'quotes' table
        # ----------------------------
        quotes_df = pd.read_csv("quotes.csv")
        quotes_df["request_id"] = range(1, len(quotes_df) + 1)
        quotes_df["order_date"] = initial_date

        # Unpack metadata fields (job_type, order_size, event_type) if present
        if "request_metadata" in quotes_df.columns:
            quotes_df["request_metadata"] = quotes_df["request_metadata"].apply(
                lambda x: ast.literal_eval(x) if isinstance(x, str) else x
            )
            quotes_df["job_type"] = quotes_df["request_metadata"].apply(lambda x: x.get("job_type", ""))
            quotes_df["order_size"] = quotes_df["request_metadata"].apply(lambda x: x.get("order_size", ""))
            quotes_df["event_type"] = quotes_df["request_metadata"].apply(lambda x: x.get("event_type", ""))

        # Retain only relevant columns
        quotes_df = quotes_df[[
            "request_id",
            "total_amount",
            "quote_explanation",
            "order_date",
            "job_type",
            "order_size",
            "event_type"
        ]]
        quotes_df.to_sql("quotes", db_engine, if_exists="replace", index=False)

        # ----------------------------
        # 4. Generate inventory and seed stock
        # ----------------------------
        inventory_df = generate_sample_inventory(paper_supplies, seed=seed)

        # Seed initial transactions
        initial_transactions = []

        # Add a starting cash balance via a dummy sales transaction
        initial_transactions.append({
            "item_name": None,
            "transaction_type": "sales",
            "units": None,
            "price": 50000.0,
            "transaction_date": initial_date,
        })

        # Add one stock order transaction per inventory item
        for _, item in inventory_df.iterrows():
            initial_transactions.append({
                "item_name": item["item_name"],
                "transaction_type": "stock_orders",
                "units": item["current_stock"],
                "price": item["current_stock"] * item["unit_price"],
                "transaction_date": initial_date,
            })

        # Commit transactions to database
        pd.DataFrame(initial_transactions).to_sql("transactions", db_engine, if_exists="append", index=False)

        # Save the inventory reference table
        inventory_df.to_sql("inventory", db_engine, if_exists="replace", index=False)

        return db_engine

    except Exception as e:
        print(f"Error initializing database: {e}")
        raise

def create_transaction(
    item_name: str,
    transaction_type: str,
    quantity: int,
    price: float,
    date: Union[str, datetime],
) -> int:
    """
    This function records a transaction of type 'stock_orders' or 'sales' with a specified
    item name, quantity, total price, and transaction date into the 'transactions' table of the database.

    Args:
        item_name (str): The name of the item involved in the transaction.
        transaction_type (str): Either 'stock_orders' or 'sales'.
        quantity (int): Number of units involved in the transaction.
        price (float): Total price of the transaction.
        date (str or datetime): Date of the transaction in ISO 8601 format.

    Returns:
        int: The ID of the newly inserted transaction.

    Raises:
        ValueError: If `transaction_type` is not 'stock_orders' or 'sales'.
        Exception: For other database or execution errors.
    """
    try:
        # Convert datetime to ISO string if necessary
        date_str = date.isoformat() if isinstance(date, datetime) else date

        # Validate transaction type
        if transaction_type not in {"stock_orders", "sales"}:
            raise ValueError("Transaction type must be 'stock_orders' or 'sales'")

        # Prepare transaction record as a single-row DataFrame
        transaction = pd.DataFrame([{
            "item_name": item_name,
            "transaction_type": transaction_type,
            "units": quantity,
            "price": price,
            "transaction_date": date_str,
        }])

        # Insert the record into the database
        transaction.to_sql("transactions", db_engine, if_exists="append", index=False)

        # Fetch and return the ID of the inserted row
        result = pd.read_sql("SELECT last_insert_rowid() as id", db_engine)
        return int(result.iloc[0]["id"])

    except Exception as e:
        print(f"Error creating transaction: {e}")
        raise

def get_all_inventory(as_of_date: str) -> Dict[str, int]:
    """
    Retrieve a snapshot of available inventory as of a specific date.

    This function calculates the net quantity of each item by summing 
    all stock orders and subtracting all sales up to and including the given date.

    Only items with positive stock are included in the result.

    Args:
        as_of_date (str): ISO-formatted date string (YYYY-MM-DD) representing the inventory cutoff.

    Returns:
        Dict[str, int]: A dictionary mapping item names to their current stock levels.
    """
    # SQL query to compute stock levels per item as of the given date
    query = """
        SELECT
            item_name,
            SUM(CASE
                WHEN transaction_type = 'stock_orders' THEN units
                WHEN transaction_type = 'sales' THEN -units
                ELSE 0
            END) as stock
        FROM transactions
        WHERE item_name IS NOT NULL
        AND transaction_date <= :as_of_date
        GROUP BY item_name
        HAVING stock > 0
    """

    # Execute the query with the date parameter
    result = pd.read_sql(query, db_engine, params={"as_of_date": as_of_date})

    # Convert the result into a dictionary {item_name: stock}
    return dict(zip(result["item_name"], result["stock"]))

def get_stock_level(item_name: str, as_of_date: Union[str, datetime]) -> pd.DataFrame:
    """
    Retrieve the stock level of a specific item as of a given date.

    This function calculates the net stock by summing all 'stock_orders' and 
    subtracting all 'sales' transactions for the specified item up to the given date.

    Args:
        item_name (str): The name of the item to look up.
        as_of_date (str or datetime): The cutoff date (inclusive) for calculating stock.

    Returns:
        pd.DataFrame: A single-row DataFrame with columns 'item_name' and 'current_stock'.
    """
    # Convert date to ISO string format if it's a datetime object
    if isinstance(as_of_date, datetime):
        as_of_date = as_of_date.isoformat()

    # SQL query to compute net stock level for the item
    stock_query = """
        SELECT
            item_name,
            COALESCE(SUM(CASE
                WHEN transaction_type = 'stock_orders' THEN units
                WHEN transaction_type = 'sales' THEN -units
                ELSE 0
            END), 0) AS current_stock
        FROM transactions
        WHERE item_name = :item_name
        AND transaction_date <= :as_of_date
    """

    # Execute query and return result as a DataFrame
    return pd.read_sql(
        stock_query,
        db_engine,
        params={"item_name": item_name, "as_of_date": as_of_date},
    )

def get_supplier_delivery_date(input_date_str: str, quantity: int) -> str:
    """
    Estimate the supplier delivery date based on the requested order quantity and a starting date.

    Delivery lead time increases with order size:
        - ≤10 units: same day
        - 11–100 units: 1 day
        - 101–1000 units: 4 days
        - >1000 units: 7 days

    Args:
        input_date_str (str): The starting date in ISO format (YYYY-MM-DD).
        quantity (int): The number of units in the order.

    Returns:
        str: Estimated delivery date in ISO format (YYYY-MM-DD).
    """
    # Debug log (comment out in production if needed)
    print(f"FUNC (get_supplier_delivery_date): Calculating for qty {quantity} from date string '{input_date_str}'")

    # Attempt to parse the input date
    try:
        input_date_dt = datetime.fromisoformat(input_date_str.split("T")[0])
    except (ValueError, TypeError):
        # Fallback to current date on format error
        print(f"WARN (get_supplier_delivery_date): Invalid date format '{input_date_str}', using today as base.")
        input_date_dt = datetime.now()

    # Determine delivery delay based on quantity
    if quantity <= 10:
        days = 0
    elif quantity <= 100:
        days = 1
    elif quantity <= 1000:
        days = 4
    else:
        days = 7

    # Add delivery days to the starting date
    delivery_date_dt = input_date_dt + timedelta(days=days)

    # Return formatted delivery date
    return delivery_date_dt.strftime("%Y-%m-%d")

def get_cash_balance(as_of_date: Union[str, datetime]) -> float:
    """
    Calculate the current cash balance as of a specified date.

    The balance is computed by subtracting total stock purchase costs ('stock_orders')
    from total revenue ('sales') recorded in the transactions table up to the given date.

    Args:
        as_of_date (str or datetime): The cutoff date (inclusive) in ISO format or as a datetime object.

    Returns:
        float: Net cash balance as of the given date. Returns 0.0 if no transactions exist or an error occurs.
    """
    try:
        # Convert date to ISO format if it's a datetime object
        if isinstance(as_of_date, datetime):
            as_of_date = as_of_date.isoformat()

        # Query all transactions on or before the specified date
        transactions = pd.read_sql(
            "SELECT * FROM transactions WHERE transaction_date <= :as_of_date",
            db_engine,
            params={"as_of_date": as_of_date},
        )

        # Compute the difference between sales and stock purchases
        if not transactions.empty:
            total_sales = transactions.loc[transactions["transaction_type"] == "sales", "price"].sum()
            total_purchases = transactions.loc[transactions["transaction_type"] == "stock_orders", "price"].sum()
            return float(total_sales - total_purchases)

        return 0.0

    except Exception as e:
        print(f"Error getting cash balance: {e}")
        return 0.0


def generate_financial_report(as_of_date: Union[str, datetime]) -> Dict:
    """
    Generate a complete financial report for the company as of a specific date.

    This includes:
    - Cash balance
    - Inventory valuation
    - Combined asset total
    - Itemized inventory breakdown
    - Top 5 best-selling products

    Args:
        as_of_date (str or datetime): The date (inclusive) for which to generate the report.

    Returns:
        Dict: A dictionary containing the financial report fields:
            - 'as_of_date': The date of the report
            - 'cash_balance': Total cash available
            - 'inventory_value': Total value of inventory
            - 'total_assets': Combined cash and inventory value
            - 'inventory_summary': List of items with stock and valuation details
            - 'top_selling_products': List of top 5 products by revenue
    """
    # Normalize date input
    if isinstance(as_of_date, datetime):
        as_of_date = as_of_date.isoformat()

    # Get current cash balance
    cash = get_cash_balance(as_of_date)

    # Get current inventory snapshot
    inventory_df = pd.read_sql("SELECT * FROM inventory", db_engine)
    inventory_value = 0.0
    inventory_summary = []

    # Compute total inventory value and summary by item
    for _, item in inventory_df.iterrows():
        stock_info = get_stock_level(item["item_name"], as_of_date)
        stock = stock_info["current_stock"].iloc[0]
        item_value = stock * item["unit_price"]
        inventory_value += item_value

        inventory_summary.append({
            "item_name": item["item_name"],
            "stock": stock,
            "unit_price": item["unit_price"],
            "value": item_value,
        })

    # Identify top-selling products by revenue
    top_sales_query = """
        SELECT item_name, SUM(units) as total_units, SUM(price) as total_revenue
        FROM transactions
        WHERE transaction_type = 'sales' AND transaction_date <= :date
        GROUP BY item_name
        ORDER BY total_revenue DESC
        LIMIT 5
    """
    top_sales = pd.read_sql(top_sales_query, db_engine, params={"date": as_of_date})
    top_selling_products = top_sales.to_dict(orient="records")

    return {
        "as_of_date": as_of_date,
        "cash_balance": cash,
        "inventory_value": inventory_value,
        "total_assets": cash + inventory_value,
        "inventory_summary": inventory_summary,
        "top_selling_products": top_selling_products,
    }


def search_quote_history(search_terms: List[str], limit: int = 5) -> List[Dict]:
    """
    Retrieve a list of historical quotes that match any of the provided search terms.

    The function searches both the original customer request (from `quote_requests`) and
    the explanation for the quote (from `quotes`) for each keyword. Results are sorted by
    most recent order date and limited by the `limit` parameter.

    Args:
        search_terms (List[str]): List of terms to match against customer requests and explanations.
        limit (int, optional): Maximum number of quote records to return. Default is 5.

    Returns:
        List[Dict]: A list of matching quotes, each represented as a dictionary with fields:
            - original_request
            - total_amount
            - quote_explanation
            - job_type
            - order_size
            - event_type
            - order_date
    """
    conditions = []
    params = {}

    # Build SQL WHERE clause using LIKE filters for each search term
    for i, term in enumerate(search_terms):
        param_name = f"term_{i}"
        conditions.append(
            f"(LOWER(qr.response) LIKE :{param_name} OR "
            f"LOWER(q.quote_explanation) LIKE :{param_name})"
        )
        params[param_name] = f"%{term.lower()}%"

    # Combine conditions; fallback to always-true if no terms provided
    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Final SQL query to join quotes with quote_requests
    query = f"""
        SELECT
            qr.response AS original_request,
            q.total_amount,
            q.quote_explanation,
            q.job_type,
            q.order_size,
            q.event_type,
            q.order_date
        FROM quotes q
        JOIN quote_requests qr ON q.request_id = qr.id
        WHERE {where_clause}
        ORDER BY q.order_date DESC
        LIMIT {limit}
    """

    # Execute parameterized query
    with db_engine.connect() as conn:
        result = conn.execute(text(query), params)
        return [dict(row._mapping) for row in result]

########################
########################
########################
# YOUR MULTI AGENT STARTS HERE
########################
########################
########################


# Set up and load your env parameters and instantiate your model.

dotenv.load_dotenv()

api_key = os.getenv("UDACITY_OPENAI_API_KEY")
if not api_key:
    raise ValueError("Missing UDACITY_OPENAI_API_KEY in .env file")

from smolagents import OpenAIServerModel, ToolCallingAgent, CodeAgent, tool

model = OpenAIServerModel(
    model_id="gpt-4o",
    api_base="https://openai.vocareum.com/v1",
    api_key=api_key,
)

"""Set up tools for your agents to use, these should be methods that combine the database functions above
 and apply criteria to them to ensure that the flow of the system is correct."""


# Tools for inventory agent

@tool
def check_inventory(as_of_date: str) -> str:
    """Check all current inventory levels and flag items that are below minimum stock.

    Args:
        as_of_date: The date to check inventory for, in YYYY-MM-DD format.

    Returns:
        A summary of all inventory levels and any items needing restocking.
    """
    inventory = get_all_inventory(as_of_date)
    inventory_df = pd.read_sql("SELECT * FROM inventory", db_engine)
    min_levels = dict(zip(inventory_df["item_name"], inventory_df["min_stock_level"]))

    lines = ["=== Inventory Report ==="]
    low_stock = []
    for item_name, stock in inventory.items():
        min_level = min_levels.get(item_name, 0)
        status = "OK"
        if stock <= min_level:
            status = "LOW - RESTOCK NEEDED"
            low_stock.append(item_name)
        lines.append(f"  {item_name}: {stock} units (min: {min_level}) [{status}]")

    if low_stock:
        lines.append(f"\nItems needing restock: {', '.join(low_stock)}")
    else:
        lines.append("\nAll items are above minimum stock levels.")

    return "\n".join(lines)


@tool
def check_item_stock(item_name: str, as_of_date: str) -> str:
    """Check the stock level of a specific item as of a given date.

    Args:
        item_name: The exact name of the item to check (must match database names).
        as_of_date: The date to check stock for, in YYYY-MM-DD format.

    Returns:
        The current stock level and whether restocking is needed.
    """
    stock_df = get_stock_level(item_name, as_of_date)
    current_stock = int(stock_df["current_stock"].iloc[0])

    inventory_df = pd.read_sql(
        "SELECT * FROM inventory WHERE item_name = :name",
        db_engine,
        params={"name": item_name},
    )

    if inventory_df.empty:
        return f"'{item_name}' is NOT in our inventory catalog. It must be ordered from supplier first."

    min_level = int(inventory_df["min_stock_level"].iloc[0])
    unit_price = float(inventory_df["unit_price"].iloc[0])

    status = "OK" if current_stock > min_level else "LOW - RESTOCK NEEDED"
    return (
        f"Item: {item_name}\n"
        f"Current Stock: {current_stock} units\n"
        f"Min Stock Level: {min_level}\n"
        f"Unit Price: ${unit_price:.2f}\n"
        f"Status: {status}"
    )


@tool
def restock_item(item_name: str, quantity: int, date: str) -> str:
    """Order stock from the supplier for a given item. Checks cash balance before ordering.

    Args:
        item_name: The exact name of the item to restock (must match database names).
        quantity: The number of units to order from the supplier.
        date: The date of the order, in YYYY-MM-DD format.

    Returns:
        Confirmation of the restock order or an error if insufficient funds.
    """
    # Look up unit price from paper_supplies catalog
    item_info = next((p for p in paper_supplies if p["item_name"].lower() == item_name.lower()), None)
    if not item_info:
        return f"Error: '{item_name}' not found in the product catalog. Use exact item names from get_product_catalog."

    unit_price = item_info["unit_price"]
    total_cost = quantity * unit_price

    # Check if we have enough cash
    cash = get_cash_balance(date)
    if total_cost > cash:
        return f"Insufficient funds. Need ${total_cost:.2f} but only ${cash:.2f} available."

    # Get delivery date
    delivery_date = get_supplier_delivery_date(date, quantity)

    # Create the stock order transaction
    tx_id = create_transaction(item_name, "stock_orders", quantity, total_cost, date)

    return (
        f"Restock order placed!\n"
        f"Item: {item_name}\n"
        f"Quantity: {quantity} units\n"
        f"Total Cost: ${total_cost:.2f}\n"
        f"Delivery Date: {delivery_date}\n"
        f"Transaction ID: {tx_id}"
    )


# Tools for quoting agent

@tool
def search_past_quotes(search_terms: str) -> str:
    """Search historical quotes for similar past orders to use as pricing reference.

    Args:
        search_terms: Comma-separated search terms to match against past quotes (e.g. "cardstock, glossy, festival").

    Returns:
        A summary of matching historical quotes with amounts and explanations.
    """
    terms = [t.strip() for t in search_terms.split(",")]
    results = search_quote_history(terms, limit=5)

    if not results:
        return "No matching historical quotes found."

    lines = ["=== Matching Historical Quotes ==="]
    for i, q in enumerate(results, 1):
        lines.append(
            f"\n--- Quote {i} ---\n"
            f"Amount: ${q['total_amount']}\n"
            f"Job Type: {q['job_type']}\n"
            f"Order Size: {q['order_size']}\n"
            f"Event Type: {q['event_type']}\n"
            f"Explanation: {q['quote_explanation'][:200]}..."
        )

    return "\n".join(lines)


@tool
def get_product_catalog() -> str:
    """Get the full product catalog with item names, categories, and unit prices.

    Returns:
        A formatted list of all available products with their prices.
    """
    lines = ["=== Product Catalog ==="]
    for item in paper_supplies:
        lines.append(f"  {item['item_name']} ({item['category']}): ${item['unit_price']:.2f}/unit")
    return "\n".join(lines)


@tool
def calculate_quote(items_and_quantities: str, as_of_date: str) -> str:
    """Calculate a price quote for a list of items with bulk discounts applied.

    Bulk discount rules:
    - 100-499 units: 5% discount
    - 500-999 units: 10% discount
    - 1000+ units: 15% discount

    Args:
        items_and_quantities: A string of items and quantities, one per line, formatted as "item_name: quantity". Example: "A4 paper: 500\nCardstock: 200"
        as_of_date: The date of the quote, in YYYY-MM-DD format.

    Returns:
        A detailed quote breakdown with per-item costs, discounts, and total.
    """
    lines = ["=== Quote Breakdown ==="]
    total = 0.0

    for entry in items_and_quantities.strip().split("\n"):
        if ":" not in entry:
            continue
        name, qty_str = entry.rsplit(":", 1)
        name = name.strip()
        try:
            qty = int(qty_str.strip())
        except ValueError:
            lines.append(f"  {name}: INVALID QUANTITY '{qty_str.strip()}'")
            continue

        # Look up unit price
        item_info = next((p for p in paper_supplies if p["item_name"].lower() == name.lower()), None)
        if not item_info:
            lines.append(f"  {name}: NOT FOUND in catalog")
            continue

        unit_price = item_info["unit_price"]
        subtotal = qty * unit_price

        # Apply bulk discount
        if qty >= 1000:
            discount = 0.15
        elif qty >= 500:
            discount = 0.10
        elif qty >= 100:
            discount = 0.05
        else:
            discount = 0.0

        discount_amount = subtotal * discount
        item_total = subtotal - discount_amount
        total += item_total

        lines.append(
            f"  {name}: {qty} x ${unit_price:.2f} = ${subtotal:.2f}"
            + (f" (-{discount*100:.0f}% = ${item_total:.2f})" if discount > 0 else "")
        )

    lines.append(f"\nTotal Quote Amount: ${total:.2f}")
    return "\n".join(lines)


# Tools for ordering agent

@tool
def process_sale(item_name: str, quantity: int, price: float, date: str) -> str:
    """Process a sale transaction for a customer order. Records the sale in the database.

    Args:
        item_name: The exact name of the item being sold (must match database names).
        quantity: The number of units sold.
        price: The total sale price for this line item.
        date: The date of the sale, in YYYY-MM-DD format.

    Returns:
        Confirmation of the sale or an error if insufficient stock.
    """
    # Check stock first
    stock_df = get_stock_level(item_name, date)
    current_stock = int(stock_df["current_stock"].iloc[0])

    if current_stock < quantity:
        return f"Insufficient stock for '{item_name}'. Have {current_stock}, need {quantity}. Restock first."

    tx_id = create_transaction(item_name, "sales", quantity, price, date)
    return (
        f"Sale processed!\n"
        f"Item: {item_name}\n"
        f"Quantity: {quantity}\n"
        f"Sale Price: ${price:.2f}\n"
        f"Transaction ID: {tx_id}"
    )


@tool
def check_delivery_estimate(order_date: str, quantity: int) -> str:
    """Estimate the supplier delivery date based on order quantity.

    Args:
        order_date: The date the order is placed, in YYYY-MM-DD format.
        quantity: The number of units being ordered.

    Returns:
        The estimated delivery date.
    """
    delivery = get_supplier_delivery_date(order_date, quantity)
    return f"Estimated delivery date for {quantity} units ordered on {order_date}: {delivery}"


@tool
def get_balance(as_of_date: str) -> str:
    """Get the current cash balance as of a specific date.

    Args:
        as_of_date: The date to check the balance for, in YYYY-MM-DD format.

    Returns:
        The current cash balance.
    """
    cash = get_cash_balance(as_of_date)
    return f"Cash balance as of {as_of_date}: ${cash:.2f}"


@tool
def get_financial_report(as_of_date: str) -> str:
    """Generate a full financial report including cash balance, inventory value, and top selling products.

    Args:
        as_of_date: The date to generate the report for, in YYYY-MM-DD format.

    Returns:
        A formatted financial report with cash, inventory value, total assets, and top sellers.
    """
    report = generate_financial_report(as_of_date)
    lines = [
        "=== Financial Report ===",
        f"Date: {report['as_of_date']}",
        f"Cash Balance: ${report['cash_balance']:.2f}",
        f"Inventory Value: ${report['inventory_value']:.2f}",
        f"Total Assets: ${report['total_assets']:.2f}",
        "",
        "Top Selling Products:",
    ]
    for item in report["top_selling_products"]:
        lines.append(f"  {item['item_name']}: {item['total_units']} units, ${item['total_revenue']:.2f} revenue")

    return "\n".join(lines)


# Set up your agents and create an orchestration agent that will manage them.

inventory_agent = ToolCallingAgent(
    tools=[check_inventory, check_item_stock, restock_item, get_product_catalog],
    model=model,
    name="inventory_agent",
    description=(
        "Manages warehouse inventory. ALWAYS call get_product_catalog FIRST to find the exact catalog item names "
        "that match what the customer is asking for. Customers use informal names like 'A4 printer paper' but the "
        "catalog name is 'A4 paper'. Map each requested item to the closest matching catalog name. "
        "Then use check_item_stock with the EXACT catalog name to see current stock. "
        "If stock is low or zero, call restock_item with the EXACT catalog name and the DATE from the request. "
        "In your response, always list the EXACT catalog names you found so other agents can use them."
    ),
)

quoting_agent = ToolCallingAgent(
    tools=[search_past_quotes, get_product_catalog, calculate_quote],
    model=model,
    name="quoting_agent",
    description=(
        "Handles pricing and quotes. Use the EXACT catalog item names provided by inventory_agent. "
        "First call search_past_quotes for similar orders, then call calculate_quote with the exact catalog names "
        "and quantities. Always use the DATE from the customer's original request when calling calculate_quote."
    ),
)

order_agent = ToolCallingAgent(
    tools=[process_sale, check_delivery_estimate, get_balance, get_financial_report],
    model=model,
    name="order_agent",
    description=(
        "Processes sales and manages finances. Use the EXACT catalog item names and the quoted prices from "
        "quoting_agent. For each item, call process_sale with the exact catalog name, quantity, quoted price, "
        "and the DATE from the customer's original request. Also call check_delivery_estimate using the request date. "
        "IMPORTANT: Always use the date from the customer request (e.g. 2025-04-05), not any other date."
    ),
)

orchestrator = ToolCallingAgent(
    tools=[],
    model=model,
    managed_agents=[inventory_agent, quoting_agent, order_agent],
    name="orchestrator",
    description=(
        "Orchestrator for Munder Difflin Paper Company. Coordinates customer requests by calling agents in this order:\n"
        "1) inventory_agent — Tell it the items the customer wants AND the request date. It will look up the product "
        "catalog to find exact matching names, check stock, and restock if needed. Note the EXACT catalog names it returns.\n"
        "2) quoting_agent — Pass the EXACT catalog item names from inventory_agent (not the customer's informal names) "
        "and the quantities. It will calculate pricing with bulk discounts.\n"
        "3) order_agent — Pass the EXACT catalog item names, quantities, the quoted prices, and the request date. "
        "It will process the sale transactions and check delivery estimates.\n"
        "After all agents respond, combine results into a professional customer response with items ordered, "
        "itemized quote with any discounts applied, total price, and estimated delivery date."
    ),
)


# Run your test scenarios by writing them here. Make sure to keep track of them.

def run_test_scenarios():
    
    print("Initializing Database...")
    init_database(db_engine)
    try:
        quote_requests_sample = pd.read_csv("quote_requests_sample.csv")
        quote_requests_sample["request_date"] = pd.to_datetime(
            quote_requests_sample["request_date"], format="%m/%d/%y", errors="coerce"
        )
        quote_requests_sample.dropna(subset=["request_date"], inplace=True)
        quote_requests_sample = quote_requests_sample.sort_values("request_date")
    except Exception as e:
        print(f"FATAL: Error loading test data: {e}")
        return

    # Get initial state
    initial_date = quote_requests_sample["request_date"].min().strftime("%Y-%m-%d")
    report = generate_financial_report(initial_date)
    current_cash = report["cash_balance"]
    current_inventory = report["inventory_value"]

    ############
    ############
    ############
    # INITIALIZE YOUR MULTI AGENT SYSTEM HERE
    # Agents are already defined at module level above (inventory_agent, quoting_agent, order_agent, orchestrator).
    # No additional initialization needed — they are ready to use.
    ############
    ############
    ############

    results = []
    for idx, row in quote_requests_sample.iterrows():
        request_date = row["request_date"].strftime("%Y-%m-%d")

        print(f"\n=== Request {idx+1} ===")
        print(f"Context: {row['job']} organizing {row['event']}")
        print(f"Request Date: {request_date}")
        print(f"Cash Balance: ${current_cash:.2f}")
        print(f"Inventory Value: ${current_inventory:.2f}")

        # Process request
        request_with_date = f"{row['request']} (Date of request: {request_date})"

        ############
        ############
        ############
        # USE YOUR MULTI AGENT SYSTEM TO HANDLE THE REQUEST
        ############
        ############
        ############

        max_retries = 3
        response = None
        for attempt in range(1, max_retries + 1):
            try:
                response = orchestrator.run(request_with_date)
                break  # Success — exit retry loop
            except Exception as e:
                print(f"[Attempt {attempt}/{max_retries}] Error: {e}")
                if attempt < max_retries:
                    print(f"Retrying in {attempt * 2} seconds...")
                    time.sleep(attempt * 2)  # Exponential backoff: 2s, 4s
                else:
                    print(f"All {max_retries} attempts failed.")
                    response = (
                        "We apologize, but we are currently unable to process your request due to a temporary system issue. "
                        "Please try again later or contact our support team for assistance."
                    )

        # Update state
        report = generate_financial_report(request_date)
        current_cash = report["cash_balance"]
        current_inventory = report["inventory_value"]

        print(f"Response: {response}")
        print(f"Updated Cash: ${current_cash:.2f}")
        print(f"Updated Inventory: ${current_inventory:.2f}")

        results.append(
            {
                "request_id": idx + 1,
                "request_date": request_date,
                "cash_balance": current_cash,
                "inventory_value": current_inventory,
                "response": response,
            }
        )

        time.sleep(1)

    # Final report
    final_date = quote_requests_sample["request_date"].max().strftime("%Y-%m-%d")
    final_report = generate_financial_report(final_date)
    print("\n===== FINAL FINANCIAL REPORT =====")
    print(f"Final Cash: ${final_report['cash_balance']:.2f}")
    print(f"Final Inventory: ${final_report['inventory_value']:.2f}")

    # Save results
    pd.DataFrame(results).to_csv("test_results.csv", index=False)
    return results


if __name__ == "__main__":
    tee = TeeOutput("full_run_output.txt")
    sys.stdout = tee
    try:
        results = run_test_scenarios()
    finally:
        tee.close()
