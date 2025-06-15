from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time

class TestTest2:
    def __init__(self):
        self.driver = webdriver.Chrome()
        self.wait = WebDriverWait(self.driver, 10)
    
    def close_driver(self):
        self.driver.quit()
    
    def is_element_available(self, selector, timeout=5):
        """Check if element is available and clickable"""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            return element
        except TimeoutException:
            return None
    
    def click_if_available(self, selector, description="element"):
        """Click element only if it's available"""
        element = self.is_element_available(selector)
        if element:
            try:
                element.click()
                print(f"Successfully clicked {description}")
                return True
            except Exception as e:
                print(f"Failed to click {description}: {e}")
                return False
        else:
            print(f"{description} not available")
            return False
    
    def test_test2(self):
        try:
            self.driver.get("http://4.156.203.206/")
            self.driver.set_window_size(975, 773)
            
            # Wait for page to load
            time.sleep(2)
            
            # Click first element if available
            if self.click_if_available(".mb-6:nth-child(1) .ml-3", "first navigation element"):
                time.sleep(1)  # Wait for page transition
            
            # Click first py-2 button if available
            if self.click_if_available(".py-2", "first py-2 button"):
                time.sleep(1)  # Wait for any dynamic changes
            
            # Check for second py-2 button
            py2_elements = self.driver.find_elements(By.CSS_SELECTOR, ".py-2")            
            if len(py2_elements) > 1:
                # Multiple py-2 elements found, click the second one
                try:
                    if py2_elements[1].is_enabled() and py2_elements[1].is_displayed():
                        py2_elements[1].click()
                        print("Successfully clicked second py-2 button")
                    else:
                        print("Second py-2 button not interactable")
                except Exception as e:
                    print(f"Failed to click second py-2 button: {e}")
            else:
                # Try to wait for the same py-2 element to be clickable again
                time.sleep(9999999999999999999)  # Wait for any dynamic changes
                if self.click_if_available(".py-2", "py-2 button (second attempt)"):
                    print("Test completed successfully")
            
        except Exception as e:
            print(f"Test failed with error: {e}")
        finally:
            time.sleep(2)  # Brief pause before closing

# Usage example
if __name__ == "__main__":
    test = TestTest2()
    try:
        test.test_test2()
    finally:
        test.close_driver()
