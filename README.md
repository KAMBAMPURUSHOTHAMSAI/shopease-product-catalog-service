# ShopEase Product Catalog Microservice

An independent FastAPI microservice for ShopEase product catalog, category, pricing, search/filtering, and inventory management. It owns a dedicated MySQL database and validates JWT access tokens issued by the existing ShopEase Authentication Service. It does not implement user registration, login, or password storage.

This service is the main product catalog and inventory data owner for ShopEase. The separately developed `shopease-product-service` remains an independent training/demo service; product data is not automatically synchronized between the two services.

## Features

- Product and category CRUD APIs.
- Product search by name/SKU, category and price filtering, availability filtering, pagination, and sorting.
- Inventory stock-in and stock-out operations with transaction history.
- Low-stock endpoint with a configurable default threshold and per-request override.
- JWT authentication and Admin/Customer role-based access control.
- MySQL transactions with row locking to protect concurrent stock changes.
- Alembic database migrations, Docker Compose setup, pytest suite, and Postman collection.

## Technology stack

- Python 3.11, FastAPI, Uvicorn
- Pydantic v2, SQLAlchemy 2, MySQL 8.4, PyMySQL, Alembic
- PyJWT (HS256)
- Docker and Docker Compose
- pytest, FastAPI TestClient, httpx, Postman

## Project structure

```text
shopease-product-catalog-service/
├── app/
│   ├── main.py
│   ├── routers/          # Product, category, and inventory routes
│   ├── models/           # Product, category, and inventory models
│   ├── schemas/          # Pydantic request/response schemas
│   ├── services/         # Business logic
│   ├── core/             # Configuration and JWT security
│   └── database/         # SQLAlchemy connection/session setup
├── alembic/
│   └── versions/         # Database migration scripts
├── tests/                # Automated API tests
├── scripts/              # MySQL concurrency test script
├── postman/
│   └── ShopEase_Product_Catalog_Service.postman_collection.json
├── Dockerfile
├── docker-compose.yml
├── alembic.ini
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Database schema

Database: `shopease_product_catalog_db`.

- `categories`: unique category name, description, active flag, and timestamps.
- `products`: category foreign key, unique SKU, `DECIMAL(12,2)` prices, non-negative stock, active flag, and timestamps. Database constraints protect price, discount, and stock values.
- `inventory_transactions`: product foreign key, `IN`/`OUT` transaction type, quantity, previous stock, updated stock, remarks, and timestamp. The product foreign key uses `RESTRICT` so inventory audit history is not silently deleted.

Category deletion is blocked with HTTP 409 while products reference the category. Product deletion is blocked with HTTP 409 when inventory history exists; deactivate the product instead to preserve the audit trail.

## Authentication and authorization

The service validates JWT access tokens issued by the existing ShopEase Authentication Service. These values must match the Auth Service configuration and token contract:

- `JWT_SECRET_KEY`: exact same secret as the Auth Service `.env` file.
- `JWT_ALGORITHM=HS256`.
- `JWT_ISSUER=shopease-auth-service`.
- `sub`: numeric Auth Service user ID.
- `role`: `admin`, `administrator`, or `super_admin` for administrative access; `customer` for customer access.

All catalog APIs require a valid Bearer token. Customers can read active products and active categories. Administrative product/category mutations, inventory mutations, inventory history, and low-stock operations require an administrator role.

Never commit `.env` or expose JWT secrets. For production deployments, prefer asymmetric JWT signing with JWKS rather than distributing an HS256 signing secret to every service.

### Preparing an administrator test account

New Auth Service accounts may default to the `customer` role. For local training, use a dedicated test account and promote it through the Auth Service's own database/admin process; never edit or forge a JWT. If using the local Auth Service MySQL database, update only the designated test account's `users.role` to `admin`, then log in again through the Auth Service to receive a new token with `role: admin`. Keep ordinary test/customer accounts as `customer`. The Product Catalog Service does not own or modify Auth Service users.

## Environment setup

Copy the example environment file and edit it:

```powershell
Copy-Item .env.example .env
notepad .env
```

Set unique values for `DB_PASSWORD` and `DB_ROOT_PASSWORD`. Set `JWT_SECRET_KEY` to the exact Auth Service secret; do not leave the example placeholder in place. The `.env` file is excluded from Git and the Docker build context.

## Docker Compose (recommended)

Run these commands from the project root:

```powershell
docker compose config --quiet
docker compose build --no-cache catalog-api
docker compose up -d
docker compose ps
docker compose logs --tail=100 catalog-api
```

Compose starts:

- Catalog API: `http://localhost:8005` (container port 8005)
- MySQL: host port `3310` mapped to container port `3306`
- MySQL named volume: `catalog_mysql_data`
- Database hostname from inside the API container: `catalog-db` (do not use `localhost` from inside the API container)

