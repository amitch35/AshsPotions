from fastapi import APIRouter, Depends
from enum import IntEnum
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db
from src.api import audit

class Color(IntEnum):
    RED = 0
    GREEN = 1
    BLUE = 2
    DARK = 3

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
        with db.engine.begin() as connection:
            red_ml_mixed = 0
            green_ml_mixed = 0
            blue_ml_mixed = 0
            dark_ml_mixed = 0
            sql = ""
            for potion in potions_delivered:
                red_ml_mixed += potion.potion_type[Color.RED]
                green_ml_mixed += potion.potion_type[Color.GREEN]
                blue_ml_mixed += potion.potion_type[Color.BLUE]
                dark_ml_mixed += potion.potion_type[Color.DARK]
                sql += "UPDATE potions_inventory "
                sql += f"WHERE red = {potion.potion_type[Color.RED]}, green = {potion.potion_type[Color.GREEN]}, "
                sql += f"blue = {potion.potion_type[Color.BLUE]}, dark = {potion.potion_type[Color.RED]} "
                sql += f"SET quantity = quantity + {potion.quantity}; "
            sql += "UPDATE global_inventory "
            sql += f"SET num_red_ml = num_red_ml - {red_ml_mixed}, num_green_ml = num_green_ml - {green_ml_mixed}, "
            sql += f"num_blue_ml = num_blue_ml - {blue_ml_mixed}, num_dark_ml = num_dark_ml - {dark_ml_mixed};"
            connection.execute(sqlalchemy.text(sql))
            audit.update_potions_count()
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

    # Initial logic: bottle all barrels into potions.
    with db.engine.begin() as connection:
        result = connection.execute(sqlalchemy.text("SELECT * FROM global_inventory"))
        inv = result.first() # inventory is on a single row
        bottle_plan = []
        if inv.num_red_ml >= 100:
            num_potions = (inv.num_red_ml // 100)
            print(f"Plan to bottle {num_potions} red potions")
            bottle_plan.append({
                    "potion_type": [100, 0, 0, 0],
                    "quantity": num_potions,
                })
        else:
            print("Not enough red ml for bottling")
        if inv.num_green_ml >= 100:
            num_potions = (inv.num_green_ml // 100)
            print(f"Plan to bottle {num_potions} green potions")
            bottle_plan.append({
                    "potion_type": [0, 100, 0, 0],
                    "quantity": num_potions,
                })
        else:
            print("Not enough green ml for bottling")
        if inv.num_blue_ml >= 100:
            num_potions = (inv.num_blue_ml // 100)
            print(f"Plan to bottle {num_potions} blue potions")
            bottle_plan.append({
                    "potion_type": [0, 0, 100, 0],
                    "quantity": num_potions,
                })
        else:
            print("Not enough blue ml for bottling")
        if inv.num_dark_ml >= 100:
            num_potions = (inv.num_dark_ml // 100)
            print(f"Plan to bottle {num_potions} dark potions")
            bottle_plan.append({
                    "potion_type": [0, 0, 0, 100],
                    "quantity": num_potions,
                })
        else:
            print("Not enough dark ml for bottling")
        return bottle_plan


