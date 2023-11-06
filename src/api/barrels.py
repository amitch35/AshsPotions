from fastapi import APIRouter, Depends
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from sqlalchemy.exc import DBAPIError
from src import database as db
from src.api.bottler import Color, MAX_BOTTLE_SLOTS
from src.api.catalog import SHOP_PHASE, PHASE_ONE, PHASE_TWO, PHASE_THREE, PHASE_FOUR
import copy

if SHOP_PHASE >= PHASE_FOUR:
    PURCHASE_THRESHOLD = 0
else:
    PURCHASE_THRESHOLD = MAX_BOTTLE_SLOTS
if SHOP_PHASE == PHASE_ONE or SHOP_PHASE == PHASE_TWO:
    PURCHASE_MAX = 10 # 4
    ML_THRESHOLD = 8000
elif SHOP_PHASE == PHASE_THREE: # Est. 33,000 ml mixed per day will check agin
    PURCHASE_MAX = 23
    ML_THRESHOLD = 30000
LARGE_NUM_ML = 10000
DARK_ML_THRESHOLD = 201000
DARK_ML_GOAL = 230000
DARK_PURCHASE_MAX = 24
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

def list_priority(potions):
    """ Returns the order in which purchasing berrels should be prioritized 
    based on how much of each type of potion are in the inventory """
    priority_list = []
    for name, red, green, blue, dark, quantity in potions:
        potion_type = [red, green, blue, dark]
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
        return biggest_barrel
    else:
        # If no matching barrels were found
        return None
    
def remove_all(color: str, options: list[Barrel]):
    """ removes all barrels of the given color from the given list """
    barrel = look_for(color, options)
    while barrel is not None:
        options = [bar for bar in options if bar.sku != barrel.sku] # Remove barrel from options
        barrel = look_for(color, options)
    return options

@router.post("/deliver")
def post_deliver_barrels(barrels_delivered: list[Barrel]):
    """ """
    print("----Barrels Deliver----")
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
            sql = ("INSERT INTO global_inventory "
                    "(gold, num_red_ml, num_green_ml, num_blue_ml, num_dark_ml)"
                    f" VALUES (- {gold_spent}, "
                    f"{red_ml_received}, {green_ml_received}, "
                    f"{blue_ml_received}, {dark_ml_received}); ")
            connection.execute(sqlalchemy.text(sql))
        return "OK"
    else:
        return "Nothing Delivered"
    
