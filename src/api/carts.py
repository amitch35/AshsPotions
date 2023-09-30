from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/carts",
    tags=["cart"],
    dependencies=[Depends(auth.get_api_key)],
)

RED_PRICE = 50

class NewCart(BaseModel):
    customer: str


@router.post("/")
def create_cart(new_cart: NewCart):
    """ """
    with db.engine.begin() as connection:
        sql = f"INSERT INTO shopping_carts (customer, red_potions_requested) VALUES ({new_cart.customer}, 0)"
        connection.execute(sqlalchemy.text(sql))
        sql = f"SELECT * FROM shopping_carts WHERE customer = {new_cart.customer} AND red_potions_requested = 0 ORDER BY id"
        result = connection.execute(sqlalchemy.text(sql))
        record = result.first()
    return {f"cart_id: {record.id}"}


@router.get("/{cart_id}")
def get_cart(cart_id: int):
    """ """
    with db.engine.begin() as connection:
        sql = f"SELECT * FROM shopping_carts WHERE id = {cart_id}"
        result = connection.execute(sqlalchemy.text(sql))
        if result:
            record = result.first()
            print(f"Cart with id: {record.id} for customer: {record.customer} contains {record.red_potions_requested} red potions")
            return { f"Cart with id: {record.id} for customer: {record.customer} contains {record.red_potions_requested} red potions"}
        else:
            print(f"Cart with id {cart_id} does not exist")
            return "No cart found"


class CartItem(BaseModel):
    quantity: int


@router.post("/{cart_id}/items/{item_sku}")
def set_item_quantity(cart_id: int, item_sku: str, cart_item: CartItem):
    """ """
    with db.engine.begin() as connection:
        sql = f"SELECT * FROM shopping_carts WHERE id = {cart_id}"
        result = connection.execute(sqlalchemy.text(sql))
        if result:
            record = result.first()
            # check if SKU is an item that I offer in my catalog
            if item_sku == "RED_POTION_0":
                sql = f"UPDATE shopping_carts SET red_potions_requested = {cart_item.quantity} WHERE id = {cart_id}"
                return "OK"
            else:
                print(f"Requested item, with SKU: {item_sku} is not offered")
                return "No matching sku found in catalog"
        else:
            print(f"Cart with id {cart_id} does not exist")
            return "No cart found"


class CartCheckout(BaseModel):
    payment: str

@router.post("/{cart_id}/checkout")
def checkout(cart_id: int, cart_checkout: CartCheckout):
    """ """
    with db.engine.begin() as connection:
        sql = f"SELECT * FROM shopping_carts WHERE id = {cart_id}"
        result = connection.execute(sqlalchemy.text(sql))
        if result:
            record = result.first()
            selling = record.red_potions_requested
            price = RED_PRICE * selling
            if cart_checkout.payment < price:
                selling = cart_checkout.payment / RED_PRICE
                price = RED_PRICE * selling
            sql = f"SELECT * FROM global_inventory"
            result = connection.execute(sqlalchemy.text(sql))
            inv = result.first() # inventory is on a single row
            if selling > inv.num_red_potions:
                selling = inv.num_red_potions
            sql = f"UPDATE global_inventory SET gold = gold + {price}, num_red_potions = num_red_potions - {selling} "
            sql += f"DELETE FROM shopping_carts WHERE id = {cart_id}"
            connection.execute(sqlalchemy.text(sql))
            return {"total_potions_bought": selling, "total_gold_paid": price}
        else:
            print(f"Cart with id {cart_id} does not exist")
            return "No cart found"
