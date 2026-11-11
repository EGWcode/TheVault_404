# The Pirate Cove — Campus Marketplace

**A cloud-based fashion marketplace for Hampton University students**

Designed & Built by Jaylen Belle, Nicholas Smith, Sidney Cerami, Noah Green, Tykeara Hammond, Nicco Hill, Anthony Jackson and Ethan Williams 
CSC 404 — Fall 26'

---

## Live Deployment

**http://the-vault-env.eba-phqfxm9m.us-east-2.elasticbeanstalk.com**

---

## What is The Pirate Cove?

The Pirate Cove is a web-based campus marketplace exclusively for Hampton University students. It allows student brand owners to create storefronts, publish clothing listings, and manage inventory, while other students can browse, wishlist, and purchase items.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask |
| Frontend | HTML, CSS, JavaScript |
| Database | PostgreSQL (AWS RDS) |
| Image Storage | Amazon S3 |
| Cloud Hosting | AWS Elastic Beanstalk |
| DB Adapter | psycopg2 |
| Version Control | GitHub |

---

## Install and Run (v0.9.0-beta)

You need **Python 3.10+** and **PostgreSQL**. The installer helps with both.

### macOS
1. Unzip the release (or clone the repo).
2. Double-click **`install.command`**. The first time, macOS may block it: right-click it, choose **Open**, then **Open** again.
3. Answer the questions (database on this computer or a server, then an optional admin account).
4. Double-click **`Launch Pirate Cove.command`**. The site opens in your browser. Keep the Terminal window open while you use it; close it to stop.

### Windows
1. Unzip the release (or clone the repo).
2. Double-click **`install.bat`**. If Python isn't installed, it opens python.org; install it with **"Add python.exe to PATH"** ticked, then run `install.bat` again.
3. Answer the questions.
4. Double-click **`Launch Pirate Cove.bat`**.

### What the installer does
- Creates a virtual environment in `venv/` and installs `requirements.txt`
- Writes `.env` with your database settings and a new random `SECRET_KEY` (an existing `.env` is kept unless you choose to replace it)
- On a Mac with Homebrew, offers to install and start PostgreSQL if it isn't running, and creates the database if it doesn't exist
- Creates the tables (`backend/init_db.py`)
- Offers to create an admin account (`backend/create_admin.py`)

Running the installer again is safe.

### Image uploads
With `AWS_S3_BUCKET` empty in `.env`, uploaded images are saved in `static/uploads/` on your computer.
Fill in the `AWS_` values to use Amazon S3 instead.

### Admin accounts
Admins log in at `/auth/admin-login`. Admin accounts live in the `users` table with `role = 'admin'`:

```bash
python backend/create_admin.py                   # create a new admin
python backend/create_admin.py --promote NAME    # make an existing user an admin
python backend/create_admin.py --demote NAME     # make an admin a normal user
```

### Manual setup (developers)

```bash
git clone https://github.com/EGWcode/TheVault_404.git
cd TheVault_404
python3 -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows
pip install -r requirements-dev.txt
cp .env.example .env            # then fill in your values
python backend/init_db.py
python app.py                   # http://127.0.0.1:5000 (set PORT=5001 if AirPlay uses 5000)
```

---

## Running Tests

```bash
python -m pytest backend/tests/test_admin.py backend/tests/test_messaging_feature.py
```

Tests that touch the database use the database in your `.env`.

---

## Building a Release

```bash
scripts/build_release.sh v0.9.0-beta
```

This makes `dist/PirateCove-v0.9.0-beta.zip` from the tagged commit, so only committed files go in.

---

## Team

| Name | Role |
|---|---|
| Ethan Williams | Project Manager, Admin backend & frontend |
| Nicco Hill | Co-PM, Wishlist & Purchase backend, Create Listing frontend |
| Nicholas Smith | Systems & Security Lead, Auth backend, Login/Signup/Cart frontend |
| Tykeara Hammond | Cloud Deployment Lead, Storefront & Listings backend & frontend, Returns system, AWS deployment |
| Jaylen Belle | Documentation Lead, User & Account Settings backend & frontend |
| Anthony Jackson| Database & App Support, Checkout backend and frontend |
| Sidney Cerami | Quality Assurance & Testing |
| Noah Green | Front End & UI Lead |
---

## Notes

- Restricted to Hampton University email addresses (`@hamptonu.edu` / `@my.hamptonu.edu`)
- No payment processing — checkout uses an in-person exchange model
- Deployed on AWS Free Tier
