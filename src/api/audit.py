from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import math
import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/audit",
    tags=["audit"],
    dependencies=[Depends(auth.get_api_key)],
)

@router.get("/inventory")
def get_inventory():
    """ """
    print("----Get Inventory----")
    with db.engine.begin() as connection:
        sql = ("SELECT SUM(gold) AS gold, SUM(pot_qty.delta) AS num_potions, "
            "SUM(num_red_ml) AS num_red_ml, SUM(num_green_ml) AS num_green_ml, "
            "SUM(num_blue_ml) AS num_blue_ml, SUM(num_dark_ml) AS num_dark_ml "
            "FROM global_inventory, potion_quantities AS pot_qty")
        result = connection.execute(sqlalchemy.text(sql))
        inv = result.first() # inventory is on a single row
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