The API waits for the MySQL health check, runs `alembic upgrade head`, and then starts Uvicorn.

- Swagger UI: `http://localhost:8005/docs`
- Health endpoint: `http://localhost:8005/health`

Stop the containers without deleting the database volume:

```powershell
docker compose down
```

Only when intentionally deleting all catalog data, remove the volume as well:

```powershell
docker compose down -v
```

**Warning:** `docker compose down -v` deletes the persisted catalog database volume and its data.

## Local development

Create and activate a Python 3.11 virtual environment. This project uses `.venv` in the examples below; it is excluded from Git.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Install the local test/concurrency tools as development dependencies:

```powershell
python -m pip install pytest httpx
```

If your configured package index does not provide a pinned dependency version, you can install from the official PyPI index:

```powershell
python -m pip install -r requirements.txt --index-url https://pypi.org/simple
```

For local API execution, start only the catalog database with Compose. The local API process connects to the published host port, so set `DB_HOST=127.0.0.1` and `DB_PORT=3310` in `.env`:

```powershell
docker compose up -d catalog-db
alembic upgrade head
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8005
```

## API catalogue

All routes require a valid Bearer JWT. Customer read routes return active products/categories only. Administrative operations require an `admin`, `administrator`, or `super_admin` role claim.

### Products

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/products/` | Create product (admin) |
| GET | `/api/products/` | List/search/filter/sort/page products (authenticated) |
| GET | `/api/products/{product_id}` | Get product details (active products for customers) |
| PUT | `/api/products/{product_id}` | Replace product (admin) |
| PATCH | `/api/products/{product_id}` | Partially update product (admin) |
| DELETE | `/api/products/{product_id}` | Delete only if no inventory history exists (admin) |

List query parameters:

- `search`: search by product name or SKU.
- `category_id`: filter by category.
- `min_price`, `max_price`: filter by price range.
- `available`: filter products by stock availability.
- `page`, `page_size`: pagination controls.
- `sort_by`: `name`, `price`, `created_at`, `stock_quantity`, or `updated_at`.
- `sort_order`: `asc` or `desc`.

The list response contains `items`, `total`, `page`, `page_size`, and `pages`.

Examples:

```text
GET /api/products/?search=mobile
GET /api/products/?category_id=1
GET /api/products/?min_price=1000&max_price=5000
GET /api/products/?page=1&page_size=10
GET /api/products/?sort_by=price&sort_order=asc
GET /api/products/?available=true
```

### Categories

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/categories/` | Create category (admin) |
| GET | `/api/categories/` | List active categories for customers; all categories for admin |
| GET | `/api/categories/{category_id}` | Get category (active category for customers) |
| PUT | `/api/categories/{category_id}` | Update, activate, or deactivate category (admin) |
| DELETE | `/api/categories/{category_id}` | Delete only if no products reference it (admin) |

