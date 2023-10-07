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

def update_potions_count():
    with db.engine.begin() as connection:
        sql = f"SELECT * FROM potions_inventory; "
        result = connection.execute(sqlalchemy.text(sql))
        total = 0
        for record in result:
            total += record.quantity
        sql = f"UPDATE global_inventory SET num_potions = {total}; "
        connection.execute(sqlalchemy.text(sql))
    return

@router.get("/inventory")
def get_inventory():
    """ """
    update_potions_count()
    with db.engine.begin() as connection:
        result = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory;"))
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
    print(audit_explanation)

    return "OK"
