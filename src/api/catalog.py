from fastapi import APIRouter
from enum import IntEnum
from pydantic import BaseModel
import sqlalchemy
from sqlalchemy import *
from sqlalchemy.exc import DBAPIError
from src import database as db
from src.api.bottler import make_bottle_plan, list_exclusions, Potion
from src.api.audit import get_global_inventory

router = APIRouter()

PHASE_ONE = 1   # Getting started, growth and aquiring customers
PHASE_TWO = 2   # Optimizing potion offerings
PHASE_THREE = 3 # Optimizing Barrel Purchases
PHASE_FOUR = 4  # Stop buying barrels

RECENTS_THRESHOLD = 9 # If more than 9 potions sold last tick sell again

CATALOG_MAX = 6

class ShopState(BaseModel):
    phase: int
    recents_threshold: int
    recents_interval: int

def get_shop_state(connection):
    sql = """SELECT phase, recents_threshold, recents_interval FROM shop_state """
    result = connection.execute(sqlalchemy.text(sql))
    state =  result.first() # Shop state is on a single row
    return ShopState(phase=state.phase, 
                    recents_threshold=state.recents_threshold,
                    recents_interval=state.recents_interval)

# Use reflection to derive table schema. You can also code this in manually.
metadata_obj = sqlalchemy.MetaData()
potions = sqlalchemy.Table("potions", metadata_obj, autoload_with=db.engine)
potion_quantities = sqlalchemy.Table("potion_quantities", metadata_obj, autoload_with=db.engine)

class RecentPotion(BaseModel):
    name: str
    potion_id: int 
    num_requested: int

def add_recent_sellers(catalog: list[Potion], potions, shop_state, conn):
    sql = f"""
        SELECT potions.name as name, potion_id, sum(quantity_requested) as num_requested
        FROM cart_contents
        JOIN potions ON cart_contents.potion_id = potions.id
        WHERE cart_contents.created_at >= now() - interval '{shop_state.recents_interval} hours'
        GROUP BY potions.name, cart_contents.potion_id
        ORDER BY num_requested desc
    """
    recents = []
    result = conn.execute(sqlalchemy.text(sql))
    for item in result:
        recents.append(RecentPotion(
                name=item.name,
                potion_id=item.potion_id,
                num_requested=item.num_requested
            ))
    num_added = 0
    for item in recents:
        if num_added != CATALOG_MAX:
            for potion in potions:
                if potion.name == item.name and item.num_requested > shop_state.recents_threshold:
                    catalog.append(potion)
                    num_added += 1
                    break  # Break out of the inner loop after finding a match
        else:
            break
    return num_added

@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    """
    Each unique item combination must have only a single price.
    Implements best sellers and time based offerings before randomly offering others
    """

    # Can return a max of 6 items.
    print("----Catalog----")
    try:
        with db.engine.begin() as conn:
            # Define how to describe potions from all queries below
            stmt = (
                select(
                    potions.c.sku,
                    potions.c.price,
                    potions.c.name,
                    potions.c.red,
                    potions.c.green,
                    potions.c.blue,
                    potions.c.dark,
                    func.coalesce(func.sum(potion_quantities.c.delta), 0).label("quantity")
                )
            )
            # Get all potions un-ordered using left join with potion_quantities for qty
            all_potions = []
            all_stmt = (stmt
                .select_from(
                    join(potions, potion_quantities, potions.c.id == potion_quantities.c.potion_id, isouter=True)
                )
                .group_by(
                    potions.c.id
                )
                .order_by("quantity", potions.c.id)
            )
            result = conn.execute(all_stmt)
            for potion in result:
                all_potions.append(Potion(
                        sku=potion.sku, 
                        price=potion.price,
                        name=potion.name,
                        red=potion.red,
                        green=potion.green,
                        blue=potion.blue,
                        dark=potion.dark,
                        quantity=potion.quantity
                    ))
            
            # Normal join on potion quantities --> going forward only get potions that are in stock
            stmt = (stmt
                .select_from(
                    join(potions, potion_quantities, potions.c.id == potion_quantities.c.potion_id)
                )
                .group_by(
                    potions.c.id
                )
                .having(
                    func.coalesce(func.sum(potion_quantities.c.delta), 0) > 0
                )
            )

            # Figure out what is expected to be bottled
            inv = get_global_inventory(conn)
            exclusions = list_exclusions(conn)
            bottle_plan = make_bottle_plan(inv, all_potions, exclusions)
            shop_state = get_shop_state(conn)
            # in Phase two or above
            if shop_state.phase >= PHASE_TWO:
                # Exclude certain potions based on the day
                if len(exclusions) > 0:
                    stmt = (
                        stmt.where(
                            and_(
                                not_(potions.c.sku.in_(exclusions))
                            )
                        )
                    )
            # Get all potions in stock
            all_available_potions = []
            result = conn.execute(stmt.order_by("quantity", potions.c.id))
            for potion in result:
                all_available_potions.append(Potion(
                        sku=potion.sku, 
                        price=potion.price,
                        name=potion.name,
                        red=potion.red,
                        green=potion.green,
                        blue=potion.blue,
                        dark=potion.dark,
                        quantity=potion.quantity
                    ))
            # Start forming the Catalog
            catalog = []
            catalog_size = 0
            # Start by adding the best sellers (if they are available)
            catalog_size += add_recent_sellers(catalog, all_available_potions, shop_state, conn)
            # make sure that no duplicates can be returned by susequent queries
            stmt = (
                stmt.where(
                    and_(
                        not_(potions.c.sku.in_([potion.sku for potion in catalog]))
                    )
                )
            )
            # remaining catalog is generated randomly
            num_needed = CATALOG_MAX - catalog_size
            if num_needed > 0:
                stmt = (
                    stmt.order_by(
                        text("RANDOM()")
                    )
                    .limit(num_needed)
                )
                result = conn.execute(stmt)
                for potion in result:
                    catalog.append(Potion(
                        sku=potion.sku, 
                        price=potion.price,
                        name=potion.name,
                        red=potion.red,
                        green=potion.green,
                        blue=potion.blue,
                        dark=potion.dark,
                        quantity=potion.quantity
                    ))
            # Increase quantity in catalog if expected to bottle more
            for potion in bottle_plan:
                for item in catalog:
                    if potion.name == item.name:
                        item.quantity += (potion.quantity - 1)
                        break  # Break out of the inner loop after finding a match

            print("Ash's Catalog:")
            catalog_json = []
            for potion in catalog:
                print(f"{potion.name}: {potion.quantity} at {potion.price}")
                catalog_json.append({
                            "sku": potion.sku,
                            "name": potion.name,
                            "quantity": potion.quantity,
                            "price": potion.price,
                            "potion_type": [potion.red, potion.green, potion.blue, potion.dark],
                        })
            return catalog_json
    except DBAPIError as error:
        print(f"Error returned: <<<{error}>>>")