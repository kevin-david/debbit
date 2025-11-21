import logging
import random
import time

from selenium.common.exceptions import TimeoutException, ElementNotInteractableException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

import utils
from result import Result

LOGGER = logging.getLogger('debbit')

'''
How to add a new merchant module to debbit

Create a new .py file in the merchants directory. Create a new block in config.txt such that the merchant name matches
the name of your new file (excluding .py). The file must have a function with the signature
`def web_automation(driver, merchant, amount):` that returns a `Result` in all possible scenarios. In error scenarios, you
may return Result.failed or simply let whatever exception be thrown. It will be caught and handled correctly by debbit.py

For more complex scenarios, please refer to the other merchant .py files.
'''


def web_automation(driver, merchant, amount):
    driver.get('https://billpay.onlinebiller.com/ebpp/durhamub/BillPay')

    logged_in = utils.is_logged_in(driver, timeout=90,
       logged_out_element=(By.ID, 'Password'),
       logged_in_element=(By.CLASS_NAME, 'select-invoice-checkbox')
    )

    if not logged_in:
        # Navigate to login page
        driver.get('https://billpay.onlinebiller.com/ebpp/durhamub/Login/Index')
        LOGGER.info('Looking for Login ID field')
        try: 
            driver.find_element_by_id('Login').send_keys(merchant.usr)
        except ElementNotInteractableException:
            pass

        time.sleep(2)  # pause to let user watch what's happening - not necessary for real merchants
        LOGGER.info('Looking for Password field')
        driver.find_element_by_id('Password').send_keys(merchant.psw)
        time.sleep(2)  # pause to let user watch what's happening - not necessary for real merchants
        LOGGER.info('Looking for login-button')
        driver.find_element_by_id('login-button').click()
        LOGGER.info('Waiting for select-invoice-checkbox to be present')
        WebDriverWait(driver, 30).until(expected_conditions.presence_of_element_located((By.CLASS_NAME, 'select-invoice-checkbox')))

    time.sleep(2)  # pause to let user watch what's happening - not necessary for real merchants
    # Select the invoice checkbox
    LOGGER.info('Clicking select-invoice-checkbox')
    driver.execute_script("document.getElementsByClassName('select-invoice-checkbox')[0].click()")
    time.sleep(2)  # pause to let user watch what's happening - not necessary for real merchants
    
    # Set the payment amount
    LOGGER.info('Looking for PaymentAmount field')
    WebDriverWait(driver, 30).until(expected_conditions.presence_of_element_located((By.NAME, 'PaymentAmount')))
    amountInput = driver.find_elements_by_name('PaymentAmount')[0]
    amountStr = utils.cents_to_str(amount)
    LOGGER.info('Setting PaymentAmount to ' + amountStr)
    # Use JavaScript to select all and clear, then type with Selenium
    driver.execute_script("document.getElementsByName('PaymentAmount')[0].select()")
    amountInput.send_keys(amountStr)  # This will replace the selected text
    # Trigger blur to ensure the page recognizes the change
    amountInput.send_keys(Keys.TAB)
    time.sleep(2)  # pause to let user watch what's happening - not necessary for real merchants
    
    # Select payment method (account selection)
    LOGGER.info('Looking for payment-method element with card ending in ' + merchant.card[-4:])
    # Select the option that matches the card's last 4 digits
    driver.find_element_by_xpath('//*[@id="payment-method"]//*[contains(.,"****' + merchant.card[-4:] + '")]').click()
    time.sleep(2)  # pause to let user watch what's happening - not necessary for real merchants
    
    # Click the payment button
    LOGGER.info('Looking for payment-button')
    WebDriverWait(driver, 30).until(expected_conditions.element_to_be_clickable((By.ID, 'payment-button')))
    driver.find_element_by_id('payment-button').click()

    # Wait for the confirmation page and verify payment method
    LOGGER.info('Waiting for confirmation page with payment-method element')
    WebDriverWait(driver, 30).until(expected_conditions.presence_of_element_located((By.ID, 'payment-method')))
    time.sleep(2)  # pause to let user watch what's happening - not necessary for real merchants
    
    # Recheck that the payment-method element contains the last 4 of the selected card
    LOGGER.info('Verifying payment-method contains card ending in ' + merchant.card[-4:])
    paymentMethodText = driver.find_element_by_id('payment-method').text
    if merchant.card[-4:] in paymentMethodText:
        # Click the agreed checkbox
        LOGGER.info('Clicking agreed checkbox')
        driver.execute_script("document.getElementById('agreed').click()")
        time.sleep(2)  # pause to let user watch what's happening - not necessary for real merchants
        
        # Click submit-payment-btn
        LOGGER.info('Clicking submit-payment-btn')
        driver.find_element_by_id('submit-payment-btn').click()
        time.sleep(2)  # pause to let user watch what's happening - not necessary for real merchants
        
        # Check for duplicate-payment-submit-button first, if it exists click it
        LOGGER.info('Checking for duplicate-payment-submit-button')
        try:
            duplicateButton = driver.find_element_by_id('duplicate-payment-submit-button')
            duplicateButton.click()
            time.sleep(2)  # pause to let user watch what's happening - not necessary for real merchants
        except NoSuchElementException:
            LOGGER.info('duplicate-payment-submit-button not found, continuing')
            pass  # duplicate-payment-submit-button doesn't exist, continue
        
        # Wait for and verify automatic-payment-submit-button exists (should always be expected)
        LOGGER.info('Looking for automatic-payment-submit-button')
        WebDriverWait(driver, 30).until(expected_conditions.element_to_be_clickable((By.ID, 'automatic-payment-submit-button')))
        wait_time = random.randint(5, 10)
        LOGGER.info('automatic-payment-submit-button found, ' + ('clicking after ' if not merchant.dry_run else ' dry run - will wait for ') + str(wait_time) + ' seconds...' )
        time.sleep(wait_time)  # sleep for a bit to show user that payment screen is reached

        if not merchant.dry_run:
            LOGGER.info('Clicking automatic-payment-submit-button to finalize payment')
            driver.find_element_by_id('automatic-payment-submit-button').click()

            LOGGER.info('Waiting for payment confirmation number')
            try:
                # Look for text containing "confirmation" (case-insensitive)
                confirmation_element = WebDriverWait(driver, 30).until(expected_conditions.presence_of_element_located((By.XPATH, "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'confirmation')]")))
                confirmation_text = confirmation_element.text
                # Verify it contains a number
                if any(char.isdigit() for char in confirmation_text):
                    LOGGER.info('Found confirmation number: ' + confirmation_text)
                    return Result.success
                else:
                    LOGGER.warning('Found confirmation text but no number: ' + confirmation_text)
                    return Result.unverified
            except TimeoutException:
                return Result.unverified  # Purchase command was executed, yet we are unable to verify that it was successfully executed.
                # since debbit may have spent money but isn't sure, we log the error and stop any further payments for this merchant until the user intervenes
        else:
            LOGGER.info('Dry run - pausing before final payment submission')
            return Result.dry_run
    else:
        LOGGER.error('Payment method verification failed - card ending in ' + merchant.card[-4:] + ' not found in payment-method text')
        return Result.failed  # Payment method verification failed
