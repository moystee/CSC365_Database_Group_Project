Flow 1: The College Student with a Nut Allergy
Sarah, a college student on a budget, signs up for the application because she wants to know what recipes she can make given the ingredients already sitting in her pantry. She also has a severe nut allergy and needs to be certain her meals are safe.
First, Sarah creates a new account to get started. She calls POST /users/create passing in her "first_name": "Sarah" and "email": "sarah@example.com", and receives a response with "user_id": 101.
Next, she makes sure her allergy is documented. She calls POST /users/add_allergy using her "user_id": 101 and the "ingredient_id" for peanuts (e.g., 42).
Sarah then logs the groceries she currently has in her kitchen—chicken, rice, and broccoli. She calls POST /ingredients/save three separate times, passing her user_id and the respective ingredient_id for each item.
Finally, Sarah wants to find dinner options. She calls GET /recipes/get_compatible passing in the IDs of the chicken, rice, and broccoli. The app returns safe, peanut-free recipes like "Chicken and Broccoli Stir-Fry" that she can make without spending extra money.






Flow 2: Roommates Minimizing Food Waste
Mark and Leo are roommates who hate wasting food. They want to combine their digital pantries to find recipes that use up ingredients before they expire.
Mark already has an account (user_id: 201). He decides to create a shared space for their apartment by calling POST /households/create with his user_id and "household_name": "The Bachelor Pad". The system returns "household_id": 12.
Leo downloads the app and signs up by calling POST /users/create, receiving "user_id": 202.
Leo then links up with Mark's pantry by calling POST /households/join, passing in "household_id": 12 and his "user_id": 202. The API returns "Success": true.
Mark wants to see what they can make together. He calls GET /pantry/get_ingredients using his user_id. Because Mark and Leo are now in the same household, the backend automatically groups their individual pantries and returns a combined list containing both Mark's eggs and Leo's spinach.
Mark selects the eggs and spinach and calls GET /recipes/get_compatible. The API returns a list of recipes, including a "Spinach Frittata," helping them use their expiring food and minimizing waste.

Flow 3: The Aspiring Chef Updating Inventory
Chef David is an aspiring cook who just finished making a beautiful, Umami-rich mushroom risotto. He needs to update his app to reflect the ingredients he used up, as well as add some new groceries he just bought.
David starts by checking his current digital inventory to see what needs to be removed. He calls GET /pantry/get_ingredients passing his "user_id": 305.
Seeing that Arborio rice and chicken broth are still listed, he removes them to maintain accurate data. He calls POST /ingredients/delete twice—once with his user_id and the ingredient_id for Arborio rice, and once for the chicken broth.
David just returned from the farmer's market with fresh basil and tomatoes. To log his new ingredients, he calls POST /ingredients/save twice, passing the respective ingredient_ids for the basil and tomatoes.
David's pantry is now perfectly up to date, ensuring that his next call to GET /recipes/get_compatible will yield accurate, culturally diverse recipe suggestions based on his fresh produce.


