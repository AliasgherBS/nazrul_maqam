from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime, date, timedelta
import traceback
import os
from dotenv import load_dotenv
import pytz

# Load environment variables
load_dotenv()

# MongoDB Connection Details
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "nazrul_maqam_tracker")

# PyObjectId for MongoDB ObjectId handling
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
        
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)
        
    @classmethod
    def __get_pydantic_json_schema__(cls, _schema_generator, _field_schema):
        return {"type": "string"}

# Pydantic models
class UserModel(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    daily_amount: float = 38.0
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_schema_extra": {"example": {"daily_amount": 38.0}},
        "json_encoders": {ObjectId: str}
    }

class UserUpdate(BaseModel):
    daily_amount: float
    
    model_config = {
        "arbitrary_types_allowed": True, 
        "json_encoders": {ObjectId: str}
    }

class UserResponse(BaseModel):
    id: int = 1  # Keep the same response format as SQLAlchemy
    daily_amount: float
    
    model_config = {
        "arbitrary_types_allowed": True
    }

class DonationBase(BaseModel):
    amount: float
    date: Optional[str] = None  # Changed from date to str for better compatibility
    is_automatic: bool = False
    comment: Optional[str] = None

class DonationCreate(DonationBase):
    pass

class DonationModel(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    user_id: str = "default_user"
    date: str  # Store as ISO string
    amount: float
    is_automatic: bool = False
    comment: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_encoders": {ObjectId: str}
    }

class DonationResponse(BaseModel):
    id: int  # Keep the same response format for compatibility
    date: date
    amount: float
    is_automatic: bool 
    comment: Optional[str] = None
    created_at: datetime
    
    model_config = {
        "arbitrary_types_allowed": True
    }

class DonationSummary(BaseModel):
    total_all_time: float
    total_this_month: float
    total_this_year: float

class AutoDonateResponse(BaseModel):
    success: bool
    message: str
    count: int

# FastAPI app
app = FastAPI(title="Nazrul Maqam Tracker API")

# Database connection
client = None
db = None

# CORS middleware - Enable all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Events
@app.on_event("startup")
async def startup_db_client():
    global client, db
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DB_NAME]
    
    # Create default user if not exists
    default_user = await db.users.find_one({"user_id": "default_user"})
    if not default_user:
        await db.users.insert_one({"user_id": "default_user", "daily_amount": 38.0})
        print("Created default user with daily amount of 38.0")

@app.on_event("shutdown")
async def shutdown_db_client():
    global client
    if client:
        client.close()

# Helper functions
def parse_date_string(date_str):
    """Parse a date string to a date object."""
    if not date_str:
        return datetime.utcnow().date()
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

def format_donation_response(donation_doc):
    """Format a MongoDB donation document to match the expected response format."""
    # Convert string date to date object
    if isinstance(donation_doc["date"], str):
        date_obj = datetime.strptime(donation_doc["date"], "%Y-%m-%d").date()
    else:
        date_obj = donation_doc["date"]
    
    # Handle created_at datetime
    if isinstance(donation_doc["created_at"], str):
        created_at = datetime.fromisoformat(donation_doc["created_at"].replace('Z', '+00:00'))
    else:
        created_at = donation_doc["created_at"]
    
    # Generate sequential ID to match the SQL format 
    # (using the last 6 digits of the ObjectId for simplicity)
    id_num = int(str(donation_doc["_id"])[-6:], 16) % 1000000  

    return {
        "id": id_num,
        "date": date_obj,
        "amount": donation_doc["amount"],
        "is_automatic": donation_doc["is_automatic"],
        "comment": donation_doc.get("comment"),
        "created_at": created_at
    }

# Endpoints
@app.get("/api/user", response_model=UserResponse)
async def get_user():
    user = await db.users.find_one({"user_id": "default_user"})
    if not user:
        print("User not found")
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": 1, "daily_amount": user["daily_amount"]}

