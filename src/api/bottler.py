from fastapi import APIRouter, Depends
from enum import IntEnum
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db

class Color(IntEnum):
    RED = 0
    GREEN = 1
    BLUE = 2
    DARK = 3

BOTTLE_THRESHOLD = 20
MAX_BOTTLE_NUM = 99999

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
    print("----Bottler Deliver----")
    print(f"Potions Delivered: {potions_delivered}")
    if potions_delivered:
        with db.engine.begin() as connection:
            red_ml_mixed = 0
            green_ml_mixed = 0
            blue_ml_mixed = 0
            dark_ml_mixed = 0
            sql = ""
            for potion in potions_delivered:
                print(f"Handling potion type: [{potion.potion_type[Color.RED]}, {potion.potion_type[Color.GREEN]}, {potion.potion_type[Color.BLUE]}, {potion.potion_type[Color.DARK]}]")
                print(f"Quantity Recieved: {potion.quantity}")
                num_potions = potion.quantity
                red_ml_mixed += potion.potion_type[Color.RED] * num_potions
                green_ml_mixed += potion.potion_type[Color.GREEN] * num_potions
                blue_ml_mixed += potion.potion_type[Color.BLUE] * num_potions
                dark_ml_mixed += potion.potion_type[Color.DARK] * num_potions
                sql += "UPDATE potions "
                sql += f"SET quantity = quantity + {num_potions} "
                sql += f"WHERE red = {potion.potion_type[Color.RED]} AND green = {potion.potion_type[Color.GREEN]} AND "
                sql += f"blue = {potion.potion_type[Color.BLUE]} AND dark = {potion.potion_type[Color.DARK]}; "
            sql += "UPDATE global_inventory "
            sql += f"SET num_red_ml = num_red_ml - {red_ml_mixed}, num_green_ml = num_green_ml - {green_ml_mixed}, "
            sql += f"num_blue_ml = num_blue_ml - {blue_ml_mixed}, num_dark_ml = num_dark_ml - {dark_ml_mixed};"
            connection.execute(sqlalchemy.text(sql))
            # Update total potions count in global inventory
            sql = f"SELECT * FROM potions; "
            result = connection.execute(sqlalchemy.text(sql))
            total = 0
            for record in result:
                total += record.quantity
            sql = f"UPDATE global_inventory SET num_potions = {total}; "
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

    # Initial logic: bottle all barrels into potions.
    print("----Bottler Plan----")
    with db.engine.begin() as connection:
        sql = "SELECT * FROM global_inventory"
        result = connection.execute(sqlalchemy.text(sql))
        inv = result.first() # inventory is on a single row
        sql = "SELECT * FROM potions ORDER BY quantity"
        result = connection.execute(sqlalchemy.text(sql))
        bottle_plan = []
        red = inv.num_red_ml
        green = inv.num_green_ml
        blue = inv.num_blue_ml
        dark = inv.num_dark_ml
        for potion in result:
            if potion.quantity < BOTTLE_THRESHOLD:
                if potion.red > 0:
                    red_ok = (red // potion.red)
                else:
                    red_ok = MAX_BOTTLE_NUM
                if potion.green > 0:
                    green_ok = (green // potion.green)
                else:
                    green_ok = MAX_BOTTLE_NUM
                if potion.blue > 0:
                    blue_ok = (blue // potion.blue)
                else:
                    blue_ok = MAX_BOTTLE_NUM
                if potion.dark > 0:
                    dark_ok = (dark // potion.dark)
                else:
                    dark_ok = MAX_BOTTLE_NUM
                #if (red_ok > 0) and green_ok and blue_ok and dark_ok:
                num_potions = min(red_ok, green_ok, blue_ok, dark_ok)
                if num_potions > 0:
                    print(f"Plan to bottle {num_potions} {potion.name} potions")
                    red -= (potion.red * num_potions)
                    green -= (potion.green * num_potions)
                    blue -= (potion.blue * num_potions)
                    dark -= (potion.dark * num_potions)
                    bottle_plan.append({
                        "potion_type": [potion.red, potion.green, potion.blue, potion.dark],
                        "quantity": num_potions,
                    })
                else:
                    print(f"Not enough ml to bottle {potion.name}")
        return bottle_plan

        # if inv.num_red_ml >= 100:
        #     num_potions = (inv.num_red_ml // 100)
        #     print(f"Plan to bottle {num_potions} red potions")
        #     bottle_plan.append({
        #             "potion_type": [100, 0, 0, 0],
        #             "quantity": num_potions,
        #         })
        # else:
        #     print("Not enough red ml for bottling")
        # if inv.num_green_ml >= 100:
        #     num_potions = (inv.num_green_ml // 100)
        #     print(f"Plan to bottle {num_potions} green potions")
        #     bottle_plan.append({
        #             "potion_type": [0, 100, 0, 0],
        #             "quantity": num_potions,
        #         })
        # else:
        #     print("Not enough green ml for bottling")
        # if inv.num_blue_ml >= 100:
        #     num_potions = (inv.num_blue_ml // 100)
        #     print(f"Plan to bottle {num_potions} blue potions")
        #     bottle_plan.append({
        #             "potion_type": [0, 0, 100, 0],
        #             "quantity": num_potions,
        #         })
        # else:
        #     print("Not enough blue ml for bottling")
        # if inv.num_dark_ml >= 100:
        #     num_potions = (inv.num_dark_ml // 100)
        #     print(f"Plan to bottle {num_potions} dark potions")
        #     bottle_plan.append({
        #             "potion_type": [0, 0, 0, 100],
        #             "quantity": num_potions,
        #         })
        # else:
        #     print("Not enough dark ml for bottling")
        # return bottle_plan


