#!/usr/bin/env python3
"""
Text-to-SQL Agent with Vector Embeddings Support
Professional agent for converting natural language queries to SQL
using LOCAL Ollama LLM (gemma3) and LOCAL embeddings (bge-m3).
"""

import os
import json
import logging
import psycopg2
import sqlglot
import requests
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from db_utils import generate_db_schema
from prompt import (
    create_text_to_sql_prompt,
    create_final_answer_prompt,
    create_sql_retry_prompt,
    create_final_answer_user_message
)

# =====================================================
# CONFIG
# =====================================================

load_dotenv()

OLLAMA_BASE_URL = "http://localhost:11434"
SQL_LLM_MODEL = "qwen2.5-coder:3b"
FINAL_LLM_MODEL = "gemma3:1b"
EMBEDDING_MODEL = "bge-m3"


# Configure logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s",
                    force=True)
logger = logging.getLogger(__name__)


class AgentTextToSql:
    """
    Text-to-SQL Agent using Ollama (gemma3) + bge-m3 embeddings.
    """

    DEFAULT_DB_CONFIG = {
        "host": "localhost",
        "port": 5432,
        "database": "receipt_db",
        "user": "postgres",
        "password": os.getenv("DATABASE_PWD")
    }

    def __init__(self, db_config: Dict[str, Any] = None, temperature: float = 0.1):
        self.temperature = temperature
        self.database_schema = None
        self.db_config = db_config or self.DEFAULT_DB_CONFIG

        self._load_database_schema()

    # =====================================================
    # DB SCHEMA
    # =====================================================

    def _load_database_schema(self) -> None:
        try:
            conn = psycopg2.connect(**self.db_config)
            formatted_text, _ = generate_db_schema(conn)
            self.database_schema = formatted_text
            conn.close()
            logger.info("Database schema loaded successfully")
        except Exception as e:
            logger.error(f"Schema load failed: {e}")
            raise

    # =====================================================
    # PROMPT
    # =====================================================

    def _create_system_prompt(self) -> str:
        return create_text_to_sql_prompt(self.database_schema)

    # =====================================================
    # OLLAMA CHAT
    # =====================================================

    def _ollama_chat(self, system_prompt, user_prompt, model):
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "options": {"temperature": self.temperature},
            "format": "json",
            "stream": False
        }

        r = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=300)
        r.raise_for_status()
        return json.loads(r.json()["message"]["content"])


    # =====================================================
    # SQL GENERATION
    # =====================================================

    def generate_sql(self, user_request: str) -> Dict[str, Any]:
        logger.info(f"User request: {user_request}")
        system_prompt = self._create_system_prompt()
        result = self._ollama_chat(system_prompt, user_request,SQL_LLM_MODEL)

        for key in ["sql_query", "need_embedding", "embedding_params"]:
            if key not in result:
                raise ValueError(f"Missing key '{key}' in LLM response")

        if result["need_embedding"] and not result["embedding_params"]:
            raise ValueError("need_embedding is true but embedding_params empty")

        if not result["need_embedding"] and result["embedding_params"]:
            raise ValueError("need_embedding is false but embedding_params not empty")

        return result

    def _populate_all_missing_embeddings(self, conn):
        """
        Scans the database for any items missing embeddings and populates them.
        This ensures the vector search has a full dataset to work with.
        """
        cur = conn.cursor()
        
        # Identify items that have no entry in item_search OR have a NULL embed
        cur.execute("""
            SELECT i.item_id, i.name
            FROM items i
            LEFT JOIN item_search s ON i.item_id = s.item_id
            WHERE s.embed IS NULL;
        """)
        
        rows = cur.fetchall()
        if not rows:
            logger.info("No missing embeddings found.")
            return

        logger.info(f"Lazy-loading embeddings for {len(rows)} items...")

        for item_id, name in rows:
            # Generate the vector for the item name
            emb = self._generate_embedding(name)
            
            # Upsert into item_search
            cur.execute("""
                INSERT INTO item_search (item_id, embed)
                VALUES (%s, %s)
                ON CONFLICT (item_id)
                DO UPDATE SET embed = EXCLUDED.embed;
            """, (item_id, emb))

        conn.commit()
        logger.info("Database embeddings are now up to date.")

    # =====================================================
    # EMBEDDINGS (OLLAMA bge-m3)
    # =====================================================

    # def _populate_missing_item_embeddings(self, conn, item_ids: List[int]):
    #     if not item_ids:
    #         return

    #     cur = conn.cursor()
    #     cur.execute("""
    #         SELECT i.item_id, i.name
    #         FROM items i
    #         LEFT JOIN item_search s ON i.item_id = s.item_id
    #         WHERE s.embed IS NULL
    #         AND i.item_id = ANY(%s);
    #     """, (item_ids,))

    #     rows = cur.fetchall()
    #     if not rows:
    #         return

    #     logger.info(f"Generating embeddings for {len(rows)} items")

    #     for item_id, name in rows:
    #         emb = self._generate_embedding(name)
    #         cur.execute("""
    #             INSERT INTO item_search (item_id, embed)
    #             VALUES (%s, %s)
    #             ON CONFLICT (item_id)
    #             DO UPDATE SET embed = EXCLUDED.embed;
    #         """, (item_id, emb))

    #     conn.commit()
  


    def _generate_embedding(self, text: str) -> List[float]:
        payload = {
            "model": EMBEDDING_MODEL,
            "prompt": text
        }

        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/embeddings",
            json=payload,
            timeout=300
        )
        response.raise_for_status()
        return response.json()["embedding"]

    def _generate_embeddings_for_params(self, embedding_params: List[Dict[str, str]]) -> List[str]:
        vectors = []
        for param in embedding_params:
            emb = self._generate_embedding(param["text_to_embed"])
            vectors.append("[" + ",".join(map(str, emb)) + "]")
        return vectors

    # =====================================================
    # SQL VALIDATION
    # =====================================================

    def _validate_sql_query(self, sql_query: str) -> tuple[bool, Optional[str]]:
        try:
            statements = [s for s in sql_query.split(";") if s.strip()]
            if len(statements) > 1:
                return False, "Multiple SQL statements detected"

            forbidden = [
                "INSERT", "UPDATE", "DELETE", "DROP", "CREATE",
                "ALTER", "TRUNCATE", "MERGE", "CALL"
            ]

            q = sql_query.upper()
            for k in forbidden:
                if k in q:
                    return False, f"Dangerous operation: {k}"

            if not q.strip().startswith("SELECT"):
                return False, "Only SELECT allowed"

            if "GROUP BY" in q and "_embed" in q.lower():
                return False, "Vector columns not allowed in GROUP BY"

            sqlglot.parse_one(sql_query.replace("<->", "+"), read="postgres")
            return True, None

        except Exception as e:
            return False, str(e)

    # =====================================================
    # SQL EXECUTION
    # =====================================================
    """
    def execute_sql(self, sql_query: str, need_embedding=False, embedding_params=None):
        logger.info(f"Executing SQL: {sql_query}")
        is_valid, err = self._validate_sql_query(sql_query)
        logger.info(f"SQL validation: is_valid={is_valid}, err={err}")
        if not is_valid:
            return {"success": False, "error": err}

        conn = psycopg2.connect(**self.db_config)
        cur = conn.cursor()

        try:
            params = []
            if need_embedding:
                embeddings = self._generate_embeddings_for_params(embedding_params)
                for emb in embeddings:
                    sql_query = sql_query.replace(
                        "%s::vector", f"'{emb}'::vector", 1
                    )

            cur.execute(sql_query)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]

            conn.close()
            return {
                "success": True,
                "row_count": len(rows),
                "results": [dict(zip(cols, r)) for r in rows],
                "column_names": cols
            }

        except Exception as e:
            conn.close()
            return {"success": False, "error": str(e)}"""
    
    # def execute_sql(self, sql_query: str, need_embedding=False, embedding_params=None):
    #     logger.info(f"--- START SQL EXECUTION ---")
    #     logger.info(f"Executing SQL: {sql_query}")
        
    #     is_valid, err = self._validate_sql_query(sql_query)
    #     logger.info(f"SQL validation: is_valid={is_valid}, err={err}")
        
    #     if not is_valid:
    #         logger.error(f"SQL Validation failed: {err}")
    #         return {"success": False, "error": err}

    #     try:
    #         logger.info("Connecting to database...")
    #         conn = psycopg2.connect(**self.db_config)
    #         cur = conn.cursor()
    #         logger.info("Database connection successful.")

    #         if need_embedding:
    #             logger.info(f"Generating embeddings for {len(embedding_params)} params...")
    #             embeddings = self._generate_embeddings_for_params(embedding_params)
                
    #             for i, emb in enumerate(embeddings):
    #                 # Using a counter to track replacement
    #                 sql_query = sql_query.replace("%s::vector", f"'{emb}'::vector", 1)
    #                 logger.debug(f"Injected embedding for param index {i}")

    #         logger.info(f"Final Query to be sent to DB: {sql_query}")
            
    #         cur.execute(sql_query)
    #         logger.info("Query execution complete. Fetching results...")
            
    #         rows = cur.fetchall()
    #         cols = [d[0] for d in cur.description]
            
    #         logger.info(f"Successfully fetched {len(rows)} rows with columns: {cols}")

    #         if need_embedding and "item_id" in cols:
    #             item_id_idx = cols.index("item_id")
    #             item_ids = list({r[item_id_idx] for r in rows})
    #             self._populate_missing_item_embeddings(conn, item_ids)

    #             # re-run query now that embeddings exist
    #             cur.execute(sql_query)
    #             rows = cur.fetchall()

    #         conn.close()
    #         logger.info("Database connection closed.")
            
    #         return {
    #             "success": True,
    #             "row_count": len(rows),
    #             "results": [dict(zip(cols, r)) for r in rows],
    #             "column_names": cols
    #         }

    #     except Exception as e:
    #         # CRITICAL: This was likely happening silently
    #         logger.error(f"DATABASE EXECUTION ERROR: {str(e)}", exc_info=True)
    #         if 'conn' in locals() and conn:
    #             conn.close()
    #             logger.info("Database connection closed after error.")
    #         return {"success": False, "error": str(e)}
    def execute_sql(self, sql_query: str, need_embedding=False, embedding_params=None):
        logger.info(f"--- START SQL EXECUTION ---")
        
        is_valid, err = self._validate_sql_query(sql_query)
        if not is_valid:
            logger.error(f"SQL Validation failed: {err}")
            return {"success": False, "error": err}

        conn = None
        try:
            logger.info("Connecting to database...")
            conn = psycopg2.connect(**self.db_config)
            
            # --- STEP 1: POPULATE DATABASE EMBEDDINGS FIRST ---
            if need_embedding:
                # Check the whole table for missing vectors before doing anything else
                self._populate_all_missing_embeddings(conn)

            # --- STEP 2: PREPARE PARAMETER EMBEDDINGS ---
            if need_embedding and embedding_params:
                logger.info(f"Generating embeddings for {len(embedding_params)} search parameters...")
                embeddings = self._generate_embeddings_for_params(embedding_params)
                
                for i, emb in enumerate(embeddings):
                    # Inject the generated vector into the query
                    sql_query = sql_query.replace("%s::vector", f"'{emb}'::vector", 1)

            # --- STEP 3: EXECUTE THE ACTUAL QUERY ---
            logger.info(f"Executing final SQL: {sql_query}")
            cur = conn.cursor()
            cur.execute(sql_query)
            
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            
            logger.info(f"Query successful. Returned {len(rows)} rows.")
            
            return {
                "success": True,
                "row_count": len(rows),
                "results": [dict(zip(cols, r)) for r in rows],
                "column_names": cols
            }

        except Exception as e:
            logger.error(f"DATABASE EXECUTION ERROR: {str(e)}", exc_info=True)
            if conn:
                conn.rollback()
            return {"success": False, "error": str(e)}
        finally:
            if conn:
                conn.close()
                logger.info("Database connection closed.")
    # def execute_sql(self, sql_query: str, need_embedding=False, embedding_params=None):
    #     logger.info("--- START SQL EXECUTION ---")
    #     logger.info(f"Executing SQL: {sql_query}")

    #     is_valid, err = self._validate_sql_query(sql_query)
    #     if not is_valid:
    #         logger.error(f"SQL Validation failed: {err}")
    #         return {"success": False, "error": err}

    #     conn = None
    #     try:
    #         conn = psycopg2.connect(**self.db_config)
    #         cur = conn.cursor()
    #         logger.info("Database connection successful.")

    #         # ✅ STEP 1: Populate missing embeddings BEFORE query
    #         if need_embedding:
    #             logger.info("Ensuring missing embeddings are generated...")
    #             self._populate_missing_item_embeddings(conn, embedding_params)

    #         # ✅ STEP 2: Generate query embedding ONCE
    #         query_embedding = None
    #         if need_embedding:
    #             query_embedding = self._generate_embeddings_for_params(embedding_params)

    #         # ✅ STEP 3: Execute query safely
    #         if need_embedding:
    #             cur.execute(sql_query, (query_embedding,))
    #         else:
    #             cur.execute(sql_query)

    #         rows = cur.fetchall()
    #         cols = [d[0] for d in cur.description]

    #         logger.info(f"Fetched {len(rows)} rows")

    #         return {
    #             "success": True,
    #             "row_count": len(rows),
    #             "results": [dict(zip(cols, r)) for r in rows],
    #             "column_names": cols,
    #         }

    #     except Exception as e:
    #         logger.error("DATABASE EXECUTION ERROR", exc_info=True)
    #         return {"success": False, "error": str(e)}

    #     finally:
    #         if conn:
    #             conn.close()
    #             logger.info("Database connection closed.")

    # =====================================================
    # FINAL ANSWER
    # =====================================================

    """"
    def generate_final_answer(self, user_request, query_results, sql_query=None):
        system_prompt = create_final_answer_prompt()
        user_msg = create_final_answer_user_message(
            user_request,
            json.dumps(query_results, indent=2),
            sql_query
        )

        result = self._ollama_chat(system_prompt, user_msg)
        return result.get("answer", str(result))"""

    def generate_final_answer(self, user_request, query_results, sql_query=None):
        logger.info("--- STARTING FINAL ANSWER GENERATION ---")
        logger.info(f"User Request: {user_request}")
        
        # Log a preview of the query results so you don't flood the logs if the list is huge
        row_count = len(query_results) if isinstance(query_results, list) else "N/A"
        logger.info(f"Data context: {row_count} rows found in DB.")

        try:
            system_prompt = create_final_answer_prompt()
            user_msg = create_final_answer_user_message(
                user_request,
                json.dumps(query_results, indent=2, default=str),
                sql_query
            )

            logger.info("Sending data to Ollama for natural language formatting...")
            
            # Call the LLM
            result = self._ollama_chat(system_prompt, user_msg,FINAL_LLM_MODEL)
            
            # Log the raw LLM response for debugging
            logger.info(f"Raw LLM Output: {result}")

            # Extract answer
            final_answer = result.get("answer", str(result))
            
            logger.info(f"Successfully generated natural language answer. {final_answer}")
            return final_answer

        except Exception as e:
            logger.error(f"Error during final answer generation: {str(e)}", exc_info=True)
            return "I found the data, but I'm having trouble explaining it. Please check the logs."
    # =====================================================
    # FULL PIPELINE WITH RETRIES
    # =====================================================

    def _regenerate_sql_with_error_feedback(
        self,
        user_request: str,
        attempt_history: List[Dict[str, str]],
        attempt: int
    ) -> Dict[str, Any]:
        """
        Regenerate SQL query by providing comprehensive error feedback to the LLM.
        Uses the same execution path as generate_sql (Ollama-based).
        """

        logger.info(
            f"Regenerating SQL with error feedback (attempt {attempt}, "
            f"{len(attempt_history)} previous failures)"
        )

        system_prompt = self._create_system_prompt()

        # -------------------------------
        # Build error history text
        # -------------------------------
        error_history_text = ""
        for i, prev in enumerate(attempt_history, 1):
            error_history_text += (
                f"\nATTEMPT {i}:\n"
                f"SQL Query:\n{prev['sql']}\n"
                f"Error:\n{prev['error']}\n"
                f"{'-' * 40}\n"
            )

        # -------------------------------
        # Build retry user prompt
        # (you said this part is already done)
        # -------------------------------
        retry_prompt = create_sql_retry_prompt(
            user_request=user_request,
            error_history_text=error_history_text,
            database_schema=self.database_schema
        )

        # -------------------------------
        # Call LLM (same as generate_sql)
        # -------------------------------
        result = self._ollama_chat(
            system_prompt,
            retry_prompt,
            SQL_LLM_MODEL
        )

        # -------------------------------
        # Validate response (same rules)
        # -------------------------------
        logger.info(f"Regenerated SQL response: {result}")
        for key in ["sql_query", "need_embedding", "embedding_params"]:
            if key not in result:
                raise ValueError(f"Missing key '{key}' in LLM response")

        if result["need_embedding"] and not result["embedding_params"]:
            raise ValueError("need_embedding is true but embedding_params empty")

        if not result["need_embedding"] and result["embedding_params"]:
            raise ValueError("need_embedding is false but embedding_params not empty")

        return result


    def process_request_with_execution(self, user_request: str, max_retries=4):
        attempt_history = []
        sql_res = None
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                logger.info("=" * 80)
                logger.info(f"ATTEMPT {attempt}/{max_retries}")
                logger.info("=" * 80)

                # -------------------------------
                # STEP 1: Generate / Regenerate SQL
                # -------------------------------
                if attempt == 1:
                    logger.info("Generating SQL (initial attempt)")
                    sql_res = self.generate_sql(user_request)
                else:
                    logger.info("Regenerating SQL with error feedback")
                    sql_res = self._regenerate_sql_with_error_feedback(
                        user_request=user_request,
                        attempt_history=attempt_history,
                        attempt=attempt
                    )

                logger.info(f"Generated SQL: {sql_res}")

                # -------------------------------
                # STEP 2: Execute SQL
                # -------------------------------
                exec_res = self.execute_sql(
                    sql_res["sql_query"],
                    sql_res.get("need_embedding", False),
                    sql_res.get("embedding_params", [])
                )

                logger.info(f"Execution result: {exec_res}")

                if not exec_res.get("success", False):
                    last_error = exec_res.get("error", "Unknown execution error")

                    attempt_history.append({
                        "sql": sql_res["sql_query"],
                        "error": last_error
                    })

                    logger.warning(f"Attempt {attempt} failed: {last_error}")
                    continue

                # -------------------------------
                # STEP 3: Generate Final Answer
                # -------------------------------

                """
                answer = self.generate_final_answer(
                    user_request,
                    exec_res,
                    sql_res["sql_query"]
                )
                """
                logger.info("Pipeline completed successfully")

                return {
                    "success": True,
                    "user_request": user_request,
                    "sql_query": sql_res["sql_query"],
                    "need_embedding": sql_res.get("need_embedding", False),
                    "embedding_params": sql_res.get("embedding_params", []),
                    "query_results": exec_res,
                    "final_answer": exec_res,
                    "failed_attempts": attempt_history,
                    "attempts": attempt
                }

            except Exception as e:
                last_error = str(e)
                logger.error(f"Attempt {attempt} crashed: {last_error}")

                attempt_history.append({
                    "sql": sql_res.get("sql_query", "SQL generation failed") if sql_res else None,
                    "error": last_error
                })

        # -------------------------------
        # All retries failed
        # -------------------------------
        logger.error("All retries exhausted")

        return {
            "success": False,
            "user_request": user_request,
            "error": f"Failed after {max_retries} attempts. Last error: {last_error}",
            "attempts": max_retries,
            "failed_attempts": attempt_history,
            "last_sql_query": sql_res["sql_query"] if sql_res else None
        }
