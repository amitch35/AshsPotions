from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel
from src.api import auth
from src.api.bottler import list_exclusions
from src.api.audit import get_shop_state
from enum import Enum
import sqlalchemy
from sqlalchemy import select, join
from sqlalchemy.exc import DBAPIError
from src import database as db

SEARCH_PAGE_SIZE = 5

REQUESTED_TOO_MANY_POTIONS = 2004

router = APIRouter(
    prefix="/carts",
    tags=["cart"],
    dependencies=[Depends(auth.get_api_key)],
)

class search_sort_options(str, Enum):
    customer_name = "customer_name"
    item_sku = "item_sku"
    line_item_total = "line_item_total"
    timestamp = "timestamp"

class search_sort_order(str, Enum):
    asc = "asc"
    desc = "desc"   

@router.get("/search/", tags=["search"])
def search_orders(
    customer_name: str = "",
    potion_sku: str = "",
    search_page: str = "",
    sort_col: search_sort_options = search_sort_options.timestamp,
    sort_order: search_sort_order = search_sort_order.desc,
):
    """
    Search for cart line items by customer name and/or potion sku.

    Customer name and potion sku filter to orders that contain the 
    string (case insensitive). If the filters aren't provided, no
    filtering occurs on the respective search term.

    Search page is a cursor for pagination. The response to this
    search endpoint will return previous or next if there is a
    previous or next page of results available. The token passed
    in that search response can be passed in the next search request
    as search page to get that page of results.

    Sort col is which column to sort by and sort order is the direction
    of the search. They default to searching by timestamp of the order
    in descending order.

    The response itself contains a previous and next page token (if
    such pages exist) and the results as an array of line items. Each
    line item contains the line item id (must be unique), item sku, 
    customer name, line item total (in gold), and timestamp of the order.
    Your results must be paginated, the max results you can return at any
    time is 5 total line items.
    """
    try:
        with db.engine.begin() as connection:
            line_item_id = search_page * SEARCH_PAGE_SIZE

            # Use reflection to derive table schema. You can also code this in manually.
            metadata_obj = sqlalchemy.MetaData()
            shopping_carts = sqlalchemy.Table("shopping_carts", metadata_obj, autoload_with=connection)
            cart_contents = sqlalchemy.Table("cart_contents", metadata_obj, autoload_with=connection)
            transactions = sqlalchemy.Table("transactions", metadata_obj, autoload_with=connection)
            potions = sqlalchemy.Table("potions", metadata_obj, autoload_with=connection)
            
            # determine sort column
            match sort_col:
                case search_sort_options.customer_name:
                    order_by = shopping_carts.c.customer
                case search_sort_options.item_sku:
                    order_by = potions.c.name
                case search_sort_options.line_item_total:
                    order_by = transactions.c.gold_paid
                case search_sort_options.timestamp:
                    order_by = transactions.c.created_at
                case _ :
                    assert False

            # determine order
            if sort_order is search_sort_order.desc:
                order_by = sqlalchemy.desc(order_by)

            # find limit and offset for page and page size
            limit = SEARCH_PAGE_SIZE + 1
            if search_page != "":
                page_num = int(search_page)
                offset = SEARCH_PAGE_SIZE * page_num
            else:
                page_num = 0
                offset = 0
            
            # build base select statement
            stmt = (
                select(
                    cart_contents.c.id,
                    cart_contents.c.quantity_requested,
                    shopping_carts.c.customer,
                    potions.c.name,
                    transactions.c.gold_paid,
                    transactions.c.created_at,
                )
                .select_from(
                    join(
                        cart_contents,
                        shopping_carts,
                        cart_contents.c.cart_id == shopping_carts.c.id,
                    )
                    .join(
                        potions,
                        cart_contents.c.potion_id == potions.c.id,
                    )
                    .join(
                        transactions,
                        cart_contents.c.cart_id == transactions.c.cart_id,
                    )
                )
                .limit(limit)
                .offset(offset)
                .order_by(order_by, sqlalchemy.desc(cart_contents.c.id))
            )
            
            # filter names only if customer name parameter is passed
            if customer_name != "":
                stmt = stmt.where(shopping_carts.c.customer.ilike(f"%{customer_name}%"))
            
            # filter potions only if potion sku parameter is passed
            if potion_sku != "":
                stmt = stmt.where(potions.c.name.ilike(f"%{potion_sku}%"))
            
            # execute search and build results
            i = 0
            result = connection.execute(stmt)
            results_json = []
            for row in result:
                if i < SEARCH_PAGE_SIZE:
                    item_string = make_look_nice(row.quantity_requested, row.name)
                    results_json.append(
                        {
                            "line_item_id": row.id,
                            "item_sku": item_string,
                            "customer_name": f"{row.customer}",
                            "line_item_total": row.gold_paid,
                            "timestamp": row.created_at.strftime('%Y-%m-%dT%H:%M:%SZ'),
                        }
                    )
                i += 1
            
            if offset > 0:
                # has previous page
                prev = f"{page_num - 1}"
            else:
                prev = ""

            if i > SEARCH_PAGE_SIZE:
                # has next page
                nxt = f"{page_num + 1}"
            else:
                nxt = ""

            return {
                "previous": prev,
                "next": nxt,
                "results": results_json
            }
    except DBAPIError as error:
        print(f"Error returned: <<<{error}>>>")

