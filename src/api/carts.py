from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from sqlalchemy.exc import DBAPIError
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
        sql = f"INSERT INTO shopping_carts (customer) VALUES ('{new_cart.customer}') RETURNING shopping_carts.id;"
        new_id = connection.execute(sqlalchemy.text(sql)).scalar_one()
        print(f"{new_cart.customer} got cart id: {new_id}")
    return {"cart_id": new_id}


@router.get("/{cart_id}")
def get_cart(cart_id: int):
    """ """
    print("----Get Cart----")
    try:
        with db.engine.begin() as connection:
            sql = f"SELECT * FROM shopping_carts WHERE id = {cart_id}"
            result = connection.execute(sqlalchemy.text(sql))
            record = result.first()
            if record:
                print(f"Cart with id: {record.id} is for customer: {record.customer}")
                return { f"Cart with id: {record.id} is for customer: {record.customer}"}
            else:
                print(f"Cart with id {cart_id} does not exist")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Cart Not Found: Cart with given id does not exist"
            )
    except DBAPIError as error:
        print(f"Error returned: <<<{error}>>>")


class CartItem(BaseModel):
    quantity: int


@router.post("/{cart_id}/items/{item_sku}")
def set_item_quantity(cart_id: int, item_sku: str, cart_item: CartItem):
    """ """
    print("----Add to Cart----")
    try:
        with db.engine.begin() as connection:
            sql = f"SELECT * FROM shopping_carts WHERE id = {cart_id}"
            result = connection.execute(sqlalchemy.text(sql))
            cart = result.first()
            if cart:
                # check if SKU is an item that is offered in shop catalog
                sql = ("SELECT sum(potion_quantities.delta) "
                        "FROM potion_quantities "
                        "JOIN potions ON potion_quantities.potion_id = potions.id "
                        f"WHERE potions.sku = '{item_sku}'")
                stock = connection.execute(sqlalchemy.text(sql)).scalar_one()
                if stock:
                    # Check if already in cart
                    sql = (f"SELECT * FROM cart_contents WHERE "
                            f"cart_id = {cart_id} "
                            "AND potion_id = ( "
                                "SELECT id FROM potions "
                                f"WHERE sku = '{item_sku}' "
                            "); ")
                    result = connection.execute(sqlalchemy.text(sql))
                    record = result.first()
                    if record is not None: # if updating the quantity asked for
                        print(f"{item_sku} already in cart {cart_id}, updating to {cart_item.quantity} ...")
                        sql = (f"UPDATE cart_contents SET quantity_requested = {cart_item.quantity} "
                                f"WHERE id = {record.id}; ")
                    else: # adding new item to cart
                        print(f"{cart_item.quantity} new {item_sku} added to cart {cart_id}")
                        sql = (f"INSERT INTO cart_contents "
                                    "(cart_id, quantity_requested, potion_id) "
                                "VALUES ( "
                                    f"{cart_id}, "
                                    f"{cart_item.quantity}, "
                                    f"(SELECT id FROM potions WHERE sku = '{item_sku}')"
                                "); ")
                    connection.execute(sqlalchemy.text(sql))
                    return {"success": True}
                else:
                    print(f"Requested item, with SKU: {item_sku} is not offered")
                    return {"success": False}
            else:
                print(f"Cart with id {cart_id} does not exist")
                return {"success": False}
    except DBAPIError as error:
        print(f"Error returned: <<<{error}>>>")


class CartCheckout(BaseModel):
    payment: str

@router.post("/{cart_id}/checkout")
def checkout(cart_id: int, cart_checkout: CartCheckout):
    """ """
    print("----Cart Checkout----")
    try:
        with db.engine.begin() as connection:
            sql = f"SELECT * FROM transactions WHERE cart_id = {cart_id} ORDER BY success desc; "
            result = connection.execute(sqlalchemy.text(sql))
            prev_transaction = result.first()
            if (prev_transaction is None) or (prev_transaction.success == False):
                sql = f"SELECT * FROM shopping_carts WHERE id = {cart_id}; "
                result = connection.execute(sqlalchemy.text(sql))
                cart = result.first()
                print(f"Cart {cart_id}: {cart}")
                if cart: # if there exists a cart with the given id
                    sql = (f"SELECT * FROM cart_contents AS cnt "
                            f"JOIN potions AS pot ON cnt.potion_id = pot.id "
                            f"WHERE cart_id = {cart_id}; ")
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
                                raise HTTPException(
                                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Forbidden: requested too many potions"
                                )
                            selling += record.quantity_requested
                            total += record.price * record.quantity_requested
                        # execute transaction 
                        print(f"Cart {cart_id} Completing transaction for {cart.customer}")
                        sql = ("INSERT INTO potion_quantities (potion_id, delta) "
                            "SELECT potion_id, - potions_requested "
                            "FROM cart_contents "
                            f"WHERE cart_id = {cart_id}; ")
                        connection.execute(sqlalchemy.text(sql))
                        transaction = True
                    else:
                        print(f"Cart with id {cart_id} was empty")
                    sql = (f"INSERT INTO transactions (cart_id, success, payment, gold_paid) "
                        f"VALUES ({cart_id}, {transaction}, '{cart_checkout.payment}', {total}); ")
                    connection.execute(sqlalchemy.text(sql))

                    return {"success": transaction, "total_potions_bought": selling, "total_gold_paid": total}
                else:
                    print(f"Cart with id {cart_id} does not exist")
                    return {"success": False, "total_potions_bought": 0, "total_gold_paid": 0}
            else:
                print(f"Cart with id {cart_id} already completed transaction")
                sql = f"SELECT SUM(potions_requested) FROM cart_contents WHERE cart_id = {cart_id}"
                potions_bought = connection.execute(sqlalchemy.text(sql)).scalar_one()
                return {"success": prev_transaction.success, "total_potions_bought": potions_bought, "total_gold_paid": prev_transaction.gold_paid}
    except DBAPIError as error:
        print(f"Error returned: <<<{error}>>>")
