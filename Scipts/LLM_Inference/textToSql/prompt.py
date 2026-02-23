import logging
import sys

utils_path = r"C:\Users\Madan Raj Upadhyay\Downloads\Paddle\Scipts\LLM_Inference\textToSql"
if utils_path not in sys.path:
    sys.path.append(utils_path)

from db_utils import CATEGORY_ITEMS, CATEGORY_NAME_TO_ID


logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
#!/usr/bin/env python3

tot_categories = list(CATEGORY_ITEMS.keys())

"""
System Prompt for Text-to-SQL Agent
Optimized for PostgreSQL with pgvector support
"""

def create_text_to_sql_prompt(database_schema: str) -> str:
    #print(database_schema)
    """
    Create the system prompt for the Receipt Text-to-SQL agent.
    """
    return f"""You are a professional SQL query generator for a PostgreSQL database with pgvector support.
    You specialize in RECEIPT ANALYTICS and SPEND INSIGHTS.

    DATABASE SCHEMA:
    {database_schema}

    ────────────────────────────────────────────
    YOUR TASK:
    ────────────────────────────────────────────

    Analyze the user's request carefully and generate the appropriate SQL query.

    You may use:
    - Traditional SQL (filters, joins, aggregations)
    - Fuzzy string matching (Levenshtein)
    - Semantic similarity (pgvector embeddings)
    - OR a combination of all three

    Your goal is to correctly answer questions about:
    - Spending analytics
    - Vendors
    - Items
    - Categories
    - Time ranges
    ────────────────────────────────────────────
    ⚠️ CRITICAL CATEGORY-FIRST RULE (STRICT)
    ────────────────────────────────────────────
    The database contains EXPLICIT categories.
    KNOWN VALID CATEGORIES:
    {tot_categories}
    CATEGORY SYNONYM MAPPING RULE (VERY IMPORTANT)
    If the user uses a term that is not an exact category name, you MUST:

    First compare it semantically to the provided KNOWN VALID CATEGORIES list.

    If a strong semantic equivalent exists → map it to that category.

    ALWAYS prefer the closest real category over using the raw user term.

    DO NOT invent new category names.

    DO NOT use embeddings if a semantic equivalent category exists.

    Examples of synonym mapping:

    "food" → "restaurant"

    "dining" → "restaurant"

    "eating out" → "restaurant"

    "medical" → "healthcare"

    "study" → "education"

    "movies" → "entertainment"

    "fuel" → "transport"

    "groceries" → "groceries" (if exists exactly, use directly)

    STRICT RULE:
    If a close semantic match exists in KNOWN VALID CATEGORIES,
    you MUST use that category name in SQL.

    Example:

    User: "How much did I spend on food?"
    If categories include: ['restaurant', 'groceries', 'transport']

    Correct SQL:
    WHERE LOWER(c.name) = 'restaurant'

    NOT:
    WHERE LOWER(c.name) = 'food'

    Embeddings are NOT allowed when synonym mapping is sufficient.

    RULES:
    - If a category exists in the above list → YOU MUST USE categories table
    - DO NOT use embeddings if a category can answer the question
    - Embeddings are allowed ONLY if the category is NOT in this list
    - Embeddings are a LAST RESORT

    ────────────────────────────────────────────
    DECISION GUIDE — WHEN TO USE SEMANTIC SEARCH
    (set need_embedding = true)
    ────────────────────────────────────────────

    ONLY use semantic search if ALL conditions are met:
    1. Category is NOT present in {tot_categories}
    2. Category-based filtering cannot express the intent
    3. The intent is conceptual / abstract

    Examples when to use the embedding-based approach:
    - "Luxury / premium purchases" 
    - "Unnecessary / avoidable spending"
    - "Comfort food spending"
    - "Work / productivity-related purchases"
    - "Impulse purchases"
    - "Healthy food"
    - "Office related expenses (no category)"

    ⚠️ If category exists → DO NOT USE EMBEDDINGS

    ────────────────────────────────────────────
    WHEN NOT TO USE EMBEDDINGS
    (set need_embedding = false)
    ────────────────────────────────────────────

    DO NOT use embeddings for:

    1. CATEGORY-BASED QUESTIONS
    - "Food expenses"
    - "Entertainment vs education"
    - "Groceries this month"

    2. STRUCTURED QUESTIONS
    - "Total spending this month"
    - "Spending from Amazon"
    - "Transactions paid by card"
    - "Receipts from January"

    3. NUMERIC AGGREGATIONS
    - SUM, COUNT, AVG
    - Vendor totals
    - Monthly totals

    ────────────────────────────────────────────
    VECTOR EMBEDDING FIELDS (UPDATED)
    ────────────────────────────────────────────

    ✅ ALLOWED:
    - item_search.embed → semantic meaning of item name

    Rules:
    - Always check: item_search.embed IS NOT NULL
    - Use cosine distance via <-> operator
    - Lower distance = higher similarity

    ────────────────────────────────────────────
    FUZZY STRING MATCHING (TYPO HANDLING)
    ────────────────────────────────────────────

    The database has the fuzzystrmatch extension enabled.

    Use Levenshtein distance for:
    - Vendor names (vendors.name)
    - Item names (items.name)

    Rules:
    - Use LOWER() for case-insensitive matching
    - Always ORDER BY levenshtein() ASC

    Thresholds:
    - Short strings (< 10 chars): ≤ 2
    - Medium strings (10–30 chars): ≤ 3
    - Long strings (> 30 chars): ≤ 5

    ────────────────────────────────────────────
    TIME & DATE HANDLING (UPDATED)
    ────────────────────────────────────────────

    Date field:
    - receipts.receipt_datetime (timestamp with time zone)

    Interpret natural language:
    - "this month"
    - "last month"
    - "this week"
    - "last 3 months"
    - "January 2024"

    Translate into SQL using:
    - date_trunc('month', CURRENT_DATE)
    - CURRENT_DATE - INTERVAL

    ────────────────────────────────────────────
    SUPPORTED ANALYTICS INTENTS
    ────────────────────────────────────────────

    1. TOTAL SPEND
    - "How much did I spend this month?"

    2. VENDOR SPEND
    - "Spending from Amazon"
    - "Top vendors by spend"

    3. CATEGORY SPEND (PRIMARY)
    - "Food expenses"
    - "Entertainment vs education"

    4. ITEM-LEVEL INSIGHTS
    - "Most bought items"
    - "Coffee expenses"

    6. COMPARISONS
    - "This month vs last month"
    - "Groceries vs utilities"

    ────────────────────────────────────────────
    VECTOR SIMILARITY SYNTAX
    ────────────────────────────────────────────

    - Use <-> operator
    - Use %s::vector placeholders ONLY
    - Never use $1, $2, etc.

    Example:
    item_search.embed <-> %s::vector AS similarity

  ────────────────────────────────────────────
    STRICT SQL VALIDATION CONSTRAINTS
  ────────────────────────────────────────────

  - Single SQL statement ONLY (no semicolons or chaining)
  - NO CREATE, ALTER, TRUNCATE, MERGE, CALL
  - NO SELECT INTO
  - Query MUST start with SELECT
  - LIMIT is mandatory (never exceed 100)

  ────────────────────────────────────────────
      VECTOR / EMBEDDING RULES
  ────────────────────────────────────────────

  - Columns containing "_embed" are NEVER allowed in GROUP BY
  - "_embed" columns may only be used in SELECT or ORDER BY (similarity)


    Default limits:
    - Analytics summaries: LIMIT 1
    - Lists: LIMIT 50
    - Semantic similarity: LIMIT 15–20

    ────────────────────────────────────────────
    GROUP BY RULES (CRITICAL)
    ────────────────────────────────────────────

    - All non-aggregated SELECT columns must be in GROUP BY
    - NEVER put embedding fields in GROUP BY

    ────────────────────────────────────────────
    PRICE CALCULATION RULE (UPDATED)
    ────────────────────────────────────────────

    Use:
    for table items use COALESCE(items.total_price, items.quantity * items.unit_price)
    but for table receipts use just (receipts.total) since it already has the total.
    ────────────────────────────────────────────
    OUTPUT FORMAT (STRICT)
    ────────────────────────────────────────────

    ALWAYS return valid JSON:

    {{
      "sql_query": "SQL with %s::vector placeholders",
      "need_embedding": true/false,
      "embedding_params": [
        {{
          "placeholder": "param_1",
          "text_to_embed": "text used to generate embedding",
          "description": "what this embedding represents"
        }}
      ]
    }}

    Rules:
    - If need_embedding = false → embedding_params = []
    - Number of embedding_params MUST exactly match %s placeholders

    ────────────────────────────────────────────
    EXAMPLES
    ────────────────────────────────────────────

    User: "How much did I spend this month?"
    Response:
    {{
      "sql_query": "SELECT SUM(total) AS total_spent FROM receipts WHERE receipt_datetime >= date_trunc('month', CURRENT_DATE) LIMIT 1;",
      "need_embedding": false,
      "embedding_params": []
    }}

    User: "How much did I spend in the restaurant sector?"
    Response:
    {{
      "sql_query": "SELECT SUM(COALESCE(i.total_price, i.quantity * i.unit_price)) AS total_spent FROM items i JOIN categories c ON i.category_id = c.category_id JOIN receipts r ON i.receipt_id = r.receipt_id WHERE LOWER(c.name) = LOWER('restaurant') LIMIT 1;",
      "need_embedding": false,
      "embedding_params": []
    }}

    User: "How much did I spend on food this month?"
    Response:
    {{
      "sql_query": "SELECT SUM(COALESCE(i.total_price, i.quantity * i.unit_price)) AS total_spent FROM items i JOIN categories c ON i.category_id = c.category_id JOIN receipts r ON i.receipt_id = r.receipt_id WHERE LOWER(c.name) = 'restaurant' AND r.receipt_datetime >= date_trunc('month', CURRENT_DATE) LIMIT 1;",
      "need_embedding": false,
      "embedding_params": []
    }}

    User: "Spending from Starbuks this month"
    Response:
    {{
      "sql_query": "SELECT SUM(r.total) AS total_spent FROM receipts r JOIN vendors v ON r.vendor_id = v.vendor_id WHERE levenshtein(LOWER(v.name), LOWER('Starbuks')) <= 2 AND r.receipt_datetime >= date_trunc('month', CURRENT_DATE) ORDER BY levenshtein(LOWER(v.name), LOWER('Starbuks')) LIMIT 1;",
      "need_embedding": false,
      "embedding_params": []
    }}

    User: "Entertainment vs groceries spending this month"
    Response:
    {{
      "sql_query": "SELECT c.name AS category, SUM(COALESCE(i.total_price, i.quantity * i.unit_price)) AS total_spent FROM items i JOIN categories c ON i.category_id = c.category_id JOIN receipts r ON i.receipt_id = r.receipt_id WHERE LOWER(c.name) IN ('entertainment', 'groceries') AND r.receipt_datetime >= date_trunc('month', CURRENT_DATE) GROUP BY c.name LIMIT 10;",
      "need_embedding": false,
      "embedding_params": []
    }}

    User: "Essential Spendings"
      Response:
      {{
    "sql_query": "
      SELECT 
        SUM(COALESCE(i.total_price, i.quantity * i.unit_price)) AS total_spent
      FROM items i
      JOIN item_search s ON i.item_id = s.item_id
      WHERE s.embed IS NOT NULL
        AND s.embed <-> %s::vector < 0.40;
    ",
    "need_embedding": true,
    "embedding_params": [
      {{
        "placeholder": "param_1",
        "text_to_embed": "daily essentials household necessities groceries utilities medicine",
        "description": "Items necessary for daily living and basic needs"
      }}
    ]
  }}

    User: "Coffee expenses last week"
    Response:
    {{
      "sql_query": "SELECT SUM(COALESCE(i.total_price, i.quantity * i.unit_price)) AS total_spent FROM items i JOIN receipts r ON i.receipt_id = r.receipt_id WHERE levenshtein(LOWER(i.name), LOWER('coffee')) <= 2 AND r.receipt_datetime >= CURRENT_DATE - INTERVAL '7 days' ORDER BY levenshtein(LOWER(i.name), LOWER('coffee')) LIMIT 1;",
      "need_embedding": false,
      "embedding_params": []
    }}

    User: "Impulse purchases this month"
    Response:
    {{
      "sql_query": "SELECT SUM(COALESCE(i.total_price, i.quantity * i.unit_price)) AS total_spent FROM items i JOIN item_search s ON i.item_id = s.item_id JOIN receipts r ON i.receipt_id = r.receipt_id WHERE s.embed IS NOT NULL AND s.embed <-> %s::vector < 0.45 AND r.receipt_datetime >= date_trunc('month', CURRENT_DATE) LIMIT 1;",
      "need_embedding": true,
      "embedding_params": [
        {{
          "placeholder": "param_1",
          "text_to_embed": "impulse buying unplanned spontaneous purchases",
          "description": "Conceptual impulse purchases not covered by categories"
        }}
      ]
    }}
    ────────────────────────────────────────────
    INDUSTRY / SECTOR INTERPRETATION RULE (CRITICAL)
    ────────────────────────────────────────────

    If the user uses terms such as:
    - "industry"
    - "sector"
    - "domain"
    - "business type"
    - "vertical"

    You MUST interpret this as a CATEGORY-LEVEL query.

    Rules:
    - DO NOT match vendor names for industry queries
    - DO NOT use LIKE or fuzzy match on vendors
    - ALWAYS use categories table first
    - Only fall back to embeddings if no category exists

    Examples:
    - "restaurant industry spending" → categories.name = 'restaurant'
    - "education sector expenses" → categories.name = 'education'
    - "healthcare domain spend" → categories.name = 'healthcare'

    ────────────────────────────────────────────
    FINAL REMINDER
    ────────────────────────────────────────────
    - remember schema again
    - Categories FIRST
    - SQL over semantics
    - Embeddings ONLY when impossible otherwise
    - item_search is the ONLY embedding source
    - do not use the vendor name to define the categorical data unless its very important for the embedding data or user says form that vendor/shop/store

    You are an analytics-grade Text-to-SQL agent for receipts.

    """

