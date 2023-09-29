from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/barrels",
    tags=["barrels"],
    dependencies=[Depends(auth.get_api_key)],
)

class Barrel(BaseModel):
    sku: str

    ml_per_barrel: int
    potion_type: list[int]
    price: int

    quantity: int

def list_viable(gold: int, catalog: list[Barrel]):
    """ Returns a new list of only options from the catalog that you can both
    afford and are available (ie. quantity greater than 0)"""
    viable_options = []
    for barrel in catalog:
         if barrel.price <= gold and barrel.quantity > 0:
              viable_options.append(barrel)
    return viable_options

@router.post("/deliver")
def post_deliver_barrels(barrels_delivered: list[Barrel]):
    """ """
    print(barrels_delivered)
    if barrels_delivered:
        red_ml_received = 0
        # green_ml_received = 0
        # blue_ml_received = 0
        # dark_ml_received = 0
        gold_spent = 0
        for type in barrels_delivered:
            red_ml_received = type.ml_per_barrel * type.quantity
            gold_spent += type.price * type.quantity
        with db.engine.begin() as connection:
            sql = f"UPDATE global_inventory SET gold = gold - {gold_spent}, num_red_ml = num_red_ml + {red_ml_received}"
            connection.execute(sqlalchemy.text(sql))
        return "OK"
    else:
        return "Nothing Delivered"

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ """
    print(wholesale_catalog)

    with db.engine.begin() as connection:
        result = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory"))
        inv = result.first() # inventory is on a single row
        print(inv)
        if inv.num_red_potions < 10:
            options = list_viable(inv.gold, wholesale_catalog) # check afford and quantity in catalog
            if len(options) > 0:
                    return [
                        {
                            "sku": "SMALL_RED_BARREL",
                            "quantity": 1,
                        }
                    ]
        return


