# By Ryan Grimes - Updated 3/19/2026
# auth_controller.py
# Account routes: log in, sign up, admin log in and log out, plus the shopping bag (cart) routes.
# app.py registers this with url_prefix='/auth', so every route here starts with /auth (e.g. /auth/login).

from flask import Blueprint, request, session, redirect, url_for, render_template, flash, jsonify
from services.auth_services import AuthService 
from config.db import get_connection
# imports created by Sidney cerami 10/20/2-26
import os
import smtplib
from email.message import EmailMessage

# auth_bp groups these routes. service (AuthService) does the real work: checking passwords, saving users, loading carts.
auth_bp = Blueprint('auth', __name__)
service = AuthService()

# ---------- Log in ----------
# GET  /auth/login -> shows the log in page
# POST /auth/login -> checks the username + password; success logs the user in, failure shows a red error box
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # POST = the form was submitted. Read what the user typed.
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')

        conn = get_connection()
        if conn is None:
            # Show errors on the styled login page instead of a plain white page - Nicco Hill 10/20/2026
            flash("Can't reach the database right now. Please try again.", "error")
            return render_template('login.html', username=user)

        # Ask AuthService if the password matches the hashed one in the database. Returns (True/False, 'user'/'admin')
        success, role = service.validate_login(user, pw, conn)
        # conn.close()
        
        # Correct password: save who they are in the session (Flask's login cookie)
        if success:
            session['user'] = user
            session['role'] = role

            #store user_id in sesion for storefront ownership checks - added by Day E 4/9/26
            try:
                cur = conn.cursor()
                cur.execute("SELECT id FROM users WHERE username = %s", (user,))
                row = cur.fetchone()
                if row:
                    session['user_id'] = row[0] # Store user_id in session
                    session['cart'] = service.get_user_cart(conn, row[0]) # Load user's cart into session on login
                    cur.close()
            except Exception as e:
                print(f"Error fetching user_id for session: {e}")
            finally:
                conn.close()

            #return redirect(url_for('auth.listings'))
            # Redirect based on role - added by David Jackson 3/23/2026
            if role and role.lower() == 'admin':
                return redirect(url_for('admin.admin_dashboard'))
            else:
                return redirect(url_for('auth.listings'))
        
        # Wrong username or password: close the database connection, then show the log in page again
        # with a red error box and the username still filled in (only the password needs retyping)
        conn.close()
        flash("That username and password don't match. Please try again.", "error")
        return render_template('login.html', username=user)
    
    # GET = just visiting the page, so show the empty form
    return render_template('login.html')

# ---------- Sign up ----------
# GET  /auth/signup -> shows the sign up page
# POST /auth/signup -> creates the account, then sends the user to log in
@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup(): #Errors now show on the signup page instead of a white screen - Tykeara Hammond 10/15/2026
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')
        email = request.form.get('email')

        conn = get_connection()
        if conn is None:
            flash("Something went wrong, please try again.", "error")
            return render_template('signup.html', username=user, email=email)

        # AuthService checks the Hampton email and password rules, hashes the password and saves the user.
        # message explains what went wrong if it fails (e.g. username taken).
        success, message = service.register_user(user, pw, email, conn)
        conn.close()

        if success:
            return redirect(url_for('auth.login')) # Removed "Signup Successful" message, user goes straight to login - Tykeara Hammond 10/15/2026
        # Signup failed: show the reason in a red box and keep the username + email filled in
        flash(message, "error") #Tykeara Hammond added flash for signup errors 10/15/2026
        return render_template('signup.html', username=user, email=email)

    return render_template('signup.html')
# Created by Sidney Cerami 10/20/2026 - Forgot Username route and email functionality
@auth_bp.route('/forgot-username', methods=['GET', 'POST'])
def forgot_username():
    if request.method == 'GET':
        return render_template('forgot_username.html')

    email = (request.form.get('email') or '').strip()
    if not email:
        flash("Enter the email address associated with your account.", "error")
        return render_template('forgot_username.html')

    smtp_host = os.getenv("SMTP_HOST")
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_FROM", smtp_user)
    smtp_port = int(os.getenv("SMTP_PORT", "587"))

    if not all((smtp_host, smtp_user, smtp_password, sender)):
        print("Forgot-username error: SMTP settings are not configured.")
        flash("We couldn't process your request right now. Please try again later.", "error")
        return render_template('forgot_username.html')

    conn = get_connection()
    if conn is None:
        flash("We couldn't process your request right now. Please try again later.", "error")
        return render_template('forgot_username.html')

    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT username FROM users WHERE LOWER(email) = LOWER(%s)",
            (email,)
        )
        user = cur.fetchone()
        cur.close()

        if user:
            message = EmailMessage()
            message["Subject"] = "Your Vault username"
            message["From"] = sender
            message["To"] = email
            message.set_content(
                f"Your Vault username is: {user[0]}\n\n"
                "If you didn't request this, you can ignore this email."
            )

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
                smtp.starttls()
                smtp.login(smtp_user, smtp_password)
                smtp.send_message(message)

        # Use the same response whether or not the email matches an account.
        flash(
            "If an account matches that email, its username has been sent.",
            "success"
        )
    except Exception as e:
        print(f"Forgot-username error: {e}")
        flash("We couldn't process your request right now. Please try again later.", "error")
    finally:
        conn.close()

    return render_template('forgot_username.html')

