# ShopEase Product Catalog Microservice

Independent FastAPI microservice for product, category, pricing, search/filtering and inventory management. It uses its own MySQL database and validates JWT access tokens issued by the existing ShopEase Authentication Service. It does not implement registration, login or password storage.

## Technology

- Python 3.11, FastAPI, Uvicorn
- Pydantic v2, SQLAlchemy 2, MySQL 8.4, PyMySQL, Alembic
- PyJWT (HS256), Docker, Docker Compose
- pytest, FastAPI TestClient, Postman collection

## Project structure

```text
shopease-product-catalog-service/
├── app/
│   ├── main.py
│   ├── routers/       # product_routes.py, category_routes.py, inventory_routes.py
│   ├── models/        # product_model.py, category_model.py, inventory_model.py
│   ├── schemas/       # product_schema.py, category_schema.py, inventory_schema.py
│   ├── services/      # product_service.py, category_service.py, inventory_service.py
│   ├── core/          # config.py, security.py
│   └── database/      # connection.py
├── alembic/versions/
├── tests/
├── postman/ShopEase_Product_Catalog_Service.postman_collection.json
├── Dockerfile
├── docker-compose.yml
├── alembic.ini
├── requirements.txt
├── .env.example
└── README.md
```

## Database schema

Database: `shopease_product_catalog_db`.

- `categories`: unique name, description, active flag and timestamps.
- `products`: category FK, unique SKU, Decimal(12,2) prices, non-negative stock, active flag and timestamps. CHECK constraints prevent invalid prices, discounts and negative stock.
- `inventory_transactions`: product FK, IN/OUT transaction type, quantity, previous stock, updated stock, remarks and timestamp. FK uses RESTRICT so audit history is not silently deleted.

Category deletion is blocked with HTTP 409 while products reference it. Product deletion is blocked with HTTP 409 when inventory history exists; deactivate the product instead to preserve the audit trail.

## Authentication and authorization

The service validates JWT access tokens from the existing ShopEase Authentication Service. The following values must match that service:

- `JWT_SECRET_KEY`: exact same secret as Auth Service `.env`.
- `JWT_ALGORITHM=HS256`.
- `JWT_ISSUER=shopease-auth-service`.
- `sub`: numeric Auth Service user ID.
- `role`: `admin` / `administrator` / `super_admin` for administrative access; customer role for customer access.

All catalog APIs require a valid Bearer token. Customers can read active products and active categories. Administrative create/update/delete/category/inventory mutation/history/low-stock endpoints require an administrator role. Never commit `.env` or expose JWT secrets. For production, prefer asymmetric JWT signing/JWKS rather than distributing an HS256 signing secret to every service.

### Preparing an administrator test account

New accounts may default to the `customer` role. For testing administrative routes, use a dedicated test account and update its role through the **Authentication Service's own database/admin process** (never edit or forge the JWT). For a local training database, connect to the Auth Service's MySQL database, update only the designated test account's `users.role` to `admin`, then log in again through the Auth Service to receive a new token containing `role: admin`. Keep ordinary test/customer accounts as `customer`. The Product Catalog Service does not own or modify Auth Service users.

## Environment setup

```powershell
Copy-Item .env.example .env
notepad .env
```

Set unique `DB_PASSWORD` and `DB_ROOT_PASSWORD`. Copy `JWT_SECRET_KEY` securely from `shopease-auth-service/.env`; do not use the placeholder. `.env` is ignored by Git and Docker build context.

## Docker Compose (recommended)

From this project root:

```powershell
docker compose config --quiet
docker compose build --no-cache catalog-api
docker compose up -d
docker compose ps
docker compose logs --tail=100 catalog-api
```

Compose runs:
- Catalog API: `http://localhost:8005` (container port 8005)
- MySQL: host port `3310` mapped to container port `3306`
- MySQL named volume: `catalog_mysql_data`
- Container DB hostname: `catalog-db` (never `localhost` from the API container)

The API waits for the MySQL health check, runs `alembic upgrade head`, then starts Uvicorn. Swagger: `http://localhost:8005/docs`; health: `http://localhost:8005/health`.

Stop without deleting the database volume:

```powershell
docker compose down
```

Only when intentionally deleting all catalog data:

```powershell
docker compose down -v
```

## Local development

```powershell
py -3.11 -m venv venv
.env\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

For local API execution, start only the catalog DB with Compose, then set `.env` `DB_HOST=127.0.0.1` and `DB_PORT=3310`:

```powershell
docker compose up -d catalog-db
alembic upgrade head
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8005
```

## API catalogue

All API routes require Bearer JWT. Customer read routes return active products/categories only. Administrative operations require `admin`, `administrator` or `super_admin` role claim.

### Products

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/products/` | Create product (admin) |
| GET | `/api/products/` | List/search/filter/sort/page products (authenticated) |
| GET | `/api/products/{product_id}` | Product details (active for customer) |
| PUT | `/api/products/{product_id}` | Replace product (admin) |
| PATCH | `/api/products/{product_id}` | Partial update (admin) |
| DELETE | `/api/products/{product_id}` | Delete only if no inventory history (admin) |

