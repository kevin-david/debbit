import logging
import time

from selenium.common.exceptions import TimeoutException, ElementNotInteractableException
from selenium.webdriver.common.by import By
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
    driver.get('https://ipn2.paymentus.com/cp/dhnc')

    logged_in = utils.is_logged_in(driver, timeout=90,
       logged_out_element=(By.ID, 'id_password'),
       logged_in_element=(By.ID, 'submit-payment') # TODO
    )

    if not logged_in:
        try: 
            driver.find_element_by_id('id_loginId').send_keys(merchant.usr)
        except ElementNotInteractableException:
            pass

        time.sleep(2)  # pause to let user watch what's happening - not necessary for real merchants
        driver.find_element_by_id('id_password').send_keys(merchant.psw)
        time.sleep(2)  # pause to let user watch what's happening - not necessary for real merchants
        driver.find_element_by_xpath('//*[contains(@class, "col-whole-action")]//*[contains(@value, "Login")]').click()
        WebDriverWait(driver, 30).until(expected_conditions.element_to_be_clickable((By.XPATH, '//*[contains(@class, "nav-item-make-payment")]')))

    time.sleep(2)  # pause to let user watch what's happening - not necessary for real merchants
    driver.find_element_by_class_name('nav-item-make-payment').click()
    time.sleep(2)  # pause to let user watch what's happening - not necessary for real merchants
    WebDriverWait(driver, 30).until(expected_conditions.element_to_be_clickable((By.XPATH, '//*[contains(@class, "btn-type-next")]')))
    
    driver.find_element_by_xpath('//*[@id="label-radio-pt-1-0"]/span').click() # Just pick the first account
    time.sleep(2)  # pause to let user watch what's happening - not necessary for real merchants
    driver.find_element_by_class_name('btn-type-next').click()

    toConfirmXPath = '//*[contains(@class, "col-whole-action")]//*[contains(@data-id, "btn-payment-details-next")]'
    WebDriverWait(driver, 30).until(expected_conditions.element_to_be_clickable((By.XPATH, toConfirmXPath)))
    amountInput = driver.find_element_by_xpath('//*[contains(@class, "paymentAmountCol")]/input')
    amountInput.clear()
    amountInput.send_keys(utils.cents_to_str(amount))

    time.sleep(2)  # pause to let user watch what's happening - not necessary for real merchants
    driver.find_element_by_xpath('//*[contains(@class, "paymentRadio")]/*[contains(text(),"****' + merchant.card[-4:] + '")]').click()
    time.sleep(2)
    driver.find_element_by_xpath(toConfirmXPath).click()

    confirmXpath = '//*[contains(@class, "col-whole-action")]//*[contains(@data-id, "btn-payment-confirmation")]'
    WebDriverWait(driver, 30).until(expected_conditions.element_to_be_clickable((By.XPATH, confirmXpath)))
    time.sleep(30)  # sleep for a bit to show user that payment screen is reached

    if merchant.dry_run == False:
        driver.find_element_by_xpath(confirmXpath).click()

        try:
            WebDriverWait(driver, 30).until(expected_conditions.presence_of_element_located((By.XPATH, "//*[contains(text(),'have been accepted')]")))
        except TimeoutException:
            return Result.unverified  # Purchase command was executed, yet we are unable to verify that it was successfully executed.
            # since debbit may have spent money but isn't sure, we log the error and stop any further payments for this merchant until the user intervenes

        return Result.success
    else:
        return Result.dry_run