def make_look_nice(qty, name):
    item_details_string = f"{qty} {name} Potion"
    if qty > 1:
        item_details_string += "s"
    return item_details_string


class NewCart(BaseModel):
    customer: str

@router.post("/")
def create_cart(new_cart: NewCart):
    """ """
    try:
        with db.engine.begin() as connection:
            #print(f"Creating cart for: {new_cart.customer}")
            sql = f"INSERT INTO shopping_carts (customer) VALUES ('{new_cart.customer}') RETURNING shopping_carts.id;"
            new_id = connection.execute(sqlalchemy.text(sql)).scalar_one()
            print(f"----New Cart---- Creating cart {new_id} for: {new_cart.customer}")
        return {"cart_id": new_id}
    except DBAPIError as error:
        print(f"Error returned: <<<{error}>>>")


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
                        print(f"----Add to Cart---- {cart_item.quantity} new {item_sku} added to cart {cart_id}")
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
    print(f"----Cart {cart_id} Checkout----")
    try:
        with db.engine.begin() as connection:
            exclusions = list_exclusions(connection)
            #print(f"Cart {cart_id}: {cart}")
            sql = (f"SELECT *, "
                    "(SELECT sum(delta) FROM potion_quantities "
                    "WHERE potion_id = cnt.potion_id) AS quantity "
                    "FROM cart_contents AS cnt "
                    f"JOIN potions AS pot ON cnt.potion_id = pot.id "
                    f"WHERE cart_id = {cart_id}; ")
            result = connection.execute(sqlalchemy.text(sql))
            transaction = False
            total = 0
            selling = 0
            # check validity of cart and determine total price
            for record in result:
                if record.quantity < record.quantity_requested:
                    print(f"Cart with id {cart_id} requested too many potions (insufficient stock)")
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED, detail="Forbidden: requested too many potions"
                    )
                selling += record.quantity_requested
                if record.sku not in exclusions:
                    total += record.price * record.quantity_requested
                else:
                    total += get_shop_state(connection).sell_off_price * record.quantity_requested
            if selling == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail="Bad Request: Cart did not exist or was empty"
                )
            # execute transaction 
            #print(f"Cart {cart_id} Completing transaction for {cart.customer}")
            transaction = True
            sql = ("INSERT INTO global_inventory "
                "(gold, num_red_ml, num_green_ml, num_blue_ml, num_dark_ml)"
                f" VALUES ({total}, 0, 0, 0, 0); \n")
            sql += ("INSERT INTO potion_quantities (potion_id, delta) "
                "SELECT potion_id, - quantity_requested "
                "FROM cart_contents "
                f"WHERE cart_id = {cart_id}; ")
            sql += (f"INSERT INTO transactions (cart_id, success, payment, gold_paid) "
                f"VALUES ({cart_id}, {transaction}, '{cart_checkout.payment}', {total}); ")
            connection.execute(sqlalchemy.text(sql))

            return {"success": transaction, "total_potions_bought": selling, "total_gold_paid": total}
    except DBAPIError as error:
        print(f"Error returned: <<<{error}>>>")