List query parameters: `search`, `category_id`, `min_price`, `max_price`, `available`, `page`, `page_size`, `sort_by` (`name`, `price`, `created_at`, `stock_quantity`, `updated_at`), `sort_order` (`asc`, `desc`). Response contains `items`, `total`, `page`, `page_size`, `pages`.

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
| GET | `/api/categories/` | List active categories for customers; all for admin |
| GET | `/api/categories/{category_id}` | Get category (active for customer) |
| PUT | `/api/categories/{category_id}` | Update/activate/deactivate category (admin) |
| DELETE | `/api/categories/{category_id}` | Delete only if no products reference it (admin) |

### Inventory

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/inventory/{product_id}` | Get stock for visible product |
| POST | `/api/inventory/{product_id}/stock-in` | Increase stock (admin) |
| POST | `/api/inventory/{product_id}/stock-out` | Decrease stock (admin) |
| GET | `/api/inventory/{product_id}/history` | Stock history (admin) |
| GET | `/api/inventory/low-stock` | Low-stock products (admin) |

`LOW_STOCK_THRESHOLD` defaults to 5 and can be overridden per request using the `threshold` query parameter (admin only).

## Inventory consistency

Stock changes select the product row using `SELECT ... FOR UPDATE` (MySQL/InnoDB), calculate the new value, and insert the inventory transaction in the same SQLAlchemy transaction. Commit failure rolls back both the quantity update and history row. Stock-out below zero returns HTTP 409. Product creation with an opening stock greater than zero creates an initial IN history row. Product PUT/PATCH stock adjustments also create audit entries.

For a repeatable concurrency check, create a product with exactly 10 units of stock, then run the supplied script from PowerShell:

```powershell
$env:ADMIN_ACCESS_TOKEN = "<admin access token>"
python scripts/concurrency_stock_check.py --product-id 1 --quantity 7
Remove-Item Env:ADMIN_ACCESS_TOKEN
```

The script sends two simultaneous stock-out requests for 7 units. Expected: one HTTP 200 and one HTTP 409; final stock is 3. `SELECT FOR UPDATE` is supported by MySQL/InnoDB; SQLite test runs do not prove production row-lock behavior.

## Status codes

- `200`: successful read/update/stock operation
- `201`: created product/category
- `204`: deletion
- `401`: missing, invalid or expired JWT
- `403`: customer attempting administrative operation
- `404`: missing/inactive resource for customer
- `409`: duplicate SKU/category, insufficient stock, or protected deletion
- `422`: Pydantic/query validation error

## Alembic commands

```powershell
alembic current
alembic history
alembic upgrade head
```

Verify DB tables:

```powershell
docker compose exec catalog-db mysql -u root -p shopease_product_catalog_db
```

```sql
SHOW TABLES;
DESCRIBE categories;
DESCRIBE products;
DESCRIBE inventory_transactions;
SELECT id, name, sku, price, stock_quantity, is_active FROM products;
SELECT product_id, transaction_type, quantity, previous_stock, updated_stock FROM inventory_transactions ORDER BY id;
EXIT;
```

## Testing

Automated tests use an isolated in-memory SQLite database and test-only JWT key; they do not change the Docker MySQL database.

```powershell
python -m pytest -q
```

Postman: import `postman/ShopEase_Product_Catalog_Service.postman_collection.json`, set `base_url=http://localhost:8005` and `access_token` to a token copied from Auth Service login. Use an Auth Service account with role `admin` for mutations; use a `customer` token to verify read-only access and 403 on admin operations. The collection has no login/register requests by design.

Test the mandatory scenarios listed in the training assignment, including invalid product/category/SKU, filters/sorting/pagination, stock IN/OUT and insufficient stock, history, low stock, role checks, invalid/missing token and concurrency. The concurrency check must be performed against the MySQL Docker service, not inferred from SQLite tests.

## GitHub submission

```powershell
git init
git branch -M main
git add app alembic tests postman Dockerfile docker-compose.yml alembic.ini requirements.txt README.md .env.example .gitignore .dockerignore .gitattributes
git check-ignore -v .env venv
git status
git commit -m "Build ShopEase Product Catalog Microservice"
git remote add origin https://github.com/<YOUR-USERNAME>/shopease-product-catalog-service.git
git push -u origin main
```

Do not commit `.env`, virtual environments, JWT secrets or database passwords.
