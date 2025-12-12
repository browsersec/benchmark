import asyncio
import os
import time
from pathlib import Path
from playwright.async_api import Playwright, async_playwright

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).parent.resolve()
TEMP_FILES_DIR = SCRIPT_DIR / "temp_files"


async def upload_file(page, file_path: str) -> None:
    """Upload a file using the file chooser dialog"""
    # Start waiting for file chooser before clicking
    async with page.expect_file_chooser() as fc_info:
        await page.get_by_role("button", name="Upload File").click()
    file_chooser = await fc_info.value
    await file_chooser.set_files(file_path)
    # Wait for upload to complete
    await asyncio.sleep(2)


async def run(playwright: Playwright) -> None:
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context()
    page = await context.new_page()
    
    await page.goto("http://localhost:5173/")
    await page.get_by_role("link", name="Office Session").click()
    await page.get_by_role("button", name="Create Office Session").click()
    
    # Wait for the office session to be ready
    await asyncio.sleep(5)
    
    # Files to upload (just filenames, will be joined with TEMP_FILES_DIR)
    filenames = [
        # Documents
        "Module2-Topic5-Graph Based Data Model.pptx",
        "sample1.odt",
        "sample2.docx",
        "sample1.odp",
        "sample2.csv",
        "sample3.txt",
        "sample3.pdf",
        "sample3.ods",
        # Images
        "sample_5184×3456.jpeg",
        "sample_1280×853.gif",
        "sample1.webp",
        "sample_5184×3456.jpg",
        # Audio
        "sample3.mp3",
        # Video
        "sample_640x360.mov",
        "sample_960x540.mp4",
        "sample_640x360.mkv",
        "sample_960x540.flv",
        "sample_960x540.wmv",
        "sample_640x360.avi",
        "sample_640x360.webm",
        # Archives
        "sample-1.zip",
        "sample-1.rar",
        "sample-1.tar",
        "sample-3.gz",
        "sample-3.bz2",
        "sample-1.7z",
    ]
    
    # Upload each file
    for filename in filenames:
        file_path = TEMP_FILES_DIR / filename
        if file_path.exists():
            print(f"Uploading: {filename}")
            time.sleep(6)
            await upload_file(page, str(file_path))
            print(f"Uploaded: {filename}")
        else:
            print(f"File not found: {file_path}")
    
    # Keep session open for viewing
    print("All files uploaded. Keeping session open...")
    await asyncio.sleep(60)  # Keep open for 1 minute
    
    # Disconnect
    await page.get_by_role("button", name="Disconnect").nth(1).click()
    
    await context.close()
    await browser.close()


async def main() -> None:
    async with async_playwright() as playwright:
        await run(playwright)


if __name__ == "__main__":
    asyncio.run(main())
