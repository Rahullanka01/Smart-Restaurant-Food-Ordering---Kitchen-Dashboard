# Tastique

A beginner-friendly restaurant ordering site and staff kitchen board built with Django, SQLite, Bootstrap, and a browser localStorage cart.

## Project Structure

```text
.
|-- config/
|   |-- __init__.py
|   |-- settings.py
|   |-- urls.py
|   `-- wsgi.py
|-- restaurant/
|   |-- __init__.py
|   |-- management/
|   |   |-- __init__.py
|   |   `-- commands/
|   |       |-- __init__.py
|   |       `-- seed_menu.py
|   |-- migrations/
|   |   |-- __init__.py
|   |   |-- 0001_initial.py
|   |   |-- 0002_alter_order_table_number.py
|   |   |-- 0003_menuitem_image_source_url.py
|   |   `-- 0004_menuitem_image_path.py
|   |-- admin.py
|   |-- apps.py
|   |-- currency.py
|   |-- forms.py
|   |-- models.py
|   |-- tests.py
|   |-- urls.py
|   |-- views.py
|   `-- templatetags/
|       |-- __init__.py
|       `-- currency.py
|-- static/
|   |-- css/site.css
|   |-- js/cart.js
|   `-- images/
|       |-- dish-placeholder.svg
|       `-- menu/ (47 unique local dish photos)
|-- templates/
|   |-- 404.html
|   |-- base.html
|   `-- restaurant/
|       |-- cart.html
|       |-- checkout.html
|       |-- home.html
|       |-- kitchen.html
|       |-- order_confirmation.html
|       `-- track_order.html
|-- .env.example
|-- .gitignore
|-- manage.py
|-- render.yaml
|-- requirements.txt
`-- README.md
```

Templates belong in `templates/`; styles and browser code belong in `static/css/` and `static/js/`. The Python code is in the `config/` project package and `restaurant/` app. Django's built-in admin is available at `/admin/`.

## Run Locally

Use Python 3.11 or newer. In PowerShell, open this folder and run:

```powershell
py -3 --version
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py makemigrations restaurant
python manage.py migrate
python manage.py seed_menu
python manage.py download_menu_images
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/`. In PowerShell, if script activation is disabled, use `\.venv\Scripts\python.exe` in place of `python` for each command. Settings load the ignored `.env` file with `python-dotenv`; values set in the shell take precedence. For production, always provide a strong `SECRET_KEY` through the hosting environment. Render supplies a generated secret through `render.yaml`.

## Sample Menu

`python manage.py seed_menu` creates or updates the seven Indian categories and 39 Indian sample dishes, preserving the original eight examples and their numeric prices. Then run `python manage.py download_menu_images` to save one validated image per menu item under `static/images/menu/`. The downloader skips existing files, rejects duplicate image bytes, validates file signatures, and does not prompt or overwrite files. It uses the existing verified sources and Openverse-licensed Flickr thumbnails when Wikimedia rate-limits direct requests. Commons/Openverse source pages are linked from cards where supplied; Unsplash images are covered by its license, which does not require attribution. Prices remain rupees; no conversion is performed. Missing or broken photos fall back to the local `static/images/dish-placeholder.svg`.

The `0004_menuitem_image_path` migration adds only a static-path field. Static serving was already configured through `STATICFILES_DIRS`, `STATIC_ROOT`, and WhiteNoise, so no media settings or `urls.py` changes are needed. Include these image files in the repository so `collectstatic` copies them during deployment.

## Test the Features

1. Browse the menu, filter by category, and search for a dish such as “Mysore” or “Biryani.” Check the green vegetarian and red non-vegetarian labels and open an image source link. Add items; the bag count updates and your cart remains in the browser after a refresh.
2. Open the cart, adjust quantities or remove a line, and confirm the displayed subtotal, estimated 8% tax, and total.
3. Submit checkout with a name, a valid phone number, and a table number. The server reloads each current menu price, checks availability and quantity, and creates the order in SQLite.
4. Save the UUID shown on the confirmation page. Use it on **Track order** to see the order status and line items.
5. Sign in at `/admin/` with a staff account, then open **Kitchen**. Set an order to Preparing, Ready, or Completed. The customer tracking page reflects the update. Only active staff can access the kitchen routes.
6. Visit an invalid URL to see the custom 404 page in production mode. In `DEBUG=True`, Django displays its technical 404 page instead. The automated test suite verifies the branded page with `DEBUG=False`; a manual production-mode run also needs a non-placeholder `SECRET_KEY` and an `ALLOWED_HOSTS` value that includes your local host.

Run the automated checks with:

```powershell
python manage.py check
python manage.py test
```

The tests verify page rendering and the custom 404, repeatable seeding of all 39 Indian dishes, unique local image paths and safe downloader behavior, Indian-number grouping, admin INR labels, server-side pricing, unavailable item and fractional-quantity rejection, session cart cleanup, and staff-only kitchen updates.

## GitHub

Create an empty repository on GitHub. In this project folder:

```powershell
git init
git add .
git commit -m "Build Tastique restaurant ordering app"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

Replace the remote URL with your own repository URL. Do not commit `.env`, passwords, or `db.sqlite3`; `.gitignore` excludes them.

## Deploy on Render

1. Push the project to GitHub, then in Render choose **New + → Blueprint** and connect that repository. Render reads `render.yaml`.
2. The build command is `pip install -r requirements.txt && python manage.py collectstatic --no-input`.
3. The start command runs `python manage.py migrate --noinput && python manage.py ensure_menu` before Gunicorn. This initializes a fresh Render runtime database and inserts the sample menu only if it is empty; it does not overwrite an existing menu.
4. `render.yaml` generates `SECRET_KEY`, sets `DEBUG=false`, and sets the CSRF trusted origin pattern. Django also allows Render's `RENDER_EXTERNAL_HOSTNAME` automatically. Do not set a committed secret in the repository.
5. After deployment, create a staff login from the Render shell with `python manage.py createsuperuser`, then manage menu records in `/admin/`.

Local SQLite data does not get uploaded to GitHub and is not copied into Render. Render starts with its own `db.sqlite3`, so local admin edits and orders do not automatically appear there. The startup command migrates and seeds the sample menu for an empty database; add any custom menu records and create staff users through the deployed admin.

This assignment intentionally uses SQLite. Render's free service filesystem is ephemeral: `db.sqlite3`, including orders and staff accounts, can be lost after a restart, redeploy, or instance replacement. The startup seed repopulates the example menu when the database is empty, but it cannot restore custom rows or orders. This is suitable for a class demo, not durable production orders. A persistent disk can change filesystem durability where the plan supports it, but production multi-instance applications should use a managed database; that would no longer meet the SQLite-only assignment requirement.

## How the Order Flow Works

The browser stores only menu item IDs and quantities in localStorage. Checkout sends those values to Django, where the app validates each quantity, looks up currently available records, and calculates subtotal, tax, and total from database prices inside a database transaction. Order items save a name and price snapshot so later menu edits do not change an existing receipt. Django forms, CSRF tokens, staff checks, and environment-based deployment secrets protect the relevant requests.