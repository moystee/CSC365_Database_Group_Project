User Stories:

As a college student, I want to cook meals at home, so that I can save money.
As a person with food allergies, I want to easily find ingredient substitutions, so that I can still make fun recipes that won’t kill me.
As a person who tries not to waste food, I want access to recipes that use ingredients I already have, so I can minimize food waste by using what might expire soon
As an aspiring chef, I want to learn how to cook recipes from different cultures, so that I can be more versatile in cooking different cuisines.
As a food influencer, I want to discover new recipes to trendy meals given the ingredients I have in my kitchen.
As an athlete, I want to know how to make the best macro dense meals given a tight budget.
As a person who is always traveling, but wants to cook instead of eating out, I want to know the best on-the-go meals. 
As a parent of a child with a peanut allergy, I want to flag "Peanuts" as an allergen so that every recipe containing them is automatically filtered out or highlighted with a warning.
As a curious cook, I want to search for "Umami-rich" recipes so that I can find savory dishes regardless of whether they are Italian, Japanese, or American.
As someone who ran out of buttermilk, I want the app to suggest a "Smart Swap" (like milk + lemon juice) so I can finish my recipe without stopping.
As a cook using an international recipe, I want to toggle between Metric and Imperial units so I don't have to manually calculate grams to ounces.
As a person who can’t decide what to cook for dinner, I want to search recipes by the ingredients in my fridge and pantry so that I can cook with what I have and be happy.

Exceptions:

Exception: If a certain ingredient or food item is not listed in the database, the app will display an option to add an entry to the system. 
Exception: If the user submits a search with no ingredients, prompt a message back to them to enter at least one ingredient.
Exception: If a user tries to delete an ingredient node that is currently linked to several recipes, the system will prevent the deletion and ask the user to reassign or remove the ingredient from those recipes first to maintain data integrity.
Exception: If a flavor search (e.g., "Zesty") returns a recipe with potentially clashing flavor profiles, the app will display a note warning the user about the experimental nature of the combination.
Exception: If the user requests a budget, but there are no recipes that fall under that category. Return a message requesting the user increases their budget or cut out certain recipes. 
Exception: If an athlete’s macro-dense meal requirements cannot be met with their current budget, the app will prioritize the most expensive macro (typically protein) and suggest the cheapest possible sources, such as lentils or canned tuna.
Exception: If a user with severe allergies selects a "Smart Swap," the app will display a high-visibility disclaimer confirming whether the substitute is processed in a facility free of their specific allergen.
Exception: If a recipe requires scaling between units and the database lacks a specific density conversion for an ingredient, the app will prompt the user to enter a manual estimate or use a standard average weight.
Exception: If a user requests a recipe from a specific culture that requires a specialized tool the user hasn't listed in their kitchen profile, the app will suggest an "Improvised Equipment" workaround.
Exception: If the "Pantry-First" search finds ingredients that are past their typical shelf life based on the user's purchase date, the app will trigger a freshness warning and suggest a "safety check" before cooking.
Exception: If the user wants recipes that are portable or wants to serve multiple people, implement a volume or serving size measurement. 
Exception: If the user is unsure of what they’d like to cook. The system will not know what they like either. Implement a favorite foods or browse the database for past recipes made to formulate the best recipes to make given ingredients in the fridge/ pantry. 
