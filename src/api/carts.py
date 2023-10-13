from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/carts",
    tags=["cart"],
    dependencies=[Depends(auth.get_api_key)],
)

class NewCart(BaseModel):
    customer: str

REQUESTED_TOO_MANY_POTIONS = 2004

@router.post("/")
def create_cart(new_cart: NewCart):
    """ """
    print("----New Cart----")
    with db.engine.begin() as connection:
        print(f"Creating cart for: {new_cart.customer}")
        sql = f"INSERT INTO shopping_carts (customer) VALUES ('{new_cart.customer}');"
        connection.execute(sqlalchemy.text(sql))
        sql = f"SELECT * FROM shopping_carts WHERE customer = '{new_cart.customer}' ORDER BY id desc"
        result = connection.execute(sqlalchemy.text(sql))
        record = result.first()
        print(f"{new_cart.customer} got cart id: {record.id}")
    return {"cart_id": record.id}


@router.get("/{cart_id}")
def get_cart(cart_id: int):
    """ """
    print("----Get Cart----")
    with db.engine.begin() as connection:
        sql = f"SELECT * FROM shopping_carts WHERE id = {cart_id}"
        result = connection.execute(sqlalchemy.text(sql))
        record = result.first()
        if record:
            print(f"Cart with id: {record.id} is for customer: {record.customer}")
            return { f"Cart with id: {record.id} is for customer: {record.customer}"}
        else:
            print(f"Cart with id {cart_id} does not exist")
        return f"Cart with id {cart_id} does not exist"


class CartItem(BaseModel):
    quantity: int


@router.post("/{cart_id}/items/{item_sku}")
def set_item_quantity(cart_id: int, item_sku: str, cart_item: CartItem):
    """ """
    print("----Add to Cart----")
    with db.engine.begin() as connection:
        sql = f"SELECT * FROM shopping_carts WHERE id = {cart_id}"
        result = connection.execute(sqlalchemy.text(sql))
        cart = result.first()
        if cart:
            if cart_item.quantity == 0: # if requesting 0 potions
                sql = f"DELETE FROM cart_contents WHERE cart_id = {cart_id} AND potion_sku = '{item_sku}'; "
                connection.execute(sqlalchemy.text(sql))
                return {"success": True}
            # check if SKU is an item that is offered in shop catalog
            sql = f"SELECT quantity FROM potions WHERE sku = '{item_sku}'; "
            result = connection.execute(sqlalchemy.text(sql))
            stock = result.first()
            if stock.quantity:
                sql = f"SELECT * FROM cart_contents WHERE cart_id = {cart_id} AND potion_sku = '{item_sku}'; "
                result = connection.execute(sqlalchemy.text(sql))
                record = result.first()
                if record is not None: # if updating the quantity asked for
                    print("Item already in cart, updating ...")
                    sql = f"UPDATE cart_contents SET quantity_requested = {cart_item.quantity} "
                    sql += f"WHERE id = {record.id}; "
                else: # adding new item to cart
                    print("New item added to cart ...")
                    sql = f"INSERT INTO cart_contents (cart_id, potion_sku, quantity_requested) "
                    sql += f"VALUES ({cart_id}, '{item_sku}', {cart_item.quantity})"
                connection.execute(sqlalchemy.text(sql))
                return {"success": True}
            else:
                print(f"Requested item, with SKU: {item_sku} is not offered")
                return {"success": False}
        else:
            print(f"Cart with id {cart_id} does not exist")
            return {"success": False}


class CartCheckout(BaseModel):
    payment: str

@router.post("/{cart_id}/checkout")
def checkout(cart_id: int, cart_checkout: CartCheckout):
    """ """
    print("----Cart Checkout----")
    with db.engine.begin() as connection:
        sql = f"SELECT * FROM shopping_carts WHERE id = {cart_id}; "
        result = connection.execute(sqlalchemy.text(sql))
        cart = result.first()
        print(f"Cart {cart_id}: {cart}")
        if cart: # if there exists a cart with the given id
            sql = f"SELECT * FROM cart_contents AS cnt "
            sql += f"JOIN potions AS pot ON cnt.potion_sku = pot.sku "
            sql += f"WHERE cart_id = {cart_id}; "
            result = connection.execute(sqlalchemy.text(sql))
            cart_content = result.first()
            transaction = False
            total = 0
            selling = 0
            if cart_content: # if there is anything in the cart
                # check validity of cart and determine total price
                result = connection.execute(sqlalchemy.text(sql))
                for record in result:
                    if record.quantity < record.quantity_requested:
                        print(f"Cart with id {cart_id} requested too many potions (insufficient stock)")
                        sql = f"INSERT INTO transactions (cart_id, success, payment, gold_paid) "
                        sql += f"VALUES ({cart_id}, {transaction}, '{cart_checkout.payment}', {REQUESTED_TOO_MANY_POTIONS}); "
                        connection.execute(sqlalchemy.text(sql))
                        return "Insufficient Potion Stock"
                    selling += record.quantity_requested
                    total += record.price * record.quantity_requested
                # execute transaction 
                print(f"Cart {cart_id} Completing transaction for {cart.customer}")
                result = connection.execute(sqlalchemy.text(sql))
                transaction = True
                sql = f"UPDATE global_inventory SET gold = gold + {total}; "
                for record in result:
                    sql += f"UPDATE potions "
                    sql += f"SET quantity = quantity - {record.quantity_requested} WHERE sku = '{record.sku}'; "
            else:
                sql = ""
                print(f"Cart with id {cart_id} was empty")
            #sql += f"DELETE FROM shopping_carts WHERE id = {cart_id}; " 
            sql += f"INSERT INTO transactions (cart_id, success, payment, gold_paid) "
            sql += f"VALUES ({cart_id}, {transaction}, '{cart_checkout.payment}', {total}); "
            connection.execute(sqlalchemy.text(sql))

            # Update total potions count in global inventory
            sql = f"SELECT * FROM potions; "
            result = connection.execute(sqlalchemy.text(sql))
            num_potions = 0
            for record in result:
                num_potions += record.quantity
            sql = f"UPDATE global_inventory SET num_potions = {num_potions}; "
            connection.execute(sqlalchemy.text(sql))

            return {"success": transaction, "total_potions_bought": selling, "total_gold_paid": total}
        else:
            print(f"Cart with id {cart_id} does not exist")
            return {"success": False, "total_potions_bought": 0, "total_gold_paid": 0}
