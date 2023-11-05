from fastapi import APIRouter
import sqlalchemy
from sqlalchemy import *
from sqlalchemy.exc import DBAPIError
from src import database as db
from src.api.bottler import make_bottle_plan, Potion
from src.api.audit import get_global_inventory

router = APIRouter()

PHASE_ONE = 1   # Getting started, growth and aquiring customers
PHASE_TWO = 2   # Optimizing potion offerings
PHASE_THREE = 3 # Optimizing Barrel Purchases
PHASE_FOUR = 4  # Stop buying barrels
SHOP_PHASE = PHASE_THREE

BEST_SELLERS = ["red_potion", "green_potion"] 

CATALOG_MAX = 6

# Use reflection to derive table schema. You can also code this in manually.
metadata_obj = sqlalchemy.MetaData()
potions = sqlalchemy.Table("potions", metadata_obj, autoload_with=db.engine)
potion_quantities = sqlalchemy.Table("potion_quantities", metadata_obj, autoload_with=db.engine)


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
            # Define how to describe potions
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

            # Build a list of all potions
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
            
            # Figure out what is expected to be bottled
            inv = get_global_inventory(conn)
            bottle_plan = make_bottle_plan(inv, all_potions)
        
            # Catalog is generated selling potions with highest quantity
            catalog = []
            # Increase quantity in available potions if expected to bottle more
            for potion in bottle_plan:
                for item in all_potions:
                    if potion.name == item.name:
                        item.quantity += (potion.quantity - 1)
                        break  # Break out of the inner loop after finding a match
            # sort available potions by quantity (highest first)
            all_potions.sort(key=lambda potion: potion.quantity, reverse=True)
            # add highest quantity potions to catalog
            for potion in all_potions:
                catalog.append(potion)
                if len(catalog) == CATALOG_MAX:
                    break

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
