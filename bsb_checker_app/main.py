import os
import requests
import pandas as pd
import io
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from sqlalchemy import create_engine, Column, String, MetaData, Table, inspect, desc
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from contextlib import contextmanager
import logging

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration ---
DATABASE_URL = "sqlite:///./bsb_data.db"
BSB_CSV_URL = "https://bsb.auspaynet.com.au/Public/BSB_DB.NSF/getBSBFullCSV?OpenAgent"
TABLE_NAME = "bsb_records"
DB_FILE_PATH = "./bsb_data.db" # Relative to where the app runs (inside bsb_checker_app)

# --- Database Setup ---
# The database file will be created in the same directory as main.py
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
metadata = MetaData()

# Define the table structure explicitly
# Use column names exactly as they appear in the CSV header for easier mapping
bsb_table = Table(
    TABLE_NAME,
    metadata,
    Column("BSB", String, primary_key=True, index=True),
    Column("Bank", String),
    Column("Branch", String),
    Column("Street", String),
    Column("Suburb", String),
    Column("State", String),
    Column("PostCode", String),
    Column("Payments Accepted", String), # Keep original name from CSV for direct mapping
)

# Create the table if it doesn't exist
metadata.create_all(bind=engine)

# --- SQLAlchemy Model ---
class BSBRecord(Base):
    __tablename__ = TABLE_NAME
    __table_args__ = {'extend_existing': True} # Allow redefinition

    BSB = Column(String, primary_key=True, index=True)
    Bank = Column(String)
    Branch = Column(String)
    Street = Column(String)
    Suburb = Column(String)
    State = Column(String)
    PostCode = Column(String)
    # Map the CSV column name to a more Pythonic attribute name if desired,
    # but direct mapping during insertion is simpler with matching names.
    # Use the name defined in the Table object above.
    Payments_Accepted = Column("Payments Accepted", String)


# --- Dependency for DB Session ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Helper Function to Download and Update DB ---
def update_bsb_database():
    logger.info(f"Attempting to download BSB data from {BSB_CSV_URL}...")
    try:
        response = requests.get(BSB_CSV_URL, timeout=60) # Add timeout
        response.raise_for_status() # Raise an exception for bad status codes
        logger.info("Download successful. Processing data...")

        # Use io.StringIO to treat the CSV content as a file for pandas
        csv_data = io.StringIO(response.text)

        # Read CSV using pandas. The CSV does not have a header row.
        # Provide column names explicitly and skip the first row (which is data, not header).
        column_names = ["BSB", "Bank", "Branch", "Street", "Suburb", "State", "PostCode", "Payments Accepted"]
        df = pd.read_csv(csv_data, header=None, names=column_names, dtype=str, skiprows=1) # Skip the actual first row of data
        logger.info(f"Successfully read {len(df)} records from CSV.")

        # Basic Data Cleaning (remove potential leading/trailing spaces)
        # Column names are already set by the 'names' parameter, so no need to strip column names.
        for col in df.columns:
             if df[col].dtype == 'object': # Apply strip only to string columns
                df[col] = df[col].str.strip()

        # Ensure BSB numbers are formatted correctly (e.g., 'XXX-XXX')
        # The CSV usually has them in 'XXX-XXX' format already. Add validation if needed.
        # Keep the original column name "Payments Accepted" from the CSV to match SQLAlchemy table definition.

        # Use pandas to_sql to replace the table content
        logger.info(f"Writing {len(df)} records to database table '{TABLE_NAME}'...")
        df.to_sql(TABLE_NAME, con=engine, if_exists='replace', index=False)
        logger.info("Database update complete.")

    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading BSB data: {e}")
    except pd.errors.ParserError as e:
        logger.error(f"Error parsing CSV data: {e}")
        # Log part of the raw response to help diagnose parsing issues
        logger.error(f"Raw CSV start:\n{response.text[:500]}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during database update: {e}", exc_info=True)


# --- FastAPI App ---
app = FastAPI(
    title="BSB Checker API",
    description="API to query Australian BSB numbers and update the BSB database.",
    version="1.0.0"
)

# --- Startup Event ---
@app.on_event("startup")
def startup_event():
    # Check if the database file exists and delete it
    db_file_absolute_path = os.path.join(os.path.dirname(__file__), DB_FILE_PATH)
    if os.path.exists(db_file_absolute_path):
        logger.info(f"Database file found at {db_file_absolute_path}. Deleting existing database.")
        try:
            os.remove(db_file_absolute_path)
            logger.info("Existing database deleted successfully.")
        except OSError as e:
            logger.error(f"Error deleting database file {db_file_absolute_path}: {e}")
            # Depending on the error, you might want to exit or handle it differently
            # For now, we'll log and attempt to proceed, which might fail later.

    # Recreate the table structure
    logger.info(f"Creating database table '{TABLE_NAME}'.")
    metadata.create_all(bind=engine)
    logger.info("Table created. Performing initial database update.")

    # Always perform a database update on startup
    update_bsb_database()


# --- API Endpoints ---
@app.post("/update-bsb", status_code=202) # Accepted
async def trigger_update_bsb(background_tasks: BackgroundTasks):
    """
    Triggers a background task to download the latest BSB data
    and update the database.
    """
    logger.info("Received request to update BSB database.")
    background_tasks.add_task(update_bsb_database)
    return {"message": "BSB database update initiated in the background."}

@app.get("/banks")
async def get_all_banks(db: Session = Depends(get_db)):
    """
    Retrieves a list of all unique bank names sorted alphabetically in descending order.
    """
    logger.info("Received request to list all banks.")
    banks_query = db.query(BSBRecord.Bank).distinct().order_by(desc(BSBRecord.Bank)).all()
    
    if not banks_query:
        logger.warning("No banks found in the database.")
        # Return an empty list instead of 404 to indicate no data but a successful query
        return []

    # Extract bank names from the query result (list of tuples)
    bank_names = [bank[0] for bank in banks_query if bank[0]] # Ensure bank name is not None
    logger.info(f"Returning {len(bank_names)} unique bank names.")
    return bank_names

@app.get("/bsb/{bsb_number}")
async def get_bsb_details(bsb_number: str, db: Session = Depends(get_db)):
    """
    Retrieves details for a given BSB number (format: XXX-XXX).
    """
    logger.info(f"Received query for BSB: {bsb_number}")
    # Basic validation for BSB format (optional but recommended)
    if not (len(bsb_number) == 7 and bsb_number[3] == '-'):
         raise HTTPException(status_code=400, detail="Invalid BSB format. Use XXX-XXX.")

    record = db.query(BSBRecord).filter(BSBRecord.BSB == bsb_number).first()

    if record is None:
        logger.warning(f"BSB number {bsb_number} not found in the database.")
        raise HTTPException(status_code=404, detail="BSB number not found")

    logger.info(f"Found details for BSB: {bsb_number}")
    # Return data matching the requested JSON structure with camelCase keys
    return {
        "bsb": record.BSB,
        "bankName": record.Bank,
        "branchName": record.Branch,
        "street": record.Street,
        "suburb": record.Suburb,
        "state": record.State,
        "postCode": record.PostCode,
        "supportedPaymentSystem": record.Payments_Accepted # Use the mapped attribute name
    }

# --- Run with Uvicorn (for local testing) ---
# You would typically run this using: uvicorn main:app --reload --app-dir bsb_checker_app
if __name__ == "__main__":
    import uvicorn
    # Run update once before starting server if running directly
    # Note: The startup event handles this when run via uvicorn command
    # update_bsb_database()
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
