#!/usr/bin/env python3
"""
Text-to-SQL Agent - Main Entry Point
Demonstrates the complete pipeline: SQL generation, query execution, and final answer generation
"""

import sys
from textToSqlAgent import AgentTextToSql


def print_result(result: dict):
    """Pretty print the complete result."""
    print("\n" + "=" * 80)
    print("COMPLETE PIPELINE RESULT")
    print("=" * 80)
    
    print("\n📝 USER REQUEST:")
    print(f"  {result['user_request']}")
    
    # Show attempts and retry info
    attempts = result.get('attempts', 1)
    failed_attempts = result.get('failed_attempts', [])
    
    if attempts > 1 or failed_attempts:
        print(f"\n🔄 RETRY INFO:")
        print(f"  Total Attempts: {attempts}")
        if failed_attempts:
            print(f"  Failed Attempts: {len(failed_attempts)}")
            for i, failed in enumerate(failed_attempts, 1):
                print(f"    Attempt {i} Error: {failed['error'][:100]}...")
    
    print("\n🔧 GENERATED SQL:")
    print(f"  {result.get('sql_query', 'N/A')}")
    
    print(f"\n🧮 NEEDS EMBEDDING: {result.get('need_embedding', False)}")
    if result.get('need_embedding') and result.get('embedding_params'):
        print(f"  Embedding Parameters: {len(result['embedding_params'])}")
        for param in result['embedding_params']:
            print(f"    - {param['placeholder']}: {param['text_to_embed']}")
    
    print("\n📊 QUERY RESULTS:")
    query_results = result.get('query_results', {})
    if query_results.get('success', False):
        print(f"  Rows Retrieved: {query_results['row_count']}")
        if query_results['row_count'] > 0:
            print(f"  Columns: {', '.join(query_results['column_names'])}")
    else:
        print(f"  Error: {query_results.get('error', 'Unknown error')}")
    
    print("\n💬 FINAL ANSWER:")
    print(f"  {result.get('final_answer', 'No answer generated')}")
    
    print("\n" + "=" * 80)


def run_example(agent: AgentTextToSql, query: str):
    """Run a single example query."""
    print("\n" + "🚀" * 40)
    print(f"\n🔍 PROCESSING: {query}")
    print("\n" + "🚀" * 40)
    
    try:
        result = agent.process_request_with_execution(query)
        
        if result["success"]:
            print_result(result)
        else:
            print(f"\n❌ Error: {result['error']}")
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")



def main():
    """Interactive mode for testing queries."""
    print("=" * 80)
    print("TEXT-TO-SQL AGENT")
    print("=" * 80)
    print("\nType your questions in natural language.")
    print("Type 'quit' or 'exit' to stop.\n")
    
    try:
        agent = AgentTextToSql()
        print("✅ Agent initialized\n")
        
        while True:
            try:
                user_query = input("📝 Your question: ").strip()
                
                if user_query.lower() in ['quit', 'exit', 'q']:
                    print("\n👋 Goodbye!")
                    break
                
                if not user_query:
                    continue
                
                result = agent.process_request_with_execution(user_query)
                
                if result["success"]:
                    print_result(result)
                else:
                    print(f"\n❌ Error: {result['error']}")
                
                print("\n")
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")
                
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()