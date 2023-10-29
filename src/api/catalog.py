from fastapi import APIRouter
import sqlalchemy
from src import database as db
from src.api.bottler import MAX_BOTTLE_NUM

router = APIRouter()

PHASE_ONE = 1 # Getting started, growth and aquiring customers
PHASE_TWO = 2 # Optimizing Purchases and offerings
SHOP_PHASE = PHASE_ONE

CATALOG_MAX = 6

@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    """
    Each unique item combination must have only a single price.
    """

    # Can return a max of 6 items.
    print("----Catalog----")
    with db.engine.begin() as connection:
        # TODO: Implement best sellers/constants and time based offerings 
        sql = ("SELECT potions.*, "
                        "COALESCE(SUM(potion_quantities.delta), 0) AS quantity "
                    "FROM potions "
                    "JOIN potion_quantities ON "
                        "potions.id = potion_quantities.potion_id "
                    "GROUP BY potions.id "
                    "HAVING coalesce(sum(potion_quantities.delta), 0) > 0 "
                    "ORDER BY RANDOM() "
                    f"LIMIT {CATALOG_MAX}")
        result = connection.execute(sqlalchemy.text(sql))
        catalog = []
        for potion in result:
            print(f"{potion.name}: {potion.quantity}")
            catalog.append({
                        "sku": potion.sku,
                        "name": potion.name,
                        "quantity": MAX_BOTTLE_NUM,
                        "price": potion.price,
                        "potion_type": [potion.red, potion.green, potion.blue, potion.dark],
                    })
        return catalog