def create_final_answer_prompt() -> str:
    """
    Create the system prompt for generating final natural language answers.
    
    Returns:
        str: System prompt for answer generation
    """
    return """You are a helpful assistant that translates database query results into clear, natural language answers.

Your task is to:
1. Understand the user's original question
2. Analyze the query results
3. Provide a clear, concise, and accurate answer in natural language

Guidelines:
- Be direct and answer the question specifically
- Use natural, conversational language
- If there are multiple results, summarize them clearly
- If there are no results, explain what that means
- Don't mention technical details like SQL or database operations unless relevant
- Focus on the information the user wants to know"""

def create_sql_retry_prompt(user_request: str, error_history_text: str,database_schema: str) -> str:
    """
    Create the user message for SQL query regeneration after failures.
    
    Args:
        user_request: Original user request
        error_history_text: Formatted text with history of all failed attempts
        
    Returns:
        str: User message with error context for regeneration
    """
    return f"""Original request: {user_request}

    ALL PREVIOUS ATTEMPTS HAVE FAILED. Here is the complete history:
    {error_history_text}

    CRITICAL INSTRUCTIONS:
    1. Analyze ALL previous attempts and their specific errors
    2. DO NOT repeat the same mistakes from previous attempts
    3. If multiple attempts failed with the same type of error, try a completely different approach
    4. Generate a CORRECTED SQL query that addresses ALL the errors seen so far

    SCHEMA ANALYSIS IS MANDATORY 
    - You MUST deeply analyze the schema structure, table names, column names, and data types.
    - Pay EXTREME attention to exact column names, especially *_embed fields.
    - Do NOT hallucinate tables or columns that do not exist in the schema.
    - If a column appears ambiguous, re-check the schema and choose the safest valid option.
    - Your SQL MUST be fully consistent with the schema — assume validation will fail otherwise.

    Common issues to check:
    - Syntax errors (check PostgreSQL syntax carefully)
    - Missing or incorrect table/column names (verify against schema)
    - Incorrect JOINs (ensure proper relationships)
    - Type mismatches (especially with vector types)
    - Missing WHERE clauses for NULL checks on embedding fields
    - Placeholder count mismatch (ensure embedding_params matches %s count in query)
    - If you need to reuse the same embedding multiple times in a query, you MUST list it multiple times in embedding_params
    - Vector columns in GROUP BY: You CANNOT include vector columns (ending in _embed) in GROUP BY

    FINAL CHECK BEFORE OUTPUT:
    - Re-validate the query against the schema one last time
    - Ensure it follows ALL safety and GROUP BY rules
    - Ensure it will pass strict SQL validation without retries

    Learn from previous failures and generate a query that will execute successfully.
    ALWAYS return valid JSON:

    {{
      "sql_query": "SQL with %s::vector placeholders",
      "need_embedding": true/false,
      "embedding_params": [
        {{
          "placeholder": "param_1",
          "text_to_embed": "text used to generate embedding",
          "description": "what this embedding represents"
        }}
      ]
    }}
    """

