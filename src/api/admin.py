from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from src.api import auth
import sqlalchemy
from src import database as db

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(auth.get_api_key)],
)

@router.post("/reset")
def reset():
    """
    Reset the game state. Gold goes to 100, all potions are removed from
    inventory, and all barrels are removed from inventory. Carts are all reset.
    """
    with db.engine.begin() as connection:
            sql = f"UPDATE global_inventory SET gold = 100, num_potions = 0, num_red_ml = 0, "
            sql += f"num_green_ml = 0, num_blue_ml = 0, num_dark_ml = 0; "
            sql += f"UPDATE potions_inventory SET quantity = 0; "
            sql += f"DELETE FROM shopping_carts; "
            connection.execute(sqlalchemy.text(sql))
    return "OK"


@router.get("/shop_info/")
def get_shop_info():
    """ """
    return {
        "shop_name": "Ash's Potions",
        "shop_owner": "Ash Mitchell",
    }

