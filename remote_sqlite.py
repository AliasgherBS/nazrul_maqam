# remote_sqlite.py
import requests
import json
from datetime import datetime, date
import traceback

class RemoteSQLiteClient:
    def __init__(self, api_url, api_key):
        """Initialize the remote SQLite client.
        
        Args:
            api_url (str): The URL of the SQLite API (e.g., 'https://your-domain.com/db_api.php')
            api_key (str): The secret API key for authentication
        """
        self.api_url = api_url
        self.api_key = api_key
        self.headers = {
            'Content-Type': 'application/json',
            'X-API-KEY': api_key
        }
    
    def ping(self):
        """Test connection to the remote database."""
        try:
            response = requests.get(
                f"{self.api_url}?op=ping",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Database ping failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def query(self, sql, params=None):
        """Execute a read query against the remote database.
        
        Args:
            sql (str): SQL query string
            params (dict or list, optional): Query parameters
            
        Returns:
            list: List of dictionaries representing the result rows
        """
        params = params or {}
        try:
            response = requests.post(
                f"{self.api_url}?op=query",
                headers=self.headers,
                json={'sql': sql, 'params': params}
            )
            response.raise_for_status()
            result = response.json()
            
            if not result.get('success', False):
                raise Exception(result.get('error', 'Unknown error'))
                
            return result['data']
        except Exception as e:
            print(f"Query error: {str(e)}")
            print(traceback.format_exc())
            raise e
    
    def execute(self, sql, params=None):
        """Execute a write query against the remote database.
        
        Args:
            sql (str): SQL query string
            params (dict or list, optional): Query parameters
            
        Returns:
            dict: Contains 'lastId' and 'changes' fields
        """
        params = params or {}
        try:
            response = requests.post(
                f"{self.api_url}?op=exec",
                headers=self.headers,
                json={'sql': sql, 'params': params}
            )
            response.raise_for_status()
            result = response.json()
            
            if not result.get('success', False):
                raise Exception(result.get('error', 'Unknown error'))
                
            return result
        except Exception as e:
            print(f"Execute error: {str(e)}")
            print(traceback.format_exc())
            raise e
    
    def get_user_by_id(self, user_id):
        """Get a user by ID from the users table."""
        results = self.query(
            "SELECT * FROM users WHERE id = :id",
            {'id': user_id}
        )
        return results[0] if results else None
    
    def update_user_settings(self, user_id, daily_amount):
        """Update a user's daily amount setting."""
        return self.execute(
            "UPDATE users SET daily_amount = :amount WHERE id = :id",
            {'amount': daily_amount, 'id': user_id}
        )
    
    def get_all_donations(self, user_id=1, start_date=None, end_date=None):
        """Get all donations, optionally filtered by date range."""
        sql = "SELECT * FROM donations WHERE user_id = :user_id"
        params = {'user_id': user_id}
        
        if start_date:
            sql += " AND date >= :start_date"
            params['start_date'] = start_date.isoformat() if isinstance(start_date, date) else start_date
            
        if end_date:
            sql += " AND date <= :end_date"
            params['end_date'] = end_date.isoformat() if isinstance(end_date, date) else end_date
            
        sql += " ORDER BY date DESC"
        
        return self.query(sql, params)
    
    def get_donation_summary(self, user_id=1):
        """Get donation summary statistics."""
        today = date.today().isoformat()
        first_day_of_month = date.today().replace(day=1).isoformat()
        first_day_of_year = date.today().replace(month=1, day=1).isoformat()
        
        # Total all-time
        all_time_result = self.query(
            "SELECT SUM(amount) as total FROM donations WHERE user_id = :user_id",
            {'user_id': user_id}
        )
        total_all_time = all_time_result[0]['total'] if all_time_result and all_time_result[0]['total'] else 0
        
        # Total this month
        month_result = self.query(
            "SELECT SUM(amount) as total FROM donations WHERE user_id = :user_id AND date >= :start_date",
            {'user_id': user_id, 'start_date': first_day_of_month}
        )
        total_this_month = month_result[0]['total'] if month_result and month_result[0]['total'] else 0
        
        # Total this year
        year_result = self.query(
            "SELECT SUM(amount) as total FROM donations WHERE user_id = :user_id AND date >= :start_date",
            {'user_id': user_id, 'start_date': first_day_of_year}
        )
        total_this_year = year_result[0]['total'] if year_result and year_result[0]['total'] else 0
        
        return {
            "total_all_time": round(float(total_all_time), 2),
            "total_this_month": round(float(total_this_month), 2),
            "total_this_year": round(float(total_this_year), 2)
        }
    
    def create_donation(self, user_id, amount, date_str=None, is_automatic=False, comment=None):
        """Create a new donation."""
        donation_date = date_str if date_str else date.today().isoformat()
        
        result = self.execute(
            """
            INSERT INTO donations (user_id, date, amount, is_automatic, comment, created_at)
            VALUES (:user_id, :date, :amount, :is_automatic, :comment, :created_at)
            """,
            {
                'user_id': user_id,
                'date': donation_date,
                'amount': amount,
                'is_automatic': 1 if is_automatic else 0,
                'comment': comment,
                'created_at': datetime.utcnow().isoformat()
            }
        )
        
        last_id = result['lastId']
        
        # Get the inserted donation
        donations = self.query("SELECT * FROM donations WHERE id = :id", {'id': last_id})
        return donations[0] if donations else None
    
    def get_latest_automatic_donation(self, user_id=1):
        """Get the latest automatic donation for a user."""
        results = self.query(
            """
            SELECT * FROM donations 
            WHERE user_id = :user_id AND is_automatic = 1
            ORDER BY date DESC
            LIMIT 1
            """,
            {'user_id': user_id}
        )
        return results[0] if results else None
    
    def create_tables_if_not_exist(self):
        """Create the necessary tables if they don't exist."""
        # Create users table
        self.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            daily_amount REAL DEFAULT 1.0
        )
        """)
        
        # Create donations table
        self.execute("""
        CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT,
            amount REAL,
            is_automatic INTEGER DEFAULT 0,
            comment TEXT,
            created_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """)
        
        # Check if default user exists, create if not
        user = self.get_user_by_id(1)
        if not user:
            self.execute(
                "INSERT INTO users (id, daily_amount) VALUES (1, 38.0)"
            )