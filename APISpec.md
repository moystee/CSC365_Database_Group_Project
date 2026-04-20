API Speculation

User sign up

New User - /users/create (POST)

Creates a new user

Request:

{
  "first_name": "string",
  "email": "string"
}
Response:
[
    {
         "user_id": "int",
    }
]

User saving ingredients to their pantry
Save Ingredient - /ingredients/save (POST)
Saves ingredient(s) to pantry
Request:
{
  "user_id": "int",
  "ingredient_id": "int",
  “Is_shared_with_household”: “bool”
}
Response:
[
    {
         "Success”: “boolean”,
    }
]

User deleting ingredient from their pantry
Delete Ingredient - /ingredients/delete (POST)
Deletes ingredient(s) to pantry
Request:
{
  "user_id": "int",
  "ingredient_id": "int"
}
Response:
[
    {
         "Success”: “boolean”,
    }
]

User saving allergies to their profile
Add allergy - /users/add_allergy (POST)
Request:
{
  "user_id": "int",
  "ingredient_id": "int"
}
Response:
[
    {
         "Success”: “boolean”,
    }
]

User creating a household
Create Household - /households/create (POST)
Creates household
Request:
[
    {
         "user_id": "int",
         “household_name”: “string”
    }
]
Response:
[
    {
         "household_id": "int",
    }
]

User joining a household
Join Household - /households/join (POST)
Adds User to household
Request:
[
    {
          "household_id": "int",
          "user_id": "int"
     }
Response:
[
    {
        "Success”: “boolean”
    }
]


Read:
Get list of compatible recipes
Get Compatible Recipes - /recipes/get_compatible (GET)
Retrieves the list of recipes compatible with the selected ingredients
Request:
[
    {
        "ingredient_id": "int"
    }
]
Response:
[
    {
        "recipe_id": "int",
        "recipe_name": "string",
        "recipe_steps": "string"
    }
]

Get Ingredients from user’s pantry
Get Ingredients from pantry - /pantry/get_ingredients (GET)
Retrieves the list of ingredients from the user’s pantry
Request:
[
    {
        "user_id": "int"
    }
]
Response:
[
    {
        "ingredient_id": "int",
        "name": "string",
        "steps": "string"
    }
]


Get user allergies
Get allergies from user - /users/get_allergies (POST)
Get user’s allergies
Request:
[
    {
        "user_id": "int"
    }
]
Response:
[
    {
        “ingredient_name": "string"
    }
]
