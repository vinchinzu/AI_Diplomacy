import llm
import os
import asyncio
import logging

# Configure logging to see more details from the llm library if it uses standard logging
logging.basicConfig(level=logging.DEBUG)

# --- Configuration ---
# These should match the values you expect to be set by run.sh or your environment
# For this test, we'll explicitly set them to ensure clarity.
# You can also comment these out and set them in your shell before running the script.
DESIRED_OLLAMA_PORT = os.environ.get("OLLAMA_PORT", "11434")
DESIRED_OLLAMA_HOST = f"http://127.0.0.1:{DESIRED_OLLAMA_PORT}"
DESIRED_OLLAMA_BASE_URL = f"http://127.0.0.1:{DESIRED_OLLAMA_PORT}"

# Explicitly set them in the environment for this script's execution context
os.environ["OLLAMA_HOST"] = DESIRED_OLLAMA_HOST
os.environ["OLLAMA_BASE_URL"] = DESIRED_OLLAMA_BASE_URL
os.environ["OLLAMA_PORT"] = DESIRED_OLLAMA_PORT


print("--- Test Script Configuration ---")
print(f"Attempting to use OLLAMA_PORT: {os.environ.get('OLLAMA_PORT')}")
print(f"Attempting to use OLLAMA_HOST: {os.environ.get('OLLAMA_HOST')}")
print(f"Attempting to use OLLAMA_BASE_URL: {os.environ.get('OLLAMA_BASE_URL')}")
print("---------------------------------")

MODEL_NAME = "gemma3:latest" # Same model as in run.sh
# Some llm setups might require the plugin prefix, e.g., "ollama/gemma3:latest"
# We'll try the plain name first as used in your run.sh fixed_models argument.

async def main():
    try:
        print(f"Attempting to get model: '{MODEL_NAME}' using llm.get_async_model()")
        # This is a common way to get an async model instance using the llm library
        model = llm.get_async_model(MODEL_NAME)
        
        if model:
            print(f"Successfully got model object: {model}")
            print(f"Model ID: {model.model_id}")
            # The provider attribute can tell us if it's correctly identified as an Ollama model
            if hasattr(model, 'provider'):
                print(f"Model provider: {model.provider}")
            
            # Check if the model object itself has an explicit ollama_url configured
            # This could come from alias definitions or plugin defaults not found in files
            effective_ollama_url = None
            if hasattr(model, 'options') and isinstance(model.options, dict) and 'ollama_url' in model.options:
                effective_ollama_url = model.options['ollama_url']
                print(f"!!! Found 'ollama_url' in model.options: {effective_ollama_url}")
            elif hasattr(model, 'ds') and hasattr(model.ds, 'options') and isinstance(model.ds.options, dict) and 'ollama_url' in model.ds.options: # Compatibility for older llm versions
                effective_ollama_url = model.ds.options['ollama_url']
                print(f"!!! Found 'ollama_url' in model.ds.options: {effective_ollama_url}")

            # Attempt a simple prompt
            prompt_text = "Hello, Ollama!"
            print(f"Sending prompt: '{prompt_text}' to model '{model.model_id}'")
            
            # The .prompt() method is usually asynchronous
            response_obj = await model.prompt(prompt_text)
            
            # Process the response
            response_text = await response_obj.text()
            print(f"LLM Response: {response_text}")
            print("--- Test Successful: Connection and basic LLM call completed! ---")
        else:
            print(f"Failed to get model: {MODEL_NAME}. llm.get_async_model() returned None or an error occurred before this point.")

    except Exception as e:
        print("--- Test Failed: An error occurred ---")
        print(f"Error type: {type(e)}")
        print(f"Error message: {e}")
        import traceback
        print("Traceback:")
        traceback.print_exc()
        print("------------------------------------")