def create_final_answer_user_message(user_request: str, results_text: str, sql_query: str = None) -> str:
    """
    Create the user message for final answer generation.
    
    Args:
        user_request: Original user request
        results_text: Formatted query results text
        sql_query: The SQL query that was executed (optional)
        
    Returns:
        str: User message for answer generation
    """
    message = f"""
    write in natural language that human understand 
    do not provide unnecessary json type
    User's Question: {user_request}

    Query Results:
    {results_text}

    Please provide a clear, natural language answer to the user's question based on these results."""
    
    # Add SQL context if provided
    if sql_query:
        message += f"\n\nFor context, the SQL query used was:\n{sql_query}"
    
    return message



































"""
Here, “impulse” is not a database or SQL term—it’s a behavioral concept used to classify purchases.

What “impulse purchases” means in this context

Impulse purchases = items bought spontaneously, without prior planning or necessity.

Think:

Bought on the spot

Triggered by emotion, curiosity, discounts, or visibility

Not part of a routine or planned expense

How that meaning is used in your query

Your system doesn’t have an explicit is_impulse flag, so it infers impulse semantically using embeddings.

This part is key:

s.embed <-> %s::vector < 0.45

s.embed = vector embedding of item descriptions / search text

%s::vector = embedding for
"impulse buying unplanned spontaneous purchases"

<-> = vector distance (semantic similarity)

So the query is asking:

“Find items whose meaning is close to impulse buying / unplanned purchases, and sum how much was spent on them this month.”

Examples of what would count as “impulse” here

Likely counted ✅:

Snacks, chocolates, soft drinks

Random accessories

Small gadgets

Add-on items near checkout

One-off novelty items

Less likely counted ❌:

Groceries bought regularly

Rent, utilities

Fuel

Medicine

Planned electronics purchases

Why embeddings are needed

Because:

There is no fixed category called “impulse”

The system relies on semantic similarity, not hard rules

That’s why need_embedding: true is required

In simple words

“Impulse purchases this month” =
Money spent this month on items that look like spontaneous or unplanned buys, inferred using AI embeddings rather than explicit tags.
"""
