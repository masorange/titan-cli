"""Preview for LoaderRenderer component."""

import time
from ..loader import LoaderRenderer


def preview_loader():
    """Preview LoaderRenderer with different styles and providers."""
    loader = LoaderRenderer()

    # Example 1: Simple loader
    print("\n1. Simple loader:")
    with loader.spin("Processing data..."):
        time.sleep(2)

    # Example 2: Claude AI loader
    print("\n2. Claude AI generating commit message:")
    with loader.spin("Generating commit message...", provider="claude"):
        time.sleep(2)

    # Example 3: Gemini AI loader
    print("\n3. Gemini AI analyzing code:")
    with loader.spin("Analyzing code structure...", provider="gemini"):
        time.sleep(2)

    # Example 4: Generic AI loader
    print("\n4. Generic AI loader:")
    with loader.spin("Running AI analysis...", provider="ai"):
        time.sleep(2)

    # Example 5: Different spinner styles
    print("\n5. Different spinner styles:")

    print("   - Dots spinner:")
    with loader.spin("Loading (dots)...", spinner="dots"):
        time.sleep(1.5)

    print("   - Arc spinner:")
    with loader.spin("Loading (arc)...", spinner="arc"):
        time.sleep(1.5)

    print("   - Line spinner:")
    with loader.spin("Loading (line)...", spinner="line"):
        time.sleep(1.5)

    # Example 6: Manual control with updates
    print("\n6. Manual control with status updates:")
    loader.start("Step 1: Fetching data...", provider="claude")
    time.sleep(1)

    loader.update("Step 2: Processing results...", provider="claude")
    time.sleep(1)

    loader.update("Step 3: Finalizing...", provider="claude")
    time.sleep(1)

    loader.stop()

    print("\n✅ Preview complete!")


if __name__ == "__main__":
    preview_loader()
