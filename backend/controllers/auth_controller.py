# By Ryan Grimes - Updated 3/19/2026
from flask import Blueprint, request, session, redirect, url_for, render_template, flash, jsonify
from services.auth_services import AuthService 
from config.db import get_connection
# By Sidney Cerami 11/09/2026 - Added imports for email functionality
import secrets
import hashlib
# imports created by Sidney cerami 10/20/2026
import os
import smtplib
from email.message import EmailMessage
from utils.auth_utils import hash_password, verify_password

auth_bp = Blueprint('auth', __name__)
service = AuthService()

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        pw = request.form.get('password')

        conn = get_connection()
        if conn is None:
            return "Database connection failed. <a href='/auth/login'>Try again</a>"

        success, role = service.validate_login(user, pw, conn)
        # conn.close()
        
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
        
        return "Invalid Credentials. <a href='/auth/login'>Try again</a>"
    
    return render_template('login.html')

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

        success, message = service.register_user(user, pw, email, conn)
        conn.close()

        if success:
            return redirect(url_for('auth.login')) # Removed "Signup Successful" message, user goes straight to login - Tykeara Hammond 10/15/2026
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

    #smtp_host = os.getenv("SMTP_HOST")
    #smtp_user = os.getenv("SMTP_USER")
    #smtp_password = os.getenv("SMTP_PASSWORD")
    #sender = os.getenv("SMTP_FROM", smtp_user)
    #smtp_port = int(os.getenv("SMTP_PORT", "587"))
# Changed to use config.py for SMTP settings - Sidney Cerami 11/08/2026
    # Get email settings from .env
    smtp_host = os.getenv("MAIL_SERVER")
    smtp_user = os.getenv("MAIL_USERNAME")
    smtp_password = os.getenv("MAIL_PASSWORD")
    sender = os.getenv("MAIL_DEFAULT_SENDER", smtp_user)
    smtp_port = int(os.getenv("MAIL_PORT", "587"))
    use_tls = os.getenv("MAIL_USE_TLS", "True").lower() == "true"




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

           # with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
             #   smtp.starttls()
             #   smtp.login(smtp_user, smtp_password)
                #  smtp.send_message(message)
# Changed to use config.py for SMTP settings - Sidney Cerami 11/08/2026
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
                if use_tls:
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

