from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db
from src.api.bottler import Color

MAX_PURCHASE_NUM = 2
NUM_COLORS = 4

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

def list_priority():
    """ Returns the order in which purchasing berrels should be prioritized 
    based on how much of each type of potion are in the inventory """
    with db.engine.begin() as connection:
        priority_list = []
        sql = "SELECT * FROM potions_inventory ORDER BY quantity"
        result = connection.execute(sqlalchemy.text(sql))
        for record in result:
            potion_type = [record.red, record.green, record.blue, record.dark]
            potion_color = potion_type.index(max(potion_type))
            if potion_color not in priority_list:
                priority_list.append(potion_color)
            if len(priority_list) == NUM_COLORS:
                break
        return priority_list
    # return [Color.RED, Color.GREEN, Color.BLUE, Color.DARK] # Default priority

def look_for(color: str, options: list[Barrel]):
    """ looks for and returns the barrel with the most ml with SKU containing
    the given string (color) or the lowercase counterpart """
    # Create a lowercase version of the color for case-insensitive matching
    color_lowercase = color.lower()

    # Filter the list of options to include only those with SKU containing the given color
    filtered_options = [barrel for barrel in options if color_lowercase in barrel.sku.lower()]

    # Find the barrel with the highest ml_per_barrel among the filtered options
    if filtered_options:
        biggest_barrel = max(filtered_options, key=lambda barrel: barrel.ml_per_barrel)
        print("found green!")
        return biggest_barrel
    else:
        # If no matching barrels were found
        return None

@router.post("/deliver")
def post_deliver_barrels(barrels_delivered: list[Barrel]):
    """ """
    print(barrels_delivered)
    if barrels_delivered:
        red_ml_received = 0
        green_ml_received = 0
        blue_ml_received = 0
        dark_ml_received = 0
        gold_spent = 0
        for barrel in barrels_delivered:
            potion_type = barrel.potion_type
            potion_color = potion_type.index(max(potion_type))
            match potion_color:
                case Color.RED:
                    red_ml_received += barrel.ml_per_barrel * barrel.quantity
                case Color.GREEN:
                    green_ml_received += barrel.ml_per_barrel * barrel.quantity
                case Color.BLUE:
                    blue_ml_received += barrel.ml_per_barrel * barrel.quantity
                case Color.DARK:
                    dark_ml_received += barrel.ml_per_barrel * barrel.quantity
            gold_spent += barrel.price * barrel.quantity
        with db.engine.begin() as connection:
            sql = f"UPDATE global_inventory SET gold = gold - {gold_spent},"
            sql += f" num_red_ml = num_red_ml + {red_ml_received},"
            sql += f" num_green_ml = num_green_ml + {green_ml_received},"
            sql += f" num_blue_ml = num_blue_ml + {blue_ml_received},"
            sql += f" num_dark_ml = num_dark_ml + {dark_ml_received};"
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
        sql = "SELECT * FROM global_inventory"
        result = connection.execute(sqlalchemy.text(sql))
        inv = result.first() # inventory is on a single row
        if inv.num_potions < 35:
            barrel_plan = []
            gold = inv.gold
            options = list_viable(gold, wholesale_catalog) # check afford and quantity in catalog
            if len(options) > 0:
                priority = list_priority()
                print(f"priority list: {priority}")
                print(f"Red = {Color.RED}, Green = {Color.GREEN}, Blue = {Color.BLUE}, Dark = {Color.DARK}")
                i = 0
                barrel = None
                while (len(options) > 0):
                    options = list_viable(gold, options) # check what options remain with current gold
                    print(f"Priority level {i}, value {priority[i]}")
                    match priority[i]:
                        case Color.RED:
                            barrel = look_for("RED", options)
                            print(f"Checked Red: {barrel}")
                        case Color.GREEN:
                            barrel = look_for("GREEN", options)
                            print(f"Checked Green: {barrel}")
                        case Color.BLUE:
                            barrel = look_for("BLUE", options)
                            print(f"Checked Blue: {barrel}")
                        case Color.DARK:
                            barrel = look_for("DARK", options)
                            print(f"Checked Dark: {barrel}")
                    i += 1 # Increment through priority list
                    if i == NUM_COLORS: # Check if need to cycle through again
                        i = 0
                        break # TODO: testing
                    if barrel is None: # if there are no options for that color
                        continue
                    gold -= barrel.price
                    # Check if there is a Barrel with the same SKU already in barrel_plan
                    index = next((index for index, item in enumerate(barrel_plan) if item.sku == barrel.sku), None)
                    if index:
                        barrel_plan[index].quantity += 1
                    else:
                        print(f"Barrel added to plan: {barrel.sku}")
                        barrel_plan.append({
                            "sku": barrel.sku,
                            "quantity": 1,
                        })
                return barrel_plan
            else:
                print("Could not afford any barrels or none available")
        else:
            print(f"Current inventory sufficient -> {inv.num_red_potions} red potions")
        return []


