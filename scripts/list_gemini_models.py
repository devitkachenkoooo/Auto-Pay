#!/usr/bin/env python3
"""
Diagnostic script to list available Gemini models using the new google-genai SDK.
This script helps identify the correct model names to fix 404 errors.
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

try:
    from google import genai
except ImportError:
    print("Error: google-genai package not found. Please install it with:")
    print("pip install google-genai")
    sys.exit(1)


def list_gemini_models() -> None:
    """List all available Gemini models and highlight those supporting generateContent."""

    # Get API key from environment variable
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set.")
        print("Please set it using: export GEMINI_API_KEY='your-api-key'")
        return

    try:
        # Initialize the client
        print("Initializing Gemini client...")
        client = genai.Client(api_key=api_key)

        # Fetch all available models
        print("Fetching available models...")
        models_pager = client.models.list()

        # Get models from the pager
        models = list(models_pager)

        if not models:
            print("No models found or empty response.")
            return

        print(f"\nFound {len(models)} models:")
        print("=" * 80)

        generate_content_models = []

        for model in models:
            model_name = model.name
            display_name = getattr(model, "display_name", "N/A")
            supported_methods = getattr(model, "supported_methods", [])

            # Check if generateContent is supported
            supports_generate_content = "generateContent" in supported_methods

            if supports_generate_content:
                generate_content_models.append(model_name)

            # Print model info with highlighting for generateContent support
            status_marker = "✓" if supports_generate_content else " "
            print(f"{status_marker} Name: {model_name}")
            print(f"   Display Name: {display_name}")
            print(f"   Supported Methods: {supported_methods}")
            print("-" * 80)

        # Summary of models that support generateContent
        if generate_content_models:
            print(
                f"\n✓ Models supporting generateContent ({len(generate_content_models)}):"
            )
            for model_name in generate_content_models:
                print(f"  - {model_name}")
        else:
            print("\n⚠ No models found that support generateContent method.")

    except Exception as e:
        print(f"Error occurred: {type(e).__name__}: {str(e)}")

        # Provide specific guidance for common errors
        if "API key" in str(e).lower() or "unauthorized" in str(e).lower():
            print("\nPossible causes:")
            print("- Invalid API key")
            print("- API key not properly set in environment")
            print("- API key doesn't have access to Gemini API")
        elif "network" in str(e).lower() or "connection" in str(e).lower():
            print("\nPossible causes:")
            print("- Network connectivity issues")
            print("- Firewall blocking API requests")
        else:
            print("\nCheck your API key and network connection.")


def main():
    """Main function to run the diagnostic."""
    print("Gemini Models Diagnostic Tool")
    print("=" * 40)
    list_gemini_models()


if __name__ == "__main__":
    main()
