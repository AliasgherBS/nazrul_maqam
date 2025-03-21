from fastapi import FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date, timedelta
import traceback
import os
from remote_sqlite import RemoteSQLiteClient

# Remote SQLite setup
API_URL = "https://nazrul-maqam.thegraphisign.com/db_api.php"
API_KEY = "aliasgher_123"
db_client = RemoteSQLiteClient(API_URL, API_KEY)

# Pydantic models (keep these the same as in your original code)
class DonationBase(BaseModel):
    amount: float
    date: Optional[str] = None  # String for better compatibility
    is_automatic: bool = False
    comment: Optional[str] = None

class DonationCreate(DonationBase):
    pass

class DonationResponse(BaseModel):
    id: int
    date: date
    amount: float
    is_automatic: bool 
    comment: Optional[str] = None
    created_at: datetime

class UserBase(BaseModel):
    daily_amount: float

class UserUpdate(UserBase):
    pass

class UserResponse(UserBase):
    id: int

class DonationSummary(BaseModel):
    total_all_time: float
    total_this_month: float
    total_this_year: float

class AutoDonateResponse(BaseModel):
    success: bool
    message: str
    count: int

# FastAPI app
app = FastAPI(title="Charity Donation Tracker API")

# CORS middleware - Enable all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup event
@app.on_event("startup")
async def startup_event():
    # Ensure tables exist
    db_client.create_tables_if_not_exist()
    print("Database initialized successfully")

# Health check endpoint
@app.get("/api/health")
def health_check():
    # Also check database connection
    db_status = db_client.ping()
    if not db_status.get('success', False):
        print(f"Database health check failed: {db_status.get('error', 'Unknown error')}")
    
    return {
        "status": "ok", 
        "timestamp": datetime.utcnow().isoformat(),
        "database_connected": db_status.get('success', False)
    }

# Endpoints - replace SQLAlchemy with RemoteSQLiteClient
@app.get("/api/user", response_model=UserResponse)
def get_user():
    user = db_client.get_user_by_id(1)
    if not user:
        print("User not found")
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.put("/api/user/settings", response_model=UserResponse)
def update_settings(user_update: UserUpdate):
    try:
        if user_update.daily_amount < 0:
            raise HTTPException(status_code=400, detail="Daily amount cannot be negative")
        
        db_client.update_user_settings(1, user_update.daily_amount)
        user = db_client.get_user_by_id(1)
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        return user
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error updating settings: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.get("/api/donations", response_model=List[DonationResponse])
def get_donations(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
):
    try:
        donations = db_client.get_all_donations(1, start_date, end_date)
        
        # Convert date strings to date objects
        for donation in donations:
            if 'date' in donation and donation['date']:
                donation['date'] = datetime.strptime(donation['date'], "%Y-%m-%d").date()
            if 'created_at' in donation and donation['created_at']:
                donation['created_at'] = datetime.fromisoformat(donation['created_at'])
            # Convert is_automatic from integer to boolean
            if 'is_automatic' in donation:
                donation['is_automatic'] = bool(donation['is_automatic'])
                
        return donations
    except Exception as e:
        print(f"Error getting donations: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error retrieving donations: {str(e)}")

@app.get("/api/donations/summary", response_model=DonationSummary)
def get_summary():
    try:
        summary = db_client.get_donation_summary(1)
        print(f"Generated summary: {summary}")
        return summary
    except Exception as e:
        print(f"Error in get_summary: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Error generating summary")
    
@app.post("/api/donations", response_model=DonationResponse)
def add_donation(donation: DonationCreate):
    try:
        if donation.amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be greater than zero")
        
        # Process date
        donation_date = None
        if donation.date:
            try:
                # Validate date format
                datetime.strptime(donation.date, "%Y-%m-%d")
                donation_date = donation.date
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Create donation
        db_donation = db_client.create_donation(
            user_id=1,
            amount=donation.amount,
            date_str=donation_date,
            is_automatic=donation.is_automatic,
            comment=donation.comment
        )
        
        if not db_donation:
            raise HTTPException(status_code=500, detail="Failed to create donation")
        
        # Convert date and created_at
        db_donation['date'] = datetime.strptime(db_donation['date'], "%Y-%m-%d").date()
        db_donation['created_at'] = datetime.fromisoformat(db_donation['created_at'])
        # Convert is_automatic from integer to boolean
        db_donation['is_automatic'] = bool(db_donation['is_automatic'])
        
        print(f"Added donation: id={db_donation['id']}, amount={donation.amount}, date={donation_date}")
        return db_donation
    except HTTPException as he:
        raise he
    except Exception as e:
        error_msg = str(e)
        print(f"Error adding donation: {error_msg}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auto-donate", response_model=AutoDonateResponse)
def auto_donate():
    try:
        user = db_client.get_user_by_id(1)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        daily_amount = user['daily_amount']
        today = date.today()
        
        # Get the latest automatic donation date
        latest_donation = db_client.get_latest_automatic_donation(1)
        
        start_date = None
        if latest_donation:
            latest_date = datetime.strptime(latest_donation['date'], "%Y-%m-%d").date()
            start_date = latest_date + timedelta(days=1)
        else:
            start_date = today
        
        # Don't add future donations
        if start_date > today:
            return {"success": True, "message": "No donations needed", "count": 0}
        
        # Add daily donations for each missing day
        donations_added = 0
        current_date = start_date
        
        while current_date <= today:
            current_date_str = current_date.isoformat()
            
            # Check if an automatic donation already exists for this date
            existing_donations = db_client.get_all_donations(
                user_id=1, 
                start_date=current_date_str, 
                end_date=current_date_str
            )
            
            existing = False
            for d in existing_donations:
                if d['is_automatic']:
                    existing = True
                    break
            
            if not existing:
                db_client.create_donation(
                    user_id=1,
                    amount=daily_amount,
                    date_str=current_date_str,
                    is_automatic=True,
                    comment="Automatic daily donation"
                )
                donations_added += 1
                
            current_date += timedelta(days=1)
        
        return {
            "success": True,
            "message": f"Added {donations_added} automatic donations",
            "count": donations_added
        }
    except Exception as e:
        print(f"Error in auto-donate: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

# Main entry point
if __name__ == "__main__":
    import uvicorn
    print("Starting Charity Donation Tracker API server")
    uvicorn.run(app, host="0.0.0.0", port=8000)