# ---------- Pages that need a logged-in user ----------
# If there's no user in the session, send them to log in first
@auth_bp.route('/listings')
def listings():
    if 'user' not in session:
        return redirect(url_for('auth.login'))
    return render_template('storefront.html')

@auth_bp.route('/account')
def account():
    if 'user' not in session: 
        return redirect(url_for('auth.login'))
    return render_template('account.html')
    
# Log out: erase everything in the session, then go back to the log in page
@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))

# ---------- Shopping bag (cart) ----------
# The cart is saved in two places: the cart_items table (so it lasts between logins) and the session (so pages load fast)
@auth_bp.route('/cart')
def view_cart():
    if 'cart' not in session:
        session['cart'] = []
    return render_template('cart.html')

# Add an item: make sure it's not sold out, save it to the database, then add it to the session cart
@auth_bp.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    if 'user_id' not in session:
        flash("Please login to add items to your bag.", "error")
        return redirect(url_for('auth.login'))

    item_id = request.form.get('item_id')
    item_name = request.form.get('item_name')
    price = request.form.get('price', 0)
    quantity = request.form.get('quantity', 1)
    size = request.form.get('size')

    # Validate listing availability before adding to cart
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT status, quantity_on_hand, is_made_to_order FROM listings WHERE id = %s",
            (item_id,)
        )
        listing = cur.fetchone()
        cur.close()
        conn.close()
        if not listing:
            return jsonify({"error": "This item is no longer available."}), 404
        listing_status, qty_on_hand, is_made_to_order = listing
        if listing_status == "SOLD_OUT" or (
            not is_made_to_order and qty_on_hand is not None and int(qty_on_hand) <= 0
        ):
            return jsonify({"error": f"{item_name} is sold out and cannot be added to your bag."}), 409
    except Exception as e:
        print(f"DB Error checking listing availability: {e}")

    # PERSIST TO DATABASE
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO cart_items (user_id, item_id, item_name, price, quantity, size)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (session['user_id'], item_id, item_name, price, quantity, size))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"DB Error adding to cart: {e}")

    # Update session for immediate UI feedback
    if 'cart' not in session:
        session['cart'] = []
    
    cart_item = {'id': item_id, 'name': item_name, 'price': float(price), 'quantity': int(quantity), 'size': size}
    temp_cart = session['cart']
    temp_cart.append(cart_item)
    session['cart'] = temp_cart
    session.modified = True

    flash(f"Added {item_name} to your bag!", "success")
    return redirect(url_for('auth.view_cart'))

# Remove the item at position index from the cart, in both the session and the database
@auth_bp.route('/remove_from_cart/<int:index>', methods=['POST'])
def remove_from_cart(index):
    if 'cart' in session and 'user_id' in session:
        temp_cart = session['cart']
        if 0 <= index < len(temp_cart):
            removed_item = temp_cart.pop(index)
            
            # REMOVE FROM DATABASE
            try:
                conn = get_connection()
                cur = conn.cursor()
                # We delete one instance of this item for this user
                cur.execute("""
                    DELETE FROM cart_items 
                    WHERE id = (
                        SELECT id FROM cart_items 
                        WHERE user_id = %s AND item_name = %s AND size = %s
                        LIMIT 1
                    )
                """, (session['user_id'], removed_item['name'], removed_item['size']))
                conn.commit()
                cur.close()
                conn.close()
            except Exception as e:
                print(f"DB Error removing item: {e}")

            session['cart'] = temp_cart
            session.modified = True
            flash(f"Removed {removed_item['name']} from bag.", "info")
    return redirect(url_for('auth.view_cart'))

# Added by Day E 4/9/26 - returns current session user info for frontend auth checks
@auth_bp.route('/api/auth/me')
def get_current_session_user():
    if 'user' not in session:
        return jsonify({"error": "Not logged in"}), 401
    
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, username, role FROM users WHERE username = %s", (session['user'],))
        user = cur.fetchone()
        conn.close()

        if not user:
            return jsonify({"error": "User not found"}), 404

        return jsonify({
            "id": user[0],
            "username": user[1],
            "role": user[2]
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# The cart as JSON, for JavaScript on the pages
@auth_bp.route('/cart/json')
def get_cart_json():
    return jsonify(session.get('cart', []))

# Shows everything in the session as JSON (for debugging)
@auth_bp.route('/debug/session')
def debug_session():
    return jsonify(dict(session))

# Admin login route - added by David Jackson 4/19/26
# ---------- Admin log in ----------
# GET  /auth/admin-login -> shows the admin log in page
# POST /auth/admin-login -> checks the admin username + password, then opens the admin dashboard
@auth_bp.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')

        # temporary hardcoded admin login for testing
        if user == "admin" and pw == "admin123":
            session['user'] = user
            session['role'] = 'admin'
            return redirect(url_for('admin.admin_dashboard'))

        # Wrong admin login: show a red error box on the styled page with the username still filled in
        flash("That admin username and password don't match. Please try again.", "error")
        return render_template('admin_login.html', username=user)

    return render_template('admin_login.html')