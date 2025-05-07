import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import the app and the dependency override mechanism
from main import app, get_db, Base, BSBRecord

# --- Test Database Setup ---
# Use an in-memory SQLite database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool, # Use StaticPool for in-memory DB with TestClient
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables in the test database
Base.metadata.create_all(bind=engine)

# --- Dependency Override ---
# Override the get_db dependency to use the test database session
def override_get_db():
    database = TestingSessionLocal()
    try:
        yield database
    finally:
        database.close()

# Apply the override to the app
app.dependency_overrides[get_db] = override_get_db

# --- Test Client ---
client = TestClient(app)

# --- Test Data Setup ---
def setup_test_data(db_session):
    """Helper function to populate the test database."""
    db_session.query(BSBRecord).delete() # Clear existing data
    banks_to_add = [
        BSBRecord(BSB='111-111', Bank='Bank C', Branch='Branch C1', Street='1 C St', Suburb='Cville', State='CS', PostCode='3000', Payments_Accepted='All'),
        BSBRecord(BSB='222-222', Bank='Bank A', Branch='Branch A1', Street='1 A St', Suburb='Aville', State='AS', PostCode='1000', Payments_Accepted='EFT'),
        BSBRecord(BSB='333-333', Bank='Bank B', Branch='Branch B1', Street='1 B St', Suburb='Bville', State='BS', PostCode='2000', Payments_Accepted='All'),
        BSBRecord(BSB='444-444', Bank='Bank A', Branch='Branch A2', Street='2 A St', Suburb='Aville', State='AS', PostCode='1001', Payments_Accepted='None'), # Duplicate Bank A
    ]
    db_session.add_all(banks_to_add)
    db_session.commit()

def clear_test_data(db_session):
    """Helper function to clear the test database."""
    db_session.query(BSBRecord).delete()
    db_session.commit()

# --- Test Cases for /banks endpoint ---
def test_get_banks_success():
    """Test retrieving the list of unique banks successfully."""
    db = TestingSessionLocal()
    setup_test_data(db)
    try:
        response = client.get("/banks")
        assert response.status_code == 200
        data = response.json()
        assert "banks" in data
        # Should return unique banks sorted alphabetically
        assert data["banks"] == ["Bank A", "Bank B", "Bank C"]
    finally:
        clear_test_data(db)
        db.close()

def test_get_banks_empty_db():
    """Test retrieving banks when the database is empty."""
    db = TestingSessionLocal()
    clear_test_data(db) # Ensure DB is empty
    try:
        response = client.get("/banks")
        assert response.status_code == 200
        data = response.json()
        assert "banks" in data
        assert data["banks"] == [] # Expect an empty list
    finally:
        db.close()

# --- Test Cases for /banks/filter endpoint ---
def test_filter_banks_by_name():
    """Test filtering banks by name."""
    db = TestingSessionLocal()
    setup_test_data(db)
    try:
        response = client.get("/banks/filter?name=Bank A")
        assert response.status_code == 200
        data = response.json()
        assert "banks" in data
        assert data["banks"] == ["Bank A"]
        
        # Test case insensitivity
        response = client.get("/banks/filter?name=bank a")
        assert response.status_code == 200
        assert response.json()["banks"] == ["Bank A"]
        
        # Test partial match
        response = client.get("/banks/filter?name=bank")
        assert response.status_code == 200
        assert len(response.json()["banks"]) == 3
    finally:
        clear_test_data(db)
        db.close()

def test_filter_banks_by_state():
    """Test filtering banks by state."""
    db = TestingSessionLocal()
    setup_test_data(db)
    try:
        response = client.get("/banks/filter?state=AS")
        assert response.status_code == 200
        data = response.json()
        assert "banks" in data
        assert data["banks"] == ["Bank A"]
        
        # Test case insensitivity
        response = client.get("/banks/filter?state=as")
        assert response.status_code == 200
        assert response.json()["banks"] == ["Bank A"]
    finally:
        clear_test_data(db)
        db.close()

def test_filter_banks_by_payments():
    """Test filtering banks by payment types."""
    db = TestingSessionLocal()
    setup_test_data(db)
    try:
        response = client.get("/banks/filter?payments_accepted=All")
        assert response.status_code == 200
        data = response.json()
        assert "banks" in data
        banks = set(data["banks"])
        assert "Bank B" in banks
        assert "Bank C" in banks
        assert len(banks) == 2
    finally:
        clear_test_data(db)
        db.close()

def test_filter_banks_multiple_criteria():
    """Test filtering banks with multiple criteria (AND logic)."""
    db = TestingSessionLocal()
    setup_test_data(db)
    try:
        response = client.get("/banks/filter?name=Bank&state=AS")
        assert response.status_code == 200
        data = response.json()
        assert "banks" in data
        assert data["banks"] == ["Bank A"]
    finally:
        clear_test_data(db)
        db.close()

def test_filter_banks_no_matches():
    """Test filtering banks with criteria that match no records."""
    db = TestingSessionLocal()
    setup_test_data(db)
    try:
        response = client.get("/banks/filter?name=NonExistentBank")
        assert response.status_code == 200
        data = response.json()
        assert "banks" in data
        assert data["banks"] == []
    finally:
        clear_test_data(db)
        db.close()

def test_filter_banks_no_parameters():
    """Test filtering banks with no parameters (should return all banks)."""
    db = TestingSessionLocal()
    setup_test_data(db)
    try:
        response = client.get("/banks/filter")
        assert response.status_code == 200
        data = response.json()
        assert "banks" in data
        assert data["banks"] == ["Bank A", "Bank B", "Bank C"]
    finally:
        clear_test_data(db)
        db.close()

# --- Test Cases for /bsb/{bsb_number} endpoint (Example - Keep existing tests if any) ---
def test_get_bsb_details_success():
    """Test retrieving details for a valid BSB number."""
    db = TestingSessionLocal()
    setup_test_data(db)
    try:
        response = client.get("/bsb/222-222")  # BSB for Bank A, Branch A1
        assert response.status_code == 200
        data = response.json()
        assert data["bsb"] == "222-222"
        assert data["bankName"] == "Bank A"
        assert data["branchName"] == "Branch A1"
    finally:
        clear_test_data(db)
        db.close()