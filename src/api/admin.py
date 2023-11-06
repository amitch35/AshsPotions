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
    print("----Reset----")
    with db.engine.begin() as connection:
            sql = f"TRUNCATE global_inventory; "
            sql += f"INSERT INTO global_inventory DEFAULT VALUES; "
            sql += f"TRUNCATE potion_quantities; "
            sql += f"TRUNCATE shopping_carts CASCADE; "
            sql += f"INSERT INTO shop_state DEFAULT VALUES; "
            connection.execute(sqlalchemy.text(sql))
    return "OK"


@router.get("/shop_info/")
def get_shop_info():
    """ """
    print("----Shop Info----")
    return {
        "shop_name": "Ash's Potions",
        "shop_owner": "Ash Mitchell",
    }

