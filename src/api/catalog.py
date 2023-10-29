from fastapi import APIRouter
from enum import IntEnum
from pydantic import BaseModel
import sqlalchemy
from sqlalchemy import *
from sqlalchemy.exc import DBAPIError
from src import database as db
from src.api.bottler import BOTTLE_THRESHOLD

router = APIRouter()

PHASE_ONE = 1 # Getting started, growth and aquiring customers
PHASE_TWO = 2 # Optimizing Purchases and offerings
SHOP_PHASE = PHASE_TWO

BEST_SELLERS = ["red_potion", "green_potion"]

CATALOG_MAX = 6

# Use reflection to derive table schema. You can also code this in manually.
metadata_obj = sqlalchemy.MetaData()
potions = sqlalchemy.Table("potions", metadata_obj, autoload_with=db.engine)
potion_quantities = sqlalchemy.Table("potion_quantities", metadata_obj, autoload_with=db.engine)

class DayOfWeek(IntEnum):
    SUNDAY = 0
    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 3
    THURSDAY = 4
    FRIDAY = 5
    SATURDAY = 6

class Potion(BaseModel):
    sku: str
    price: int
    name: str
    red: int
    green: int
    blue: int
    dark: int
    quantity: int

def add_best_sellers(catalog: list[Potion], potions):
    num_added = 0
    for potion in potions:
        if potion.sku in BEST_SELLERS and potion.sku not in [potion.sku for potion in catalog]:
            catalog.append(potion)
            num_added += 1
    return num_added

def list_exclusions(day_of_week):
    # Some potions don't sell well on certain days of the week
    match day_of_week:
        case DayOfWeek.SUNDAY:
            print("Today is Sunday.")
            exclude = []
        case DayOfWeek.MONDAY:
            print("Today is Monday.")
            exclude = ["blue_potion"]
        case DayOfWeek.TUESDAY:
            print("Today is Tuesday.")
            exclude = []
        case DayOfWeek.WEDNESDAY:
            print("Today is Wednesday.")
            exclude = []
        case DayOfWeek.THURSDAY:
            print("Today is Thursday.")
            exclude = []
        case DayOfWeek.FRIDAY:
            print("Today is Friday.")
            exclude = ["purple_potion"]
        case DayOfWeek.SATURDAY:
            print("Today is Saturday.")
            exclude = ["purple_potion"]
    return exclude

@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    """
    Each unique item combination must have only a single price.
    """

    # Can return a max of 6 items.
    print("----Catalog----")
    try:
        with db.engine.begin() as conn:
            # Implements best sellers and time based offerings before randomly offering others
            catalog = []
            catalog_size = 0
            #sql = ("SELECT EXTRACT(DOW FROM CURRENT_TIMESTAMP) AS day_of_week FROM CURRENT_TIMESTAMP;")
            day_of_week = int(conn.execute(select(extract("DOW", func.current_timestamp()))))
            stmt = (
                select(
                    [potions, func.coalesce(func.sum(potion_quantities.c.delta), 0).label("quantity")]
                )
                .select_from(
                    potions.join(potion_quantities, potions.c.id == potion_quantities.c.potion_id)
                )
                .group_by(
                    potions.c.id
                )
                .having(
                    func.coalesce(func.sum(potion_quantities.c.delta), 0) > 0
                )
            )
            # exclude some potions on certain days
            exclusions = list_exclusions(day_of_week)
            if len(exclusions) > 0:
                stmt = (
                    stmt.where(
                        and_(
                            not_(potions.c.sku.in_(exclusions))
                        )
                    )
                )
            all_available_potions = conn.execute(sqlalchemy.text(stmt))
            catalog_size += add_best_sellers(catalog, all_available_potions)
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
                    catalog.append(potion)
            
            catalog_json = []
            for potion in catalog:
                print(f"{potion.name}: {potion.quantity}")
                if SHOP_PHASE == PHASE_ONE:
                    qty = potion.quantity
                elif SHOP_PHASE == PHASE_TWO:
                    qty = BOTTLE_THRESHOLD
                catalog_json.append({
                            "sku": potion.sku,
                            "name": potion.name,
                            "quantity": qty,
                            "price": potion.price,
                            "potion_type": [potion.red, potion.green, potion.blue, potion.dark],
                        })
            return catalog_json
    except DBAPIError as error:
        print(f"Error returned: <<<{error}>>>")