### Inventory

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/inventory/{product_id}` | Get stock for a visible product |
| POST | `/api/inventory/{product_id}/stock-in` | Increase stock (admin) |
| POST | `/api/inventory/{product_id}/stock-out` | Decrease stock (admin) |
| GET | `/api/inventory/{product_id}/history` | Get stock transaction history (admin) |
| GET | `/api/inventory/low-stock` | List low-stock products (admin) |

`LOW_STOCK_THRESHOLD` defaults to 5 and can be overridden per request using the `threshold` query parameter (admin only).

## Inventory consistency and concurrency

Stock changes select the product row using `SELECT ... FOR UPDATE` (MySQL/InnoDB), calculate the new stock, and insert the inventory transaction in the same SQLAlchemy transaction. A commit failure rolls back both the stock update and its history row. A stock-out that would make stock negative returns HTTP 409. Product creation with opening stock greater than zero creates an initial `IN` history row. Product PUT/PATCH stock adjustments also create audit entries.

For a repeatable concurrency check, choose a product whose stock is exactly 10 units and use its actual product ID. Run the script from PowerShell with a fresh Admin access token:

```powershell
$env:ADMIN_ACCESS_TOKEN = "<admin access token>"
python scripts/concurrency_stock_check.py --product-id <product_id> --quantity 7
Remove-Item Env:ADMIN_ACCESS_TOKEN
```

The script sends two simultaneous stock-out requests for 7 units. Expected result: one HTTP 200 and one HTTP 409; final stock is 3. `SELECT FOR UPDATE` is supported by MySQL/InnoDB; SQLite test runs do not prove production row-lock behavior.

## HTTP status codes

- `200`: successful read, update, or stock operation.
- `201`: product/category created.
- `204`: deletion completed with no response body.
- `401`: missing, invalid, or expired JWT.
- `403`: customer attempted an administrative operation.
- `404`: resource not found or inactive resource requested by a customer.
- `409`: duplicate SKU/category, insufficient stock, or protected deletion.
- `422`: Pydantic or query-parameter validation error.

## Alembic commands

```powershell
alembic current
alembic history
alembic upgrade head
```

To inspect the database tables:

```powershell
docker compose exec catalog-db mysql -u root -p shopease_product_catalog_db
```

Then, at the MySQL prompt:

```sql
SHOW TABLES;
DESCRIBE categories;
DESCRIBE products;
DESCRIBE inventory_transactions;
SELECT id, name, sku, price, stock_quantity, is_active FROM products;
SELECT product_id, transaction_type, quantity, previous_stock, updated_stock
FROM inventory_transactions ORDER BY id;
EXIT;
```

## Testing

The automated tests use an isolated in-memory SQLite database and a test-only JWT key; they do not modify the Docker MySQL database.

Install test tools if they are not already installed:

```powershell
python -m pip install pytest httpx
```

Run the suite:

```powershell
python -m pytest -v
```

The project test run used during development completed with **24 passed**. Re-run tests after making code or dependency changes.

### Postman

Import `postman/ShopEase_Product_Catalog_Service.postman_collection.json` into Postman. Set `base_url` to `http://localhost:8005` and configure the token variables used by the collection with access tokens obtained from Auth Service login. Use an Auth Service account with role `admin` for mutations and a `customer` token to verify read-only access and HTTP 403 on administrative operations. The collection does not include login/register requests by design.

The manual test scenarios include product/category create and update, duplicate SKU/category and invalid input, search/filter/sort/pagination, stock IN/OUT, insufficient stock, history, low stock, role checks, missing/invalid/expired tokens, deletion protections, and concurrency. Perform the concurrency check against the MySQL Docker service; do not infer MySQL row-lock behavior from SQLite tests.

## GitHub submission

Before committing, confirm that `.env`, `.venv`, `venv`, and test caches are ignored and that `.env.example` contains placeholders only. Do not commit real database passwords, JWT secrets, or access tokens.

For a new local repository:

```powershell
git init
git branch -M main
git add .
git check-ignore -v .env .venv .pytest_cache
git diff --cached --check
git status
git commit -m "Build ShopEase Product Catalog Microservice with Inventory Management"
```

Connect the GitHub remote and push the `main` branch (replace the URL with your repository URL):

```powershell
git remote add origin https://github.com/<YOUR-USERNAME>/shopease-product-catalog-service.git
git push -u origin main
```
