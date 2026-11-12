from decimal import Decimal
import pytest
from app.models.product_model import Product
from app.models.inventory_model import InventoryTransaction
from app.database.connection import get_db
from tests.conftest import TestingSessionLocal

CATEGORY={"name":"Electronics","description":"Electronic products","is_active":True}
PRODUCT={"category_id":1,"name":"Android Mobile","description":"Test handset","sku":"MOB-001","price":"25000.00","discount_price":"23000.00","stock_quantity":10,"brand":"ShopEase","image_url":None,"is_active":True}

def create_category(client, headers): return client.post('/api/categories/', json=CATEGORY, headers=headers)
def create_product(client, headers): return client.post('/api/products/', json=PRODUCT, headers=headers)

def test_health(client):
    r=client.get('/health'); assert r.status_code==200 and r.json()['status']=='ok'
def test_missing_token_is_401(client): assert client.get('/api/products/').status_code==401
def test_customer_cannot_create_category(client, customer_headers): assert client.post('/api/categories/',json=CATEGORY,headers=customer_headers).status_code==403
def test_admin_create_category_and_duplicate(client, admin_headers):
    assert create_category(client,admin_headers).status_code==201
    assert create_category(client,admin_headers).status_code==409
def test_customer_sees_only_active_categories(client, admin_headers, customer_headers):
    create_category(client,admin_headers)
    r=client.get('/api/categories/',headers=customer_headers); assert r.status_code==200 and len(r.json())==1
    client.put('/api/categories/1',json={"name":"Electronics","description":"off","is_active":False},headers=admin_headers)
    assert client.get('/api/categories/',headers=customer_headers).json()==[]
def test_admin_create_product_and_opening_stock_history(client, admin_headers):
    create_category(client,admin_headers); r=create_product(client,admin_headers)
    assert r.status_code==201 and r.json()['sku']=='MOB-001'
    h=client.get('/api/inventory/1/history',headers=admin_headers)
    assert h.status_code==200 and h.json()[0]['transaction_type']=='IN' and h.json()[0]['updated_stock']==10
def test_duplicate_sku_rejected(client,admin_headers):
    create_category(client,admin_headers); assert create_product(client,admin_headers).status_code==201
    p={**PRODUCT,"name":"Another Mobile"}; assert client.post('/api/products/',json=p,headers=admin_headers).status_code==409
def test_invalid_category_rejected(client,admin_headers):
    r=client.post('/api/products/',json={**PRODUCT,"category_id":999},headers=admin_headers); assert r.status_code==404
def test_negative_price_validation(client,admin_headers):
    create_category(client,admin_headers); r=client.post('/api/products/',json={**PRODUCT,"price":"-5"},headers=admin_headers); assert r.status_code==422
def test_customer_lists_only_active_products(client,admin_headers,customer_headers):
    create_category(client,admin_headers); create_product(client,admin_headers)
    r=client.get('/api/products/',headers=customer_headers); assert r.status_code==200 and r.json()['total']==1
    client.patch('/api/products/1',json={"is_active":False},headers=admin_headers)
    assert client.get('/api/products/',headers=customer_headers).json()['total']==0
def test_customer_cannot_mutate_product(client,admin_headers,customer_headers):
    create_category(client,admin_headers); create_product(client,admin_headers)
    assert client.patch('/api/products/1',json={"name":"Blocked"},headers=customer_headers).status_code==403
def test_search_filter_pagination_sort(client,admin_headers,customer_headers):
    create_category(client,admin_headers)
    create_product(client,admin_headers)
    p={**PRODUCT,"name":"Android Mobile Pro","sku":"MOB-002","price":"30000.00","stock_quantity":0}
    client.post('/api/products/',json=p,headers=admin_headers)
    r=client.get('/api/products/?search=mobile&page=1&page_size=1&sort_by=price&sort_order=asc',headers=customer_headers)
    assert r.status_code==200 and r.json()['total']==2 and len(r.json()['items'])==1 and r.json()['items'][0]['sku']=='MOB-001'
