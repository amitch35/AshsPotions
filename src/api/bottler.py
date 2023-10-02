from fastapi import APIRouter, Depends
from enum import Enum
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/bottler",
    tags=["bottler"],
    dependencies=[Depends(auth.get_api_key)],
)

class PotionInventory(BaseModel):
    potion_type: list[int]
    quantity: int

@router.post("/deliver")
def post_deliver_bottles(potions_delivered: list[PotionInventory]):
    """ """
    print(potions_delivered)
    if potions_delivered:
        red_potions_received = 0
        # green_potions_received = 0
        # blue_potions_received = 0
        # dark_potions_received = 0
        red_ml_mixed = 0
        for potion in potions_delivered:
            red_ml_mixed += potion.potion_type[0]
            red_potions_received += potion.quantity
        with db.engine.begin() as connection:
            sql = f"UPDATE global_inventory SET num_red_potions = num_red_potions + {red_potions_received}, num_red_ml = num_red_ml - {red_ml_mixed}"
            connection.execute(sqlalchemy.text(sql))
        return "OK"
    else:
        return "Nothing Delivered"

# Gets called 4 times a day
@router.post("/plan")
def get_bottle_plan():
    """
    Go from barrel to bottle.
    """

    # Each bottle has a quantity of what proportion of red, blue, and
    # green potion to add.
    # Expressed in integers from 1 to 100 that must sum up to 100.

    # Initial logic: bottle all barrels into red potions.
    with db.engine.begin() as connection:
        result = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory"))
        inv = result.first() # inventory is on a single row
        print(f"Current red ml: {inv.num_red_ml}")
        if inv.num_red_ml >= 100:
            num_potions = (inv.num_red_ml / 100) - (inv.num_red_ml % 100)
            print(f"Plan to bottle {num_potions} potions")
            return [
                {
                    "potion_type": [100, 0, 0, 0],
                    "quantity": num_potions,
                }
            ]
        else:
            print("Not enough ml for bottling")
        return []


