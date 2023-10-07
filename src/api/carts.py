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

RED_PRICE = 50

class NewCart(BaseModel):
    customer: str


@router.post("/")
def create_cart(new_cart: NewCart):
    """ """
    with db.engine.begin() as connection:
        sql = f"INSERT INTO shopping_carts (customer) VALUES ('{new_cart.customer}');"
        connection.execute(sqlalchemy.text(sql))
        sql = f"SELECT * FROM shopping_carts WHERE customer = '{new_cart.customer}' ORDER BY id desc"
        result = connection.execute(sqlalchemy.text(sql))
        record = result.first()
    return {f"cart_id: {record.id}"}


@router.get("/{cart_id}")
def get_cart(cart_id: int):
    """ """
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
    with db.engine.begin() as connection:
        sql = f"SELECT * FROM shopping_carts WHERE id = {cart_id}"
        result = connection.execute(sqlalchemy.text(sql))
        cart = result.first()
        if cart:
            if cart_item.quantity == 0: # if requesting 0 potions
                sql = f"DELETE FROM cart_contents WHERE cart_id = {cart_id} AND potion_sku = '{item_sku}'; "
                connection.execute(sqlalchemy.text(sql))
                return "OK"
            # check if SKU is an item that is offered in shop catalog
            sql = f"SELECT quantity FROM potions_inventory WHERE sku = '{item_sku}'; "
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
                return "OK"
            else:
                print(f"Requested item, with SKU: {item_sku} is not offered")
                return "No matching sku found in catalog or out of stock"
        else:
            print(f"Cart with id {cart_id} does not exist")
            return "Cart not found"


class CartCheckout(BaseModel):
    payment: str
    gold_paid: int

@router.post("/{cart_id}/checkout")
def checkout(cart_id: int, cart_checkout: CartCheckout):
    """ """
    with db.engine.begin() as connection:
        sql = f"SELECT * FROM shopping_carts WHERE id = {cart_id}; "
        result = connection.execute(sqlalchemy.text(sql))
        cart = result.first()
        print(f"Cart {cart_id}: {cart}")
        if cart: # if there exists a cart with the given id
            sql = f"SELECT * FROM cart_contents AS cnt "
            sql += f"JOIN potions_inventory AS pot ON cnt.potion_sku = pot.sku "
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
                        sql = f"DELETE FROM shopping_carts WHERE id = {cart_id}; " 
                        connection.execute(sqlalchemy.text(sql))
                        return "Insufficient Potion Stock"
                        # raise HTTPException(
                        #     status_code=status.HTTP_401_UNAUTHORIZED, detail="Forbidden: insufficient potion stock"
                        # )
                    selling += record.quantity_requested
                    total += record.price * record.quantity_requested
                # execute transaction if paid enough
                if cart_checkout.gold_paid >= total:
                    transaction = True
                    sql = f"UPDATE global_inventory SET gold = gold + {total}; "
                    for record in result:
                        sql += f"UPDATE potions_inventory "
                        sql += f"SET quantity = quantity - {record.quantity_requested} WHERE sku = '{record.sku}'; "
                else:
                    sql = ""
                    print(f"Cart with id {cart_id} did not pay enough for potions requested")
                    selling = 0
                    total = 0
            else:
                sql = ""
                print(f"Cart with id {cart_id} was empty")
            sql += f"DELETE FROM shopping_carts WHERE id = {cart_id}; " 
            connection.execute(sqlalchemy.text(sql))

            # Update total potions count in global inventory
            sql = f"SELECT * FROM potions_inventory; "
            result = connection.execute(sqlalchemy.text(sql))
            total = 0
            for record in result:
                total += record.quantity
            sql = f"UPDATE global_inventory SET num_potions = {total}; "
            connection.execute(sqlalchemy.text(sql))

            return {"success": transaction, "total_potions_bought": selling, "total_gold_paid": total}
        else:
            print(f"Cart with id {cart_id} does not exist")
            return {"success": False, "total_potions_bought": 0, "total_gold_paid": 0}