def test_product_get_and_update_patch(client,admin_headers):
    create_category(client,admin_headers); create_product(client,admin_headers)
    assert client.get('/api/products/1',headers=admin_headers).status_code==200
    updated={**PRODUCT,"name":"Updated Mobile","sku":"MOB-001","price":"26000.00","discount_price":None}
    assert client.put('/api/products/1',json=updated,headers=admin_headers).status_code==200
    assert client.patch('/api/products/1',json={"brand":"New Brand"},headers=admin_headers).json()['brand']=='New Brand'
def test_stock_in_out_history_and_negative_guard(client,admin_headers):
    create_category(client,admin_headers); create_product(client,admin_headers)
    assert client.post('/api/inventory/1/stock-in',json={"quantity":5,"remarks":"Restock"},headers=admin_headers).json()['stock_quantity']==15
    assert client.post('/api/inventory/1/stock-out',json={"quantity":3},headers=admin_headers).json()['stock_quantity']==12
    assert client.post('/api/inventory/1/stock-out',json={"quantity":99},headers=admin_headers).status_code==409
    hist=client.get('/api/inventory/1/history',headers=admin_headers).json()
    assert len(hist)==3 and hist[0]['updated_stock']==12

def test_inventory_admin_only(client,admin_headers,customer_headers):
    create_category(client,admin_headers); create_product(client,admin_headers)
    assert client.post('/api/inventory/1/stock-in',json={"quantity":1},headers=customer_headers).status_code==403
    assert client.get('/api/inventory/low-stock',headers=customer_headers).status_code==403

def test_low_stock_endpoint(client,admin_headers):
    create_category(client,admin_headers); create_product(client,admin_headers)
    r=client.get('/api/inventory/low-stock?threshold=10',headers=admin_headers)
    assert r.status_code==200 and len(r.json())==1

def test_category_delete_blocked_when_products_exist(client,admin_headers):
    create_category(client,admin_headers); create_product(client,admin_headers)
    assert client.delete('/api/categories/1',headers=admin_headers).status_code==409

def test_product_delete_blocked_to_preserve_inventory_history(client,admin_headers):
    create_category(client,admin_headers); create_product(client,admin_headers)
    assert client.delete('/api/products/1',headers=admin_headers).status_code==409
    assert client.patch('/api/products/1',json={"is_active":False},headers=admin_headers).status_code==200


def test_invalid_token_is_401(client):
    r=client.get('/api/categories/',headers={"Authorization":"Bearer invalid.token.value"})
    assert r.status_code==401

def test_customer_cannot_view_inactive_product(client,admin_headers,customer_headers):
    create_category(client,admin_headers); create_product(client,admin_headers)
    client.patch('/api/products/1',json={"is_active":False},headers=admin_headers)
    assert client.get('/api/products/1',headers=customer_headers).status_code==404

def test_zero_stock_change_quantity_rejected(client,admin_headers):
    create_category(client,admin_headers); create_product(client,admin_headers)
    assert client.post('/api/inventory/1/stock-in',json={"quantity":0},headers=admin_headers).status_code==422

def test_min_price_greater_than_max_price_rejected(client,admin_headers,customer_headers):
    create_category(client,admin_headers); create_product(client,admin_headers)
    r=client.get('/api/products/?min_price=5000&max_price=1000',headers=customer_headers)
    assert r.status_code==422

def test_category_delete_succeeds_when_empty(client,admin_headers):
    create_category(client,admin_headers)
    assert client.delete('/api/categories/1',headers=admin_headers).status_code==204


def test_expired_token_is_401(client):
    from tests.conftest import make_token
    expired = make_token(user_id=8, role="customer", minutes=-1)
    r=client.get('/api/products/',headers={"Authorization":f"Bearer {expired}"})
    assert r.status_code==401
