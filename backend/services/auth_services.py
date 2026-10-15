#By Ryan Grimes 2/27/2026
#Edited by Tykeara Hammond 10/13/2026
#Register user and validate login
from utils.auth_utils import hash_password, verify_password
import re
class AuthService:
    def register_user(self, username, password, email, db_conn): #Stores a user's unique ID, username, password, and email into the database
        if not email.strip().lower().endswith("@hamptonu.edu") and not email.strip().lower().endswith("@my.hamptonu.edu"): #Fixed Hampton Login Credentials and added .strip() so a stray space wouldnt fail signup. Added 10/12/2026 by Tykeara Hammond
            print(f"You Must Use a Hampton University Associated Email") 
            return False, "You Must Use a Hampton University Associated Email"
        #password check - Tykeara 
        if not self.validate_password(password):
            print("Password does not meet requirements")
            return False, "Password must be atleast 8 characters and include an uppercase letter, a lowercase letter, a number, and a symbol (#?!@$%^&*_-)"
        hashed_pw = hash_password(password)
        try:
            cur = db_conn.cursor() #Creates a point for data to be entered into database
            query = "INSERT INTO users (username, password, email) VALUES (%s, %s, %s)" #Enters data into SQL database. '%s' prevents SQLi by forcing the database to treat user input strictly as data, not as executable SQL code
            cur.execute(query, (username, hashed_pw, email)) #Inputs data at cursor point
            db_conn.commit() #Saves changes
            cur.close() #Closes cursor
            return True, "Signup Successful"
        except Exception as e:
            print(f"Registration Error: {e}")
            db_conn.rollback() #If connection fails, all changes are voided to prevent saving partial data
            return False, "Signup Failed"
    def validate_password(self, password): #Tykeara Hammond added Password Strength (10/13/2026)
        pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[#?!@$%^&*_-]).{8,}$'
        return bool(re.fullmatch(pattern, password))
    
    def validate_login(self, username, password, db_conn):
        try: 
            cur = db_conn.cursor() #Creates a pointer
            cur.execute("SELECT password, role FROM users WHERE username = %s", (username,)) #Has pointer search for occurence of entered credentials
            result = cur.fetchone() #Fetches the row of data that matches the query
            cur.close() #Closes cursor

            if result and verify_password(result[0], password): #If username and password hash match return true
                return True, result [1]
        
            return False, None
        except Exception as e:
            print(f"Login Error: {e}")
            return False, None
    
    def get_user_cart(self, db_conn, user_id): #Retrieves all items from the persistent database for a specific user.
        try:
            cur = db_conn.cursor()
            cur.execute("""
                SELECT item_id, item_name, price, quantity, size 
                FROM cart_items WHERE user_id = %s
            """, (user_id,))
            rows = cur.fetchall()
            return [{'id': r[0], 'name': r[1], 'price': float(r[2]), 'quantity': r[3], 'size': r[4]} for r in rows]
        except Exception as e:
            print(f"Service Error: Could not fetch cart: {e}")
            return []

    def clear_user_cart(self, db_conn, user_id): #Removes all items from the database bag (useful after checkout).
        try:
            cur = db_conn.cursor()
            cur.execute("DELETE FROM cart_items WHERE user_id = %s", (user_id,))
            db_conn.commit()
        except Exception as e:
            print(f"Service Error: Could not clear cart: {e}")