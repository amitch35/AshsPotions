from fastapi import APIRouter
import sqlalchemy
from src import database as db

router = APIRouter()


@router.get("/catalog/", tags=["catalog"])
def get_catalog():
    """
    Each unique item combination must have only a single price.
    """

    # Can return a max of 20 items.
    print("----Catalog----")
    with db.engine.begin() as connection:
        sql = "SELECT * FROM potions WHERE quantity > 0 ORDER BY quantity desc; "
        result = connection.execute(sqlalchemy.text(sql))
        catalog = []
        for potion in result:
            # TODO: max of 20 items for catalog
            catalog.append({
                        "sku": potion.sku,
                        "name": potion.name,
                        "quantity": potion.quantity,
                        "price": potion.price,
                        "potion_type": [potion.red, potion.green, potion.blue, potion.dark],
                    })
            print(catalog)
        return catalog