# Create by Sidney Cerami 11/09/2026 - Forgot Password functionality
@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'GET':
        return render_template('forgot_password.html')

    email = (request.form.get('email') or '').strip()

    if not email:
        flash("Enter the email address associated with your account.", "error")
        return render_template('forgot_password.html')

    # Reuse the existing Brevo SMTP configuration
    smtp_host = os.getenv("MAIL_SERVER")
    smtp_user = os.getenv("MAIL_USERNAME")
    smtp_password = os.getenv("MAIL_PASSWORD")
    sender = os.getenv("MAIL_DEFAULT_SENDER", smtp_user)
    smtp_port = int(os.getenv("MAIL_PORT", "587"))
    use_tls = os.getenv("MAIL_USE_TLS", "True").lower() == "true"

    if not all((smtp_host, smtp_user, smtp_password, sender)):
        print("Forgot-password error: SMTP settings are not configured.")
        flash("We couldn't process your request right now. Please try again later.", "error")
        return render_template('forgot_password.html')

    conn = get_connection()

    if conn is None:
        flash("We couldn't process your request right now. Please try again later.", "error")
        return render_template('forgot_password.html')

    try:
        cur = conn.cursor()

        # Look up the account using the submitted email
        cur.execute(
            "SELECT id FROM users WHERE LOWER(email) = LOWER(%s)",
            (email,)
        )
        user = cur.fetchone()

        if user:
            user_id = user[0]

            # Generate a secure reset token
            token = secrets.token_urlsafe(32)

            # Store only the SHA-256 hash of the token
            token_hash = hashlib.sha256(token.encode()).hexdigest()

            # Remove older reset links for this account
            cur.execute(
                "DELETE FROM password_resets WHERE user_id = %s",
                (user_id,)
            )

            # Save the new token with a 30-minute expiration
            cur.execute("""
                INSERT INTO password_resets (user_id, reset_token, expires_at)
                VALUES (%s, %s, NOW() + INTERVAL '30 minutes')
            """, (user_id, token_hash))

            conn.commit()

            # Build the reset link
            reset_link = url_for(
                'auth.reset_password',
                token=token,
                _external=True
            )

            message = EmailMessage()
            message["Subject"] = "Reset Your Vault Password"
            message["From"] = sender
            message["To"] = email
            message.set_content(
                "We received a request to reset your Vault password.\n\n"
                f"Use the link below to create a new password:\n{reset_link}\n\n"
                "This link expires in 30 minutes and can only be used once.\n\n"
                "If you did not request a password reset, you can ignore this email."
            )

            try:
                with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
                    if use_tls:
                        smtp.starttls()

                    smtp.login(smtp_user, smtp_password)
                    smtp.send_message(message)

            except Exception:
                # Remove the reset token if the email could not be sent
                cur.execute(
                    "DELETE FROM password_resets WHERE reset_token = %s",
                    (token_hash,)
                )
                conn.commit()
                raise

        cur.close()

        # Do not reveal whether an account exists
        flash(
            "If an account matches that email, a password reset link has been sent.",
            "success"
        )

    except Exception as e:
        print(f"Forgot-password error: {e}")
        conn.rollback()
        flash(
            "We couldn't process your request right now. Please try again later.",
            "error"
        )

    finally:
        conn.close()

    return render_template('forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    # Hash the token from the URL to compare it with the database
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    conn = get_connection()

    if conn is None:
        flash("Something went wrong. Please try again later.", "error")
        return redirect(url_for('auth.forgot_password'))

    try:
        cur = conn.cursor()

        # Check that the token exists and has not expired
        cur.execute("""
            SELECT user_id
            FROM password_resets
            WHERE reset_token = %s
              AND expires_at > NOW()
        """, (token_hash,))

        reset_record = cur.fetchone()

        if not reset_record:
            cur.close()
            flash("This password reset link is invalid or has expired.", "error")
            return redirect(url_for('auth.forgot_password'))

        if request.method == 'GET':
            cur.close()
            return render_template('reset_password.html', token=token)

        new_password = request.form.get('password') or ''
        confirm_password = request.form.get('confirm_password') or ''

        if new_password != confirm_password:
            cur.close()
            flash("Your passwords do not match.", "error")
            return render_template('reset_password.html', token=token)

        if not service.validate_password(new_password):
            cur.close()
            flash(
                "Password must be at least 8 characters and include an uppercase "
                "letter, a lowercase letter, a number, and a symbol.",
                "error"
            )
            return render_template('reset_password.html', token=token)

        user_id = reset_record[0]
        hashed_password = hash_password(new_password)

        # Update the password and invalidate all reset links for this account
        cur.execute(
            "UPDATE users SET password = %s WHERE id = %s",
            (hashed_password, user_id)
        )

        cur.execute(
            "DELETE FROM password_resets WHERE user_id = %s",
            (user_id,)
        )

        conn.commit()
        cur.close()

        flash("Your password has been reset successfully. Please log in.", "success")
        return redirect(url_for('auth.login'))

    except Exception as e:
        print(f"Reset-password error: {e}")
        conn.rollback()
        flash("We couldn't reset your password. Please try again.", "error")
        return redirect(url_for('auth.forgot_password'))

    finally:
        conn.close()


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
    
@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))

@auth_bp.route('/cart')
def view_cart():
    if 'cart' not in session:
        session['cart'] = []
    return render_template('cart.html')

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
    
@auth_bp.route('/cart/json')
def get_cart_json():
    return jsonify(session.get('cart', []))

@auth_bp.route('/debug/session')
def debug_session():
    return jsonify(dict(session))

# Admin login route - added by David Jackson 4/19/26
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

        return "Invalid Admin Credentials. <a href='/auth/admin-login'>Try again</a>"

    return render_template('admin_login.html')