from fastapi import APIRouter, Depends
from enum import IntEnum
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from sqlalchemy.exc import DBAPIError
from src import database as db

class Color(IntEnum):
    RED = 0
    GREEN = 1
    BLUE = 2
    DARK = 3
    BLANK = 4

BOTTLE_THRESHOLD = 30
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
    print(f"Potions Mixes Delivered: {len(potions_delivered)}")
    if potions_delivered:
        with db.engine.begin() as connection:
            red_ml_mixed = 0
            green_ml_mixed = 0
            blue_ml_mixed = 0
            dark_ml_mixed = 0
            sql = ("INSERT INTO potion_quantities (potion_id, delta) "
                        "VALUES ")
            i = 0
            for potion in potions_delivered:
                i += 1
                print(f"Handling potion type: [{potion.potion_type[Color.RED]}, {potion.potion_type[Color.GREEN]}, {potion.potion_type[Color.BLUE]}, {potion.potion_type[Color.DARK]}]")
                print(f"Quantity Recieved: {potion.quantity}")
                num_potions = potion.quantity
                red_ml_mixed += potion.potion_type[Color.RED] * num_potions
                green_ml_mixed += potion.potion_type[Color.GREEN] * num_potions
                blue_ml_mixed += potion.potion_type[Color.BLUE] * num_potions
                dark_ml_mixed += potion.potion_type[Color.DARK] * num_potions
                sql += ("(( "
                                "SELECT id FROM potions WHERE "
                                f"red = {potion.potion_type[Color.RED]} AND "
                                f"green = {potion.potion_type[Color.GREEN]} AND "
                                f"blue = {potion.potion_type[Color.BLUE]} AND "
                                f"dark = {potion.potion_type[Color.DARK]}"
                            "), "
                            f"{num_potions}")
                if i != len(potions_delivered):
                    sql +=  "), "
                else: 
                    sql += "); "
            sql += ("INSERT INTO global_inventory "
                    "(gold, num_red_ml, num_green_ml, num_blue_ml, num_dark_ml)"
                    f" VALUES (0, - {red_ml_mixed}, - {green_ml_mixed}, "
                    f"- {blue_ml_mixed}, - {dark_ml_mixed}); ")
            connection.execute(sqlalchemy.text(sql))
            return "OK"
    else:
        return "Nothing Delivered"
    
def make_bottle_plan(inv, potions):
    bottle_plan = []
    inv_red = inv.num_red_ml
    inv_green = inv.num_green_ml
    inv_blue = inv.num_blue_ml
    inv_dark = inv.num_dark_ml
    # TODO: make it so never goes above 300 using inv.num_potions
    for name, red, green, blue, dark, quantity in potions:
        if quantity < BOTTLE_THRESHOLD:
            if red > 0:
                red_ok = (inv_red // red)
            else:
                red_ok = MAX_BOTTLE_NUM
            if green > 0:
                green_ok = (inv_green // green)
            else:
                green_ok = MAX_BOTTLE_NUM
            if blue > 0:
                blue_ok = (inv_blue // blue)
            else:
                blue_ok = MAX_BOTTLE_NUM
            if dark > 0:
                dark_ok = (inv_dark // dark)
            else:
                dark_ok = MAX_BOTTLE_NUM
            # How many potions can be mixed
            num_potions = min(red_ok, green_ok, blue_ok, dark_ok)
            if num_potions > 0:
                # bottle as much as possible up to threshold
                num_potions = min(num_potions, max(0, BOTTLE_THRESHOLD - quantity))
                if num_potions > 0:
                    print(f"Plan to bottle {num_potions} {name} potions")
                    inv_red -= (red * num_potions)
                    inv_green -= (green * num_potions)
                    inv_blue -= (blue * num_potions)
                    inv_dark -= (dark * num_potions)
                    bottle_plan.append({
                        "potion_type": [red, green, blue, dark],
                        "quantity": num_potions,
                    })
                else: # If inventory alread has more than threshold
                    print(f"No need to bottle {name} with {quantity} in stock")
            else:
                print(f"Not enough ml to bottle {name}")
        else:
                print(f"Already have {quantity} of {name}")
    return bottle_plan

# Gets called 4 times a day
@router.post("/plan")
def get_bottle_plan():
    """
    Go from barrel to bottle.
    """

    # Each bottle has a quantity of what proportion of red, blue, and
    # green potion to add.
    # Expressed in integers from 1 to 100 that must sum up to 100.
    # Maximum Total Potion Inventory is 300

    # Initial logic: bottle all barrels into potions.
    print("----Bottler Plan----")
    try:
        with db.engine.begin() as connection:
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
                    "SUM(delta) AS num_potions "
                "FROM potion_quantities) as potion_sum;")
            result = connection.execute(sqlalchemy.text(sql))
            inv = result.first() # inventory is on a single row
            # Order potions by quantity (include name, quantity and ml mix info)
            sql = ("SELECT potions.name, "
                        "potions.red, potions.green, potions.blue, potions.dark, "
                        "COALESCE(SUM(potion_quantities.delta), 0) AS quantity "
                    "FROM potions "
                    "LEFT JOIN potion_quantities ON "
                        "potions.id = potion_quantities.potion_id "
                    "GROUP BY potions.id "
                    "ORDER BY quantity, potions.id; ")
            potions = connection.execute(sqlalchemy.text(sql))
            return make_bottle_plan(inv, potions)
    except DBAPIError as error:
        print(f"Error returned: <<<{error}>>>")


