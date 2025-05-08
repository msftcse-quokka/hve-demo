import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import the app and the dependency override mechanism
from .main import app, get_db, Base, BSBRecord

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

def test_get_banks_success_descending_order():
    """Test retrieving the list of unique banks successfully, sorted in descending order."""
    db = TestingSessionLocal()
    setup_test_data(db)
    try:
        response = client.get("/banks")
        assert response.status_code == 200
        data = response.json()
        assert "banks" in data
        # Should return unique banks sorted alphabetically in descending order
        assert data["banks"] == ["Bank C", "Bank B", "Bank A"]
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

# --- Test Cases for /bsb/{bsb_number} endpoint (Example - Keep existing tests if any) ---
def test_get_bsb_details_success():
    """Test retrieving details for a specific BSB."""
    db = TestingSessionLocal()
    setup_test_data(db)
    try:
        response = client.get("/bsb/222-222")
        assert response.status_code == 200
        data = response.json()
        assert data["bsb"] == "222-222"
        assert data["bankName"] == "Bank A"
        assert data["branchName"] == "Branch A1"
    finally:
        clear_test_data(db)
        db.close()

def test_get_bsb_details_not_found():
    """Test retrieving details for a non-existent BSB."""
    db = TestingSessionLocal()
    clear_test_data(db)
    try:
        response = client.get("/bsb/999-999")
        assert response.status_code == 404
        assert response.json() == {"detail": "BSB number not found"}
    finally:
        db.close()

def test_get_bsb_details_invalid_format():
    """Test retrieving details with an invalid BSB format."""
    response = client.get("/bsb/123456")
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid BSB format. Use XXX-XXX."}

