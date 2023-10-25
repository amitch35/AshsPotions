from fastapi import APIRouter
import sqlalchemy
from src import database as db

router = APIRouter()

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
            catalog.append({
                        "sku": potion.sku,
                        "name": potion.name,
                        "quantity": potion.quantity,
                        "price": potion.price,
                        "potion_type": [potion.red, potion.green, potion.blue, potion.dark],
                    })
        print(catalog)
        return catalog
