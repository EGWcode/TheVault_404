import sys
import os
import secrets
from flask import Flask, render_template, redirect, url_for, session, request, jsonify, make_response
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend'))) 

from controllers.listing_controller import listing_bp
from controllers.storefront_controller import storefront_bp, storefront_pages_bp 
from controllers.purchase_controller import purchase_bp
from controllers.wishlist_controller import wishlist_bp
from controllers.admin_controller import admin_bp
from controllers.auth_controller import auth_bp 
from controllers.return_controller import returns_bp
from controllers.checkout_controller import checkout_bp
from controllers.menu_controller import menu_api_bp, menu_pages_bp  # Added by Anthony Jackson - dropdown menu pages
from controllers.message_controller import messages_bp # Added 10/20/26 for buyer-seller messaging
from controllers.rating_controller import ratings_bp  # Added by Anthony Jackson 10/21/26 - storefront ratings
from controllers.profile_controller import profile_bp  # Added by Anthony Jackson 10/21/26 - optional user profile
from init_db import create_vault_tables
from controllers.discovery_controller import discovery_bp  # Updated by Noah Green 10/17/2026


def create_app():
    app = Flask(__name__,
                template_folder='templates',
                static_folder='static')

    # Session key now comes from the environment (SECRET_KEY), not the code
    app.secret_key = os.environ.get('SECRET_KEY')
    if not app.secret_key:
        # No key set, so use a random one just so the app still runs.
        # Logins will reset every time the app restarts until SECRET_KEY is set.
        app.secret_key = secrets.token_hex(32)
        print("[startup] WARNING: SECRET_KEY is not set. Set it in the environment.")

    # Session inactivity protection - added by Nicholas Smith, 10/25/2026.
    # Only browser keyboard/mouse activity refreshes the server-side idle timestamp.
    IDLE_SECONDS = 5 * 60

    @app.before_request
    def enforce_idle_timeout():
        if 'user' not in session:
            return None
        last_activity = session.get('last_activity')
        if last_activity is None or time.time() - last_activity >= IDLE_SECONDS:
            session.clear()
            if request.path.startswith('/api/') or request.path.startswith('/auth/api/') or request.path == '/auth/activity':
                return jsonify({'error': 'Session expired due to inactivity.'}), 401
            return redirect(url_for('auth.login', timeout='1'))
        return None
        # Browser activity heartbeat
    # Added by Nicholas Smith - 10/25/2026
    @app.route('/auth/activity', methods=['POST'])
    def update_activity():
        if 'user' not in session:
            return jsonify({'error': 'Not logged in'}), 401

        session['last_activity'] = time.time()
        return jsonify({'status': 'active'}), 200

    

    @app.after_request
    def load_idle_script(response):
        # Reuse existing templates without changing their appearance.
        if ('user' in session and response.status_code == 200 and
                response.mimetype == 'text/html' and not response.direct_passthrough):
            html = response.get_data(as_text=True)
            if '</body>' in html.lower():
                import re
                reset = session.pop('client_idle_reset', False)
                bootstrap = '<script>localStorage.setItem("thevault_last_input", String(Date.now()));</script>' if reset else ''
                html = re.sub(r'</body>',
                    bootstrap + '<script src="/static/js/idle_timeout.js" defer></script></body>',
                    html, count=1, flags=re.IGNORECASE)
                response.set_data(html)
        return response

    # Run DB migrations on every startup so new columns are always present
    try:
        from init_db import create_vault_tables
        create_vault_tables()
    except Exception as _db_init_err:
        print(f"[startup] DB migration warning: {_db_init_err}")

    #The Welcome Screen (Default) Ryan Grimes 3/19/2026
    @app.route('/')
    def index():
        return render_template('index.html')

    # Route to the main storefront page after login - Updated 3/22/2026
    @app.route('/storefront')
    def storefront():
        return render_template('storefront.html')

    # Route to the "Create Storefront" form - Updated 3/22/2026
    @app.route('/create-storefront')
    def create_storefront():
        return render_template('create_storefront.html')

    # Route to the "Create Listing" form - Updated 3/24/2026
    @app.route('/create-listing')
    def create_listing():
        return render_template('create_listing.html')

    #Route to the Cart screen - Updated 3/22/2026
    @app.route('/cart')
    def cart():
        return render_template('cart.html')

    #Route to the Checkout - Updated 4/22/2026
    @app.route('/checkout')
    def checkout():
        if not session.get("user"):
            return redirect(url_for("auth.login"))
        return render_template('checkout.html')

    # Route to the Order Confirmation page - Added 4/22/2026
    @app.route('/order-confirmation')
    def order_confirmation():
        if not session.get("user"):
            return redirect(url_for("auth.login"))
        return render_template('order_confirmation.html')
    
    # Route to My Storefront dashboard page - Updated 4/9/2026
    @app.route('/my-storefront')
    def my_storefront():
        if not session.get("user"):
            return redirect(url_for("auth.login"))
        return render_template('my_storefront.html')
    
    #Route to the Campus Sitemap page - By Jaylen Belle / updated 10/16/2026
    @app.route('/sitemap')
    def sitemap():
        return render_template('sitemap.html')
    
    # Browse pages added by Noah Green 10/17/2026

    @app.get('/brands')
    def browse_brands():
        return render_template(
            'discover.html',
            page='brands',
            title='Explore Brands',
            subtitle='Find independent brands on The Pirate Cove.'
        )

    @app.get('/categories')
    def browse_categories():
        return render_template(
            'discover.html',
            page='categories',
            title='All Categories',
            subtitle='Browse the categories your campus storefronts offer.'
        )

    @app.get('/new-drops')
    def browse_new_drops():
        return render_template(
            'discover.html',
            page='new',
            title='New Drops',
            subtitle='See the latest active listings across The Pirate Cove.'
        )

    @app.get('/hot')
    def browse_hot():
        return render_template(
            'discover.html',
            page='hot',
            title='Hot!',
            subtitle='Discover the most ordered listings on The Pirate Cove.'
        )

    # Register Blueprints
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(listing_bp)
    app.register_blueprint(storefront_bp)
    app.register_blueprint(storefront_pages_bp)  # Updated by Day E 3/22/26
    app.register_blueprint(purchase_bp)
    app.register_blueprint(wishlist_bp)
    app.register_blueprint(admin_bp) # Updated 3/19/2026 by Ryan Grimes
    app.register_blueprint(returns_bp)
    app.register_blueprint(checkout_bp, url_prefix='/api')
    app.register_blueprint(menu_api_bp)    # Added by Anthony Jackson - dropdown menu data
    app.register_blueprint(menu_pages_bp)  # Added by Anthony Jackson - dropdown menu pages
    app.register_blueprint(messages_bp) # Added 10/20/26 for buyer-seller messaging
    app.register_blueprint(discovery_bp)
    app.register_blueprint(ratings_bp)  # Added by Anthony Jackson 10/21/26 - storefront ratings
    app.register_blueprint(profile_bp)  # Added by Anthony Jackson 10/21/26 - optional user profile

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
