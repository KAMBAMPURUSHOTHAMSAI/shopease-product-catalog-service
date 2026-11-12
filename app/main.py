from fastapi import FastAPI
from app.core.config import get_settings
from app.routers import product_routes, category_routes, inventory_routes
settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.app_version,
    description="Independent ShopEase Product Catalog Microservice with categories, product search and inventory management.")
app.include_router(product_routes.router)
app.include_router(category_routes.router)
app.include_router(inventory_routes.router)

@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "service": "ShopEase Product Catalog Service"}
