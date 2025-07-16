#!/usr/bin/env python3
"""
Test script to verify Selenium and OpenCV setup
"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.action_chains import ActionChains
import cv2
import numpy as np
import time
import os

def test_selenium_opencv():
    """Test if Selenium and OpenCV work together"""
    print("Testing Selenium and OpenCV setup...")
    
    try:
        # Initialize Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1280,720")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        
        print("Starting Chrome browser...")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        
        try:
            # Navigate to a test page
            print("Navigating to test page...")
            driver.get('https://example.com')
            time.sleep(2)
            
            # Take a screenshot
            print("Taking screenshot...")
            screenshot = driver.get_screenshot_as_png()
            screenshot_array = np.frombuffer(screenshot, dtype=np.uint8)
            frame = cv2.imdecode(screenshot_array, cv2.IMREAD_COLOR)
            
            # Add a test circle
            cv2.circle(frame, (100, 100), 20, (0, 0, 255), -1)
            
            # Save the test image
            test_dir = 'static/videos'
            os.makedirs(test_dir, exist_ok=True)
            test_image_path = os.path.join(test_dir, 'test_screenshot.png')
            cv2.imwrite(test_image_path, frame)
            
            print(f"✅ Test successful! Screenshot saved to: {test_image_path}")
            
            # Test mouse movement
            print("Testing mouse movement...")
            actions = ActionChains(driver)
            actions.move_by_offset(100, 100)
            actions.perform()
            time.sleep(1)
            
            print("✅ Mouse movement test successful!")
            
        finally:
            driver.quit()
            print("Browser closed.")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = test_selenium_opencv()
    if success:
        print("\n🎉 All tests passed! Your setup is ready.")
    else:
        print("\n❌ Tests failed. Please check your setup.") 