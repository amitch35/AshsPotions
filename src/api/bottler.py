from fastapi import APIRouter, Depends
from enum import IntEnum
from pydantic import BaseModel
from src.api import auth
from src.api.audit import get_global_inventory
import sqlalchemy
from sqlalchemy.exc import DBAPIError
from src import database as db

class Color(IntEnum):
    RED = 0
    GREEN = 1
    BLUE = 2
    DARK = 3
    BLANK = 4

NUM_POTION_MIXES = 6
MAX_BOTTLE_SLOTS = 300
BOTTLE_THRESHOLD = MAX_BOTTLE_SLOTS // NUM_POTION_MIXES
MAX_BOTTLE_NUM = 99999

router = APIRouter(
    prefix="/bottler",
    tags=["bottler"],
    dependencies=[Depends(auth.get_api_key)],
)

def list_exclusions(conn):
    # Some potions don't sell well on certain days of the week
    sql = """
        SELECT sku 
        FROM exclusions
        WHERE day = extract(DOW from CURRENT_TIMESTAMP) 
    """
    exclusions = []
    result = conn.execute(sqlalchemy.text(sql))
    for row in result:
        exclusions.append(row.sku)
    return exclusions

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
    
class Potion(BaseModel):
    sku: str
    price: int
    name: str
    red: int
    green: int
    blue: int
    dark: int
    quantity: int
    
def make_bottle_plan(inv, potions, exclusions):
    bottle_plan = []
    inv_red = inv.num_red_ml
    inv_green = inv.num_green_ml
    inv_blue = inv.num_blue_ml
    inv_dark = inv.num_dark_ml
    # make it so never goes above max of 300 
    slots_available = MAX_BOTTLE_SLOTS - inv.num_potions
    for potion in potions:
        if potion.quantity < BOTTLE_THRESHOLD and potion.sku not in exclusions:
            if potion.red > 0:
                red_ok = (inv_red // potion.red)
            else:
                red_ok = MAX_BOTTLE_NUM
            if potion.green > 0:
                green_ok = (inv_green // potion.green)
            else:
                green_ok = MAX_BOTTLE_NUM
            if potion.blue > 0:
                blue_ok = (inv_blue // potion.blue)
            else:
                blue_ok = MAX_BOTTLE_NUM
            if potion.dark > 0:
                dark_ok = (inv_dark // potion.dark)
            else:
                dark_ok = MAX_BOTTLE_NUM
            # How many potions can be mixed
            num_potions = min(red_ok, green_ok, blue_ok, dark_ok)
            if num_potions > 0:
                # bottle as much as possible up to threshold
                num_potions = min(num_potions, max(0, BOTTLE_THRESHOLD - potion.quantity))
                # but not more than can fit in available slots
                num_potions = min(slots_available, num_potions)
                if num_potions > 0:
                    print(f"Plan to bottle {num_potions} {potion.name} potions")
                    inv_red -= (potion.red * num_potions)
                    inv_green -= (potion.green * num_potions)
                    inv_blue -= (potion.blue * num_potions)
                    inv_dark -= (potion.dark * num_potions)
                    bottle_plan.append(Potion(
                        sku="", 
                        price=0,
                        name=potion.name,
                        red=potion.red,
                        green=potion.green,
                        blue=potion.blue,
                        dark=potion.dark,
                        quantity=num_potions
                    ))
                    # update available slots
                    slots_available -= num_potions
                else: # If inventory alread has more than threshold
                    if slots_available == 0:
                        print(f"Did not bottle {potion.name} to avoid exceeding {MAX_BOTTLE_SLOTS} potions")
                    else:
                        print(f"No need to bottle {potion.name} with {potion.quantity} in stock")
            else:
                print(f"Not enough ml to bottle {potion.name}")
        else:
            if potion.quantity < BOTTLE_THRESHOLD:
                print(f"Already have {potion.quantity} of {potion.name}")
            else:
                print(f"{potion.name} excluded today")
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
            inv = get_global_inventory(connection)
            # Order potions by quantity (include name, quantity and ml mix info)
            sql = ("SELECT potions.sku, potions.name, "
                        "potions.red, potions.green, potions.blue, potions.dark, "
                        "COALESCE(SUM(potion_quantities.delta), 0) AS quantity "
                    "FROM potions "
                    "LEFT JOIN potion_quantities ON "
                        "potions.id = potion_quantities.potion_id "
                    "GROUP BY potions.id "
                    "ORDER BY quantity, potions.id; ")
            potions = connection.execute(sqlalchemy.text(sql))
            exclusions = list_exclusions(connection)
            bottle_plan = make_bottle_plan(inv, potions, exclusions)
            bottle_plan_json = []
            for potion in bottle_plan:
                bottle_plan_json.append({
                        "potion_type": [potion.red, potion.green, potion.blue, potion.dark],
                        "quantity": potion.quantity,
                    })
            return bottle_plan_json
    except DBAPIError as error:
        print(f"Error returned: <<<{error}>>>")


