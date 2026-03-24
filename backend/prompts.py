TEXT_PARSING_PROMPT = """Extract the food ingredients from this food description. Return a JSON object with:
- "confirmed": ingredients explicitly mentioned
- "likely": ingredients that are commonly part of the described dishes but not explicitly stated
- "source": "text"

Be specific about individual ingredients. For example, "stir fry with rice" should list rice, oil, and whatever protein/vegetables are mentioned or likely.

Return ONLY valid JSON, no other text.

Food description: {meal_text}"""

IMAGE_PARSING_PROMPT = """Look at this food photo and identify the food ingredients. Return a JSON object with:
- "confirmed": ingredients you can clearly identify
- "likely": ingredients that are probably present but not clearly visible
- "source": "image"

Return ONLY valid JSON, no other text."""

ANALYSIS_SUMMARY_PROMPT = """You are helping someone track eczema triggers by analysing correlations between food ingredients and flare-ups.

Here are the statistical results:

{stats_table}

Key metrics:
- lift: how much more frequently an ingredient appears before elevated skin states vs. normal meals (>1.0 = more common before flares)
- flare_appearances: number of distinct flare events this ingredient preceded
- confounded_flares: flare events where medication was also taken (±12h), which may mask the true trigger

{warnings}

Write a clear, cautious summary in plain English. Highlight the top suspects but emphasise:
1. Correlation does not prove causation
2. More data improves confidence
3. Consider elimination diets for top suspects, one at a time
4. Consult a dermatologist or allergist for proper testing

Keep it under 200 words."""