# --- Synchronous Test Function ---
def test_synchronous_model():
    print("\n--- Starting Synchronous LLM Connection Test ---")
    try:
        print(f"Attempting to get model: '{MODEL_NAME}' using llm.get_model() (synchronous)")
        # The Ollama plugin should pick up OLLAMA_HOST/OLLAMA_BASE_URL from environment variables
        model = llm.get_model(MODEL_NAME)
        
        if model:
            print(f"Successfully got synchronous model object: {model}")
            print(f"Synchronous Model ID: {model.model_id}")
            
            if hasattr(model, 'provider'):
                print(f"Synchronous Model provider: {model.provider}")

            # Check if the model object itself has an explicit ollama_url configured
            effective_ollama_url = None
            if hasattr(model, 'options') and isinstance(model.options, dict) and 'ollama_url' in model.options:
                effective_ollama_url = model.options['ollama_url']
                print(f"!!! Found 'ollama_url' in synchronous model.options: {effective_ollama_url}")
            elif hasattr(model, 'ds') and hasattr(model.ds, 'options') and isinstance(model.ds.options, dict) and 'ollama_url' in model.ds.options:
                effective_ollama_url = model.ds.options['ollama_url']
                print(f"!!! Found 'ollama_url' in synchronous model.ds.options: {effective_ollama_url}")
            
            if effective_ollama_url == DESIRED_OLLAMA_BASE_URL or effective_ollama_url == DESIRED_OLLAMA_HOST:
                 print(f"Synchronous model is correctly configured for {effective_ollama_url}")
            else:
                print(f"WARNING: Synchronous model's effective Ollama URL '{effective_ollama_url}' does not match desired '{DESIRED_OLLAMA_BASE_URL}' or '{DESIRED_OLLAMA_HOST}'")


            # Attempt a simple prompt using the synchronous model
            # Note: The exact method for synchronous execution can vary.
            # Some models might have a .prompt(...).text() sequence that's blocking,
            # others might have a specific .invoke() or similar.
            # We'll try common patterns.
            prompt_text = "Hello, synchronous Ollama!"
            print(f"Sending prompt: '{prompt_text}' to synchronous model '{model.model_id}'")
            
            response_obj = model.prompt(prompt_text) # This might be async on some model objects
                                                    # or return a response object that needs to be awaited or iterated.
            
            # If model.prompt() returns a future or awaitable, this won't work directly.
            # For simplicity, we'll assume it might return a Response object with a .text property or method
            # that can be called synchronously or is already resolved.
            # This part is highly dependent on the specific llm library version and model class.
            
            # A common pattern for synchronous execution or getting text from response:
            response_text = ""
            if hasattr(response_obj, 'text'):
                if callable(response_obj.text):
                    try:
                        # Attempt to call it, might be async, might be sync
                        response_text = response_obj.text()
                        if asyncio.iscoroutine(response_text): # Check if it returned a coroutine
                             print("Response.text() is a coroutine, trying to run it synchronously (this might fail if not designed for it)")
                             # This is a simplified way, proper handling might need asyncio.run in a new thread for true sync blocking
                             # For a test script, this might be okay or reveal issues.
                             try:
                                 response_text = asyncio.run(response_text) # This is problematic if an event loop is already running.
                             except RuntimeError as re:
                                 print(f"Could not run response_obj.text() with asyncio.run: {re}. The main script uses asyncio.run(main()).")
                                 print("This indicates that model.prompt() for the sync model might still be async internally or require different handling.")
                                 response_text = "[Could not retrieve async text synchronously in this context]"
                        # If not a coroutine, assume it's the text
                    except Exception as call_e:
                        print(f"Error calling response_obj.text(): {call_e}")
                        response_text = f"[Error during text retrieval: {call_e}]"
                else: # It's an attribute
                    response_text = response_obj.text
            elif isinstance(response_obj, str): # Sometimes it might just return a string
                response_text = response_obj
            else: # Last resort, convert response object to string
                response_text = str(response_obj)


            print(f"Synchronous LLM Response: {response_text}")
            if "Could not retrieve" not in response_text and "Error during text retrieval" not in response_text:
                 print("--- Synchronous Test Successful (Model retrieval and basic prompt attempt) ---")
            else:
                 print("--- Synchronous Test Partially Successful (Model retrieval OK, prompting had issues) ---")

        else:
            print(f"Failed to get synchronous model: {MODEL_NAME}. llm.get_model() returned None.")

    except TypeError as te:
        print("--- Synchronous Test Failed: TypeError ---")
        print(f"Error message: {te}")
        if "unexpected keyword argument 'options'" in str(te):
            print("This confirms the 'options' argument is not supported for llm.get_model().")
        import traceback
        traceback.print_exc()
        print("------------------------------------")
    except Exception as e:
        print("--- Synchronous Test Failed: An error occurred ---")
        print(f"Error type: {type(e)}")
        print(f"Error message: {e}")
        import traceback
        traceback.print_exc()
        print("------------------------------------")

    # Demonstrate the error explicitly
    print("\n--- Attempting llm.get_model() WITH 'options' (expected to fail) ---")
    try:
        model_with_options = llm.get_model(MODEL_NAME, options={"host": DESIRED_OLLAMA_HOST})
        print(f"Unexpectedly succeeded in getting model with options: {model_with_options}")
    except TypeError as te:
        print(f"Successfully caught expected TypeError: {te}")
        print("This confirms 'options' is not a valid argument for llm.get_model().")
        print("The Ollama host should be configured via OLLAMA_HOST/OLLAMA_BASE_URL environment variables.")
    except Exception as e:
        print(f"Caught an unexpected error when trying to force TypeError: {e}")
    print("--------------------------------------------------------------------")


if __name__ == "__main__":
    print("--- Starting LLM Connection Test ---")
    print(f"IMPORTANT: Please ensure your Ollama server is running and accessible on {DESIRED_OLLAMA_HOST}")
    print("You can typically start it with: OLLAMA_PORT=" + DESIRED_OLLAMA_PORT + " ollama serve")
    print("------------------------------------")
    
    asyncio.run(main()) 
    
    # Run the synchronous test
    test_synchronous_model()
    
    print("\n--- All Tests Finished ---") 