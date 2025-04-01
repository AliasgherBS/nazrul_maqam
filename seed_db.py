import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB Connection Details
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "nazrul_maqam_tracker")

# Initial donation data to seed the database
seed_data = [
    {
        "date": "2025-04-01",
        "amount": 38.0,
        "is_automatic": True,
        "comment": "Automatic daily contribution",
        "created_at": "2025-04-01T00:24:17.000Z"
    },
    {
        "date": "2025-03-31",
        "amount": 38.0,
        "is_automatic": True,
        "comment": "Automatic daily contribution",
        "created_at": "2025-03-31T00:24:17.000Z"
    },
    {
        "date": "2025-03-30", 
        "amount": 110.0,
        "is_automatic": False,
        "comment": None,
        "created_at": "2025-03-30T20:03:27.000Z"
    },
    {
        "date": "2025-03-30",
        "amount": 38.0,
        "is_automatic": True,
        "comment": "Automatic daily contribution",
        "created_at": "2025-03-30T01:18:09.000Z"
    },
    {
        "date": "2025-03-29",
        "amount": 38.0,
        "is_automatic": True,
        "comment": "Automatic daily contribution",
        "created_at": "2025-03-29T02:37:56.000Z"
    },
    {
        "date": "2025-03-28",
        "amount": 38.0,
        "is_automatic": True,
        "comment": "Automatic daily contribution",
        "created_at": "2025-03-28T02:37:56.000Z"
    },
    {
        "date": "2025-03-27",
        "amount": 38.0,
        "is_automatic": True,
        "comment": "Automatic daily contribution",
        "created_at": "2025-03-27T22:04:13.000Z"
    },
    {
        "date": "2025-03-26",
        "amount": 38.0,
        "is_automatic": True,
        "comment": "Automatic daily contribution",
        "created_at": "2025-03-26T02:22:56.000Z"
    },
    {
        "date": "2025-03-25",
        "amount": 38.0,
        "is_automatic": True,
        "comment": "Automatic daily contribution",
        "created_at": "2025-03-25T01:01:15.000Z"
    },
    {
        "date": "2025-03-24",
        "amount": 38.0,
        "is_automatic": True,
        "comment": "Automatic daily contribution",
        "created_at": "2025-03-24T11:48:16.000Z"
    },
    {
        "date": "2025-03-24",
        "amount": 21.0,
        "is_automatic": False,
        "comment": None,
        "created_at": "2025-03-24T11:50:22.000Z"
    },
    {
        "date": "2025-03-24",
        "amount": 76.0,
        "is_automatic": False,
        "comment": "Manual Daily Contribution for 22nd and 23rd March",
        "created_at": "2025-03-24T11:50:35.000Z"
    },
    {
        "date": "2025-03-24",
        "amount": 53.0,
        "is_automatic": False,
        "comment": "LambdaTheta interview",
        "created_at": "2025-03-24T11:50:52.000Z"
    },
    {
        "date": "2025-03-24",
        "amount": 5.0,
        "is_automatic": False,
        "comment": None,
        "created_at": "2025-03-24T11:50:57.000Z"
    },
    {
        "date": "2025-03-24",
        "amount": 53.0,
        "is_automatic": False,
        "comment": None,
        "created_at": "2025-03-24T11:51:38.000Z"
    }
]

async def seed_database():
    try:
        # Connect to MongoDB
        client = AsyncIOMotorClient(MONGODB_URI)
        db = client[DB_NAME]
        
        # Check and create default user
        user = await db.users.find_one({"user_id": "default_user"})
        if not user:
            await db.users.insert_one({
                "user_id": "default_user",
                "daily_amount": 38.0
            })
            print("Default user created")
        else:
            print("Default user already exists")
            
        # Clear existing donations if any
        await db.donations.delete_many({"user_id": "default_user"})
        print("Cleared existing donations")
        
        # Add seed data
        for donation in seed_data:
            # Add user_id to each document
            donation["user_id"] = "default_user"
            
            # Insert document
            await db.donations.insert_one(donation)
            
        # Confirm records
        count = await db.donations.count_documents({"user_id": "default_user"})
        print(f"Seeded database with {count} donations")
        
    except Exception as e:
        print(f"Error seeding database: {str(e)}")
    finally:
        # Close connection
        client.close()
        print("Database connection closed")

# Run the seeding function
if __name__ == "__main__":
    print("Seeding MongoDB database with initial data...")
    asyncio.run(seed_database())
    print("Seeding complete!")