def make_barrel_plan(wholesale_catalog, inv, potions, num_potions):
    if num_potions < PURCHASE_THRESHOLD:
        barrel_plan = []
        gold = inv.gold
        print(f"Available Gold: {gold}")
        options = copy.deepcopy(wholesale_catalog)
        options = list_viable(gold, options) # check afford and quantity in catalog
        if SHOP_PHASE >= PHASE_THREE:
            options = remove_all("MINI", options)
            options = remove_all("SMALL", options)
            options = remove_all("MEDIUM", options)
        if len(options) > 0:
            priority = list_priority(potions)
            print(f"Priority list: {priority}")
            print(f"Red = {Color.RED}, Green = {Color.GREEN}, Blue = {Color.BLUE}, Dark = {Color.DARK}")
            if inv.num_red_ml > ML_THRESHOLD:
                priority = [color for color in priority if color != Color.RED]
                options = remove_all("RED", options)
                print(f"Alread have enough red ml: {inv.num_red_ml}")
            if inv.num_green_ml > ML_THRESHOLD:
                priority = [color for color in priority if color != Color.GREEN]
                options = remove_all("GREEN", options)
                print(f"Alread have enough green ml: {inv.num_green_ml}")
            if inv.num_blue_ml > ML_THRESHOLD:
                priority = [color for color in priority if color != Color.BLUE]
                options = remove_all("BLUE", options)
                print(f"Alread have enough blue ml: {inv.num_blue_ml}")
            if inv.num_dark_ml > DARK_ML_THRESHOLD:
                priority = [color for color in priority if color != Color.DARK]
                options = remove_all("DARK", options)
                print(f"Alread have enough dark ml: {inv.num_dark_ml}")
            if len(priority) > 0:
                #print(f"Updated Priority list: {priority}")
                i = 0
                barrel = None
                red_cnt = 0
                green_cnt = 0
                blue_cnt = 0
                dark_cnt = 0
                dark_needed = DARK_ML_GOAL - inv.num_dark_ml
                while (len(options) > 0):
                    #TEST:print(f"Remaining number of options: {len(options)}")
                    curr_color = priority[i]
                    #TEST:print(f"Priority {i}, value {Color(curr_color).name}")
                    match curr_color:
                        case Color.RED:
                            if red_cnt < PURCHASE_MAX:
                                barrel = look_for("RED", options)
                                #TEST:print(f"Checked options for Red: {barrel}")
                                red_cnt += 1
                            else:
                                barrel = None
                                options = remove_all("RED", options)
                                print(f"Getting Sufficient number of red barrels: {red_cnt}")
                        case Color.GREEN:
                            if green_cnt < PURCHASE_MAX:
                                barrel = look_for("GREEN", options)
                                #TEST:print(f"Checked options for Green: {barrel}")
                                green_cnt += 1
                            else:
                                barrel = None
                                options = remove_all("GREEN", options)
                                print(f"Getting Sufficient number of green barrels: {green_cnt}")
                        case Color.BLUE:
                            if blue_cnt < PURCHASE_MAX:
                                barrel = look_for("BLUE", options)
                                #TEST:print(f"Checked options for Blue: {barrel}")
                                blue_cnt += 1
                            else:
                                barrel = None
                                options = remove_all("BLUE", options)
                                print(f"Getting Sufficient number of blue barrels: {blue_cnt}")
                        case Color.DARK:
                            if dark_cnt < DARK_PURCHASE_MAX and (dark_cnt * LARGE_NUM_ML) < dark_needed:
                                barrel = look_for("DARK", options)
                                #TEST:print(f"Checked options for Dark: {barrel}")
                                dark_cnt += 1
                            else:
                                barrel = None
                                options = remove_all("DARK", options)
                                print(f"Getting Sufficient number of dark barrels: {dark_cnt}")
                        case Color.BLANK:
                            barrel = None
                    i += 1 # Increment through priority list
                    if i == len(priority): # Check if need to cycle through again
                        i = 0
                    if barrel is None: # if there are no options for that color
                        priority = [color for color in priority if color != curr_color] # remove from priority list
                        i = max(0, i - 1) # move i to accomodate removing from priority list
                        print(f"Removed {Color(curr_color).name} from priority, no options found")
                        continue
                    gold -= barrel.price
                    # Check if there is a Barrel with the same SKU already in barrel_plan
                    index = next((index for index, item in enumerate(barrel_plan) if item.sku == barrel.sku), None)
                    if index is not None:
                        #TEST:print("Barrel already in plan")
                        wholesale_barrel = next((bar for bar in wholesale_catalog if bar.sku == barrel.sku), None)
                        if wholesale_barrel.quantity == barrel_plan[index].quantity: # If already asking for max offered
                            print(f"Asking for all available {barrel.sku}, looking for other options")
                            options = [bar for bar in options if bar.sku != wholesale_barrel.sku] # Remove barrel from options
                        else: # If there is still stock available
                            #TEST:print(f"Adding another {barrel.sku} to plan")
                            barrel_plan[index].quantity += 1 # add another barrel to plan
                    else:
                        #TEST:print(f"Barrel added to plan: {barrel.sku}")
                        # Only choose to get 1 per iteration
                        plan_barrel = Barrel(sku=barrel.sku, ml_per_barrel=barrel.ml_per_barrel, potion_type=barrel.potion_type, price=barrel.price, quantity=1)
                        barrel_plan.append(plan_barrel)
                    #TEST:print(f"Remaining Gold: {gold}")
                    options = list_viable(gold, options) # check what options remain with current gold
            else:
                print(f"Current inventory sufficient, all ml types above {ML_THRESHOLD}")
            plan_list = [f"sku: {bar.sku}, quantity: {bar.quantity}" for bar in barrel_plan]
            for item in plan_list:
                print(item)
            return ({ "sku": bar.sku, "quantity": bar.quantity, } for bar in barrel_plan)
        else:
            if SHOP_PHASE >= PHASE_THREE:
                print("No Large barrels offered from wholesale")
            else:
                print("Could not afford any barrels or none available")
    else:
        print(f"Current inventory sufficient -> {num_potions} potions")
    return []

# Gets called once a day
@router.post("/plan")
def get_wholesale_purchase_plan(wholesale_catalog: list[Barrel]):
    """ """
    print("----Barrels Plan----")
    print("Wholesale Catalog: ")
    print(wholesale_catalog)

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
            inv = result.first() # inventory is summed to a single row
            # Order potions by quantity to prioritize ml for lower inventory
            sql = ("SELECT potions.name, "
                        "potions.red, potions.green, potions.blue, potions.dark, "
                        "COALESCE(SUM(potion_quantities.delta), 0) AS quantity "
                    "FROM potions "
                    "LEFT JOIN potion_quantities ON "
                        "potions.id = potion_quantities.potion_id "
                    "GROUP BY potions.id "
                    "ORDER BY quantity, potions.id; ")
            potions = connection.execute(sqlalchemy.text(sql))
            sql = ("SELECT COALESCE(SUM(delta),0) FROM potion_quantities")
            num_potions = connection.execute(sqlalchemy.text(sql)).scalar_one()
            return make_barrel_plan(wholesale_catalog, inv, potions, num_potions)
    except DBAPIError as error:
        print(f"Error returned: <<<{error}>>>")