@app.put("/api/user/settings", response_model=UserResponse)
async def update_settings(user_update: UserUpdate):
    try:
        if user_update.daily_amount < 0:
            raise HTTPException(status_code=400, detail="Daily amount cannot be negative")
        
        update_result = await db.users.update_one(
            {"user_id": "default_user"}, 
            {"$set": {"daily_amount": user_update.daily_amount}}
        )
        
        if update_result.modified_count == 0:
            # If no document was updated, check if it exists
            user = await db.users.find_one({"user_id": "default_user"})
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
        
        # Return updated user
        user = await db.users.find_one({"user_id": "default_user"})
        return {"id": 1, "daily_amount": user["daily_amount"]}
    
    except Exception as e:
        print(f"Error updating settings: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.get("/api/donations", response_model=List[DonationResponse])
async def get_donations(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
):
    try:
        # Build query
        query = {"user_id": "default_user"}
        
        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query["$gte"] = start_date.isoformat()
            if end_date:
                date_query["$lte"] = end_date.isoformat()
            if date_query:
                query["date"] = date_query
        
        # Fetch donations
        donations = []
        async for doc in db.donations.find(query).sort("date", -1):  # Descending order by date
            donations.append(format_donation_response(doc))
        
        return donations
    
    except Exception as e:
        print(f"Error getting donations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving donations: {str(e)}")

@app.get("/api/donations/summary", response_model=DonationSummary)
async def get_summary():
    try:
        today = datetime.utcnow().date()
        
        # Total all-time
        cursor = db.donations.find({"user_id": "default_user"})
        total_all_time = 0
        async for doc in cursor:
            total_all_time += doc["amount"]
        
        # Total this month
        first_day_of_month = today.replace(day=1)
        cursor = db.donations.find({
            "user_id": "default_user",
            "date": {"$gte": first_day_of_month.isoformat()}
        })
        total_this_month = 0
        async for doc in cursor:
            total_this_month += doc["amount"]
        
        # Total this year
        first_day_of_year = today.replace(month=1, day=1)
        cursor = db.donations.find({
            "user_id": "default_user",
            "date": {"$gte": first_day_of_year.isoformat()}
        })
        total_this_year = 0
        async for doc in cursor:
            total_this_year += doc["amount"]
        
        summary = {
            "total_all_time": round(total_all_time, 2),
            "total_this_month": round(total_this_month, 2),
            "total_this_year": round(total_this_year, 2)
        }
        
        print(f"Generated summary: {summary}")
        return summary
    
    except Exception as e:
        print(f"Error in get_summary: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Error generating summary")
    
@app.post("/api/donations", response_model=DonationResponse)
async def add_donation(donation: DonationCreate):
    try:
        if donation.amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be greater than zero")
        
        # If date not provided, use today
        donation_date = None
        if donation.date:
            try:
                # Parse and validate date
                donation_date = parse_date_string(donation.date)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        else:
            donation_date = datetime.utcnow().date()
        
        # Create donation document
        created_at = datetime.utcnow()
        new_donation = {
            "user_id": "default_user",
            "date": donation_date.isoformat(),
            "amount": donation.amount,
            "is_automatic": donation.is_automatic,
            "comment": donation.comment,
            "created_at": created_at
        }
        
        # Insert into database
        result = await db.donations.insert_one(new_donation)
        
        # Get the inserted document
        doc = await db.donations.find_one({"_id": result.inserted_id})
        
        # Format for response
        response_data = format_donation_response(doc)
        
        print(f"Added donation: id={result.inserted_id}, amount={donation.amount}, date={donation_date}")
        return response_data
    
    except HTTPException as he:
        # Re-raise HTTP exceptions directly
        raise he
    except Exception as e:
        error_msg = str(e)
        print(f"Error adding donation: {error_msg}")
        print(traceback.format_exc())
        # Return a simple string error rather than a complex object
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auto-donate", response_model=AutoDonateResponse)
async def auto_donate():
    try:
        # Get user
        user = await db.users.find_one({"user_id": "default_user"})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        daily_amount = user["daily_amount"]
        today = datetime.utcnow().date()
        
        # Get the latest automatic donation date
        latest_auto = await db.donations.find_one(
            {"user_id": "default_user", "is_automatic": True},
            sort=[("date", -1)]
        )
        
        # Determine start date
        start_date = None
        if latest_auto:
            if isinstance(latest_auto["date"], str):
                latest_date = datetime.strptime(latest_auto["date"], "%Y-%m-%d").date()
            else:
                latest_date = latest_auto["date"]
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
            # Check if an automatic donation already exists for this date
            existing = await db.donations.find_one({
                "user_id": "default_user",
                "date": current_date.isoformat(),
                "is_automatic": True
            })
            
            if not existing:
                donation = {
                    "user_id": "default_user",
                    "date": current_date.isoformat(),
                    "amount": daily_amount,
                    "is_automatic": True,
                    "comment": "Automatic daily contribution",
                    "created_at": datetime.utcnow()
                }
                await db.donations.insert_one(donation)
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
        raise HTTPException(status_code=500, detail=f"Error in auto-donate: {str(e)}")

# Health check endpoint
@app.get("/api/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

# Root endpoint to serve the website
@app.get("/")
async def serve_website():
    return FileResponse("index.html")

# If running as script, start the server
if __name__ == "__main__":
    import uvicorn
    print("Starting Nazrul Maqam Tracker API server")
    uvicorn.run(app, host="0.0.0.0", port=8000)