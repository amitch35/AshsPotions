from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db

PHASE_ONE = 1   # Getting started, growth and aquiring customers
PHASE_TWO = 2   # Optimizing potion offerings
PHASE_THREE = 3 # Optimizing Barrel Purchases
PHASE_FOUR = 4  # Stop buying barrels

router = APIRouter(
    prefix="/audit",
    tags=["audit"],
    dependencies=[Depends(auth.get_api_key)],
)

class ShopState(BaseModel):
    phase: int
    recents_threshold: int
    recents_interval: int
    sell_off_price: int
    bottle_max: int

def get_shop_state(connection):
    sql = """SELECT phase, recents_threshold, recents_interval, sell_off_price, bottle_max FROM shop_state """
    result = connection.execute(sqlalchemy.text(sql))
    state =  result.first() # Shop state is on a single row
    return ShopState(phase=state.phase, 
                    recents_threshold=state.recents_threshold,
                    recents_interval=state.recents_interval,
                    sell_off_price=state.sell_off_price,
                    bottle_max=state.bottle_max)

def get_global_inventory(connection):
    sql = ("SELECT gold, potion_sum.num_potions, "
               "num_red_ml, num_green_ml, num_blue_ml, num_dark_ml "
               "FROM "
               "(SELECT "
                    "SUM(gold) AS gold, "
                    "SUM(num_red_ml) AS num_red_ml, "
                    "SUM(num_green_ml) AS num_green_ml, "
                    "SUM(num_blue_ml) AS num_blue_ml, "
                    "SUM(num_dark_ml) AS num_dark_ml "
                "FROM global_inventory) as inv, "
                "(SELECT "
                    "COALESCE(SUM(delta),0) AS num_potions "
                "FROM potion_quantities) as potion_sum;")
    result = connection.execute(sqlalchemy.text(sql))
    return result.first() # inventory is on a single row

@router.get("/inventory")
def get_inventory():
    """ """
    print("----Get Inventory----")
    with db.engine.begin() as connection:
        inv = get_global_inventory(connection)
        total_ml = inv.num_red_ml + inv.num_green_ml + inv.num_blue_ml + inv.num_dark_ml
        print(f"number_of_potions: {inv.num_potions}, ml_in_barrels: {total_ml}, gold: {inv.gold}")
        return {"number_of_potions": inv.num_potions, "ml_in_barrels": total_ml, "gold": inv.gold}

class Result(BaseModel):
    gold_match: bool
    barrels_match: bool
    potions_match: bool

# Gets called once a day
@router.post("/results")
def post_audit_results(audit_explanation: Result):
    """ """
    print("----Audit Results----")
    print(f"Gold match: {audit_explanation.gold_match}\nBarrels Match: {audit_explanation.barrels_match}\nPotions Match: {audit_explanation.potions_match}")
    print(audit_explanation)

    return "OK"
