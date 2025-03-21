from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, Float, String, Boolean, Date, DateTime, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date, timedelta
import traceback

# Database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./donation_tracker.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    daily_amount = Column(Float, default=1.0)
    
    donations = relationship("Donation", back_populates="user")

class Donation(Base):
    __tablename__ = "donations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    date = Column(Date, default=datetime.utcnow().date)
    amount = Column(Float)
    is_automatic = Column(Boolean, default=False)
    comment = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="donations")

# Create tables
Base.metadata.create_all(bind=engine)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic models
class DonationBase(BaseModel):
    amount: float
    date: Optional[str] = None  # Changed from date to str for better compatibility
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
    
    class Config:
        orm_mode = True

class UserBase(BaseModel):
    daily_amount: float

class UserUpdate(UserBase):
    pass

class UserResponse(UserBase):
    id: int
    
    class Config:
        orm_mode = True

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
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create default user if doesn't exist
@app.on_event("startup")
async def startup_event():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == 1).first()
        if not user:
            db.add(User(id=1, daily_amount=38.0))  # Default amount is 38
            db.commit()
            print("Created default user with daily amount of 38.0")
    finally:
        db.close()

# Endpoints
@app.get("/api/user", response_model=UserResponse)
def get_user(db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        print("User not found")
        raise HTTPException(status_code=404, detail="User not found")
    return user

@app.put("/api/user/settings", response_model=UserResponse)
def update_settings(user_update: UserUpdate, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.id == 1).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user_update.daily_amount < 0:
            raise HTTPException(status_code=400, detail="Daily amount cannot be negative")
        
        user.daily_amount = user_update.daily_amount
        db.commit()
        db.refresh(user)
        return user
    except Exception as e:
        db.rollback()
        print(f"Error updating settings: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@app.get("/api/donations", response_model=List[DonationResponse])
def get_donations(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    try:
        query = db.query(Donation).filter(Donation.user_id == 1)
        
        if start_date:
            query = query.filter(Donation.date >= start_date)
        if end_date:
            query = query.filter(Donation.date <= end_date)
        
        return query.order_by(Donation.date.desc()).all()
    except Exception as e:
        print(f"Error getting donations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving donations: {str(e)}")

@app.get("/api/donations/summary", response_model=DonationSummary)
def get_summary(db: Session = Depends(get_db)):
    try:
        today = datetime.utcnow().date()
        
        # Total all-time
        total_all_time = db.query(func.sum(Donation.amount)).filter(
            Donation.user_id == 1
        ).scalar() or 0
        
        # Total this month
        first_day_of_month = today.replace(day=1)
        total_this_month = db.query(func.sum(Donation.amount)).filter(
            Donation.user_id == 1,
            Donation.date >= first_day_of_month
        ).scalar() or 0
        
        # Total this year
        first_day_of_year = today.replace(month=1, day=1)
        total_this_year = db.query(func.sum(Donation.amount)).filter(
            Donation.user_id == 1,
            Donation.date >= first_day_of_year
        ).scalar() or 0
        
        summary = {
            "total_all_time": round(total_all_time or 0, 2),
            "total_this_month": round(total_this_month or 0, 2),
            "total_this_year": round(total_this_year or 0, 2)
        }
        
        print(f"Generated summary: {summary}")
        return summary
    except Exception as e:
        print(f"Error in get_summary: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Error generating summary")
    
@app.post("/api/donations", response_model=DonationResponse)
def add_donation(donation: DonationCreate, db: Session = Depends(get_db)):
    try:
        if donation.amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be greater than zero")
        
        # If date not provided, use today
        donation_date = None
        if donation.date:
            try:
                # Convert string date to date object
                donation_date = datetime.strptime(donation.date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        else:
            donation_date = datetime.utcnow().date()
        
        db_donation = Donation(
            user_id=1,
            date=donation_date,
            amount=donation.amount,
            is_automatic=donation.is_automatic,
            comment=donation.comment
        )
        
        db.add(db_donation)
        db.commit()
        db.refresh(db_donation)
        
        print(f"Added donation: id={db_donation.id}, amount={donation.amount}, date={donation_date}")
        return db_donation
    except HTTPException as he:
        # Re-raise HTTP exceptions directly
        raise he
    except Exception as e:
        db.rollback()
        error_msg = str(e)
        print(f"Error adding donation: {error_msg}")
        print(traceback.format_exc())
        # Return a simple string error rather than a complex object
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auto-donate", response_model=AutoDonateResponse)
def auto_donate(db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    today = datetime.utcnow().date()
    
    # Get the latest automatic donation date
    latest_donation = db.query(Donation).filter(
        Donation.user_id == 1,
        Donation.is_automatic == True
    ).order_by(Donation.date.desc()).first()
    
    start_date = latest_donation.date + timedelta(days=1) if latest_donation else today
    
    # Don't add future donations
    if start_date > today:
        return {"success": True, "message": "No donations needed", "count": 0}
    
    # Add daily donations for each missing day
    donations_added = 0
    current_date = start_date
    
    while current_date <= today:
        # Check if an automatic donation already exists for this date
        existing = db.query(Donation).filter(
            Donation.user_id == 1,
            Donation.date == current_date,
            Donation.is_automatic == True
        ).first()
        
        if not existing:
            donation = Donation(
                user_id=1,
                date=current_date,
                amount=user.daily_amount,
                is_automatic=True,
                comment="Automatic daily contribution"
            )
            db.add(donation)
            donations_added += 1
            
        current_date += timedelta(days=1)
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Added {donations_added} automatic donations",
        "count": donations_added
    }

# Health check endpoint
@app.get("/api/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

# If running as script, start the server
if __name__ == "__main__":
    import uvicorn
    print("Starting Charity Donation Tracker API server")
    uvicorn.run(app, host="0.0.0.0", port=8000)