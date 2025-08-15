from dotenv import load_dotenv
load_dotenv()

import os
import asyncio
from tyler import Agent, Thread, Message, ThreadStore, FileStore, AgentResult

async def main():
    """
    Demonstrates explicitly creating and setting stores for an Agent.
    """
    # 1. Create stores.
    #    By default, this uses in-memory stores. To persist across runs, set env vars:
    #      NARRATOR_DATABASE_URL (e.g., "sqlite+aiosqlite:///threads.db")
    #      FILE_STORE_PATH (e.g., "./stored_files")
    database_url = os.getenv("NARRATOR_DATABASE_URL")
    file_store_path = os.getenv("FILE_STORE_PATH")

    thread_store = await ThreadStore.create(database_url) if database_url else await ThreadStore.create()
    file_store = await FileStore.create(base_path=file_store_path) if file_store_path else await FileStore.create()
    print(f"Created in-memory stores:")
    print(f"  Thread Store: {type(thread_store)}")
    print(f"  File Store: {type(file_store)}")
    
    # 2. Initialize the agent with explicit stores.
    #    Pass the store instances directly to the Agent constructor.
    agent = Agent(
        name="StoreAwareAssistant",
        purpose="Answer questions concisely using explicitly set stores.",
        model_name="gpt-4o",
        thread_store=thread_store,  # Pass store instance directly
        file_store=file_store       # Pass store instance directly
    )
    print(f"Initialized agent: {agent.name}")
    print("Agent configured with explicit stores.")

    # 3. Create a new thread. Because the agent is configured with stores,
    #    operations like saving the thread will use the provided stores.
    thread = Thread()
    print(f"Created new thread with ID: {thread.id}")

    # 4. Add a user message
    user_message = Message(role="user", content="What is the capital of Spain?")
    thread.add_message(user_message)
    print(f"Added user message: '{user_message.content}'")

    # 5. Run the agent. It will use the configured stores internally.
    print("Running agent...")
    result = await agent.go(thread)
    print("Agent finished processing.")

    # 6. Print the assistant's response and execution details
    print(f"Assistant Response: {result.content}")
            
    # The thread is automatically saved to the store during execution
    print(f"Thread saved to store with ID: {thread.id}")

    # 7. Demonstrate sharing stores between multiple agents
    print("\n--- Sharing Stores Between Agents ---")
    
    # Create a second agent that uses the same stores
    second_agent = Agent(
        name="SecondAssistant", 
        purpose="Another assistant that shares the same storage.",
        model_name="gpt-4o",
        thread_store=thread_store,  # Same store instance
        file_store=file_store       # Same store instance
    )
    print(f"Created second agent: {second_agent.name}")
    print("Both agents now share the same thread and file stores!")

    # 8. Simulate a reload from the store to demonstrate persistence/continuity
    #    (Even with in-memory, this exercises the store API)
    reloaded_thread = await thread_store.get(thread.id)
    print(f"Reloaded thread {reloaded_thread.id} from store (messages: {len(reloaded_thread.messages)})")

    # 9. Have the second agent continue the conversation on the same (reloaded) thread
    print("\n--- Follow-up With Second Agent On Same Thread ---")
    follow_up_message = Message(
        role="user",
        content="Thanks! As a follow-up, tell me one fun fact related to your previous answer."
    )
    reloaded_thread.add_message(follow_up_message)
    print(f"Added follow-up user message: '{follow_up_message.content}'")
    print(f"Thread now has {len(reloaded_thread.messages)} messages (continuing the same conversation)")

    print("Running second agent on the existing thread...")
    second_result = await second_agent.go(reloaded_thread)
    print("Second agent finished processing.")
    print(f"Second Assistant Response: {second_result.content}")

    # Note: Since the stores are in-memory, the thread data still only exists
    # for the duration of this script run. To persist data, you would provide
    # a database URL to ThreadStore.create and a directory path to FileStore.create
    # 
    # For persistent storage:
    # thread_store = await ThreadStore.create("sqlite+aiosqlite:///threads.db")
    # file_store = await FileStore.create(base_path="./stored_files")

if __name__ == "__main__":
    # Added basic error handling for asyncio run
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"An error occurred: {e}") 