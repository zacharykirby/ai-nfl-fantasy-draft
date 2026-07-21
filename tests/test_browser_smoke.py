"""Focused headless-browser checks for the draft-night critical path."""

import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support import expected_conditions as expected
from selenium.webdriver.support.ui import WebDriverWait


ROOT = Path(__file__).resolve().parents[1]


def _free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


@pytest.fixture
def browser_server(web_draft):
    port = _free_port()
    command = [
        sys.executable,
        "-m",
        "fantasy_draft.api.app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--sessions-dir",
        str(web_draft["sessions_dir"]),
        "--board",
        str(web_draft["board_path"]),
    ]
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(50):
            if process.poll() is not None:
                pytest.fail("browser test server exited during startup")
            try:
                urllib.request.urlopen(f"{base_url}/api/v1/health", timeout=0.2).read()
                break
            except OSError:
                time.sleep(0.1)
        else:
            pytest.fail("browser test server did not become healthy")
        yield f"{base_url}/?session=phone-test"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.fixture
def browser(browser_server):
    if not shutil.which("firefox"):
        pytest.skip("Firefox is required for browser smoke tests")
    options = Options()
    options.add_argument("-headless")
    try:
        driver = webdriver.Firefox(options=options, service=Service(log_output=subprocess.DEVNULL))
    except WebDriverException as error:
        pytest.skip(f"Firefox WebDriver is unavailable: {error}")
    driver.set_window_rect(width=390, height=844)
    driver.get(browser_server)
    WebDriverWait(driver, 10).until(
        expected.text_to_be_present_in_element((By.ID, "session-name"), "phone-test")
    )
    try:
        yield driver
    finally:
        driver.quit()


def wait(driver, seconds=10):
    return WebDriverWait(driver, seconds)


@pytest.mark.browser
@pytest.mark.parametrize("width,height", [(320, 700), (390, 844), (700, 390)])
def test_cockpit_fits_phone_viewports_and_keeps_touch_targets(browser, width, height):
    browser.set_window_rect(width=width, height=height)
    browser.refresh()
    wait(browser).until(expected.text_to_be_present_in_element((By.ID, "current-pick"), "2"))

    overflow = browser.execute_script(
        "return document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 1

    for element_id in ("refresh", "undo-last", "draft-primary", "command-send"):
        height = browser.execute_script(
            "return arguments[0].getBoundingClientRect().height",
            browser.find_element(By.ID, element_id),
        )
        assert height >= 44, f"#{element_id} is only {height}px tall"


@pytest.mark.browser
def test_search_confirm_double_submit_and_refresh_records_one_pick(browser):
    search = browser.find_element(By.ID, "player-search")
    search.send_keys("Bijan")
    draft_button = wait(browser).until(
        expected.element_to_be_clickable((By.CSS_SELECTOR, '[data-draft-player="Bijan Robinson"]'))
    )
    draft_button.click()
    dialog = wait(browser).until(expected.visibility_of_element_located((By.ID, "confirmation-dialog")))
    assert dialog.get_attribute("open") is not None
    assert browser.find_element(By.ID, "confirmation-player").text == "Bijan Robinson"

    confirm = browser.find_element(By.ID, "confirm-pick")
    browser.execute_script("arguments[0].click(); arguments[0].click();", confirm)
    wait(browser).until(expected.text_to_be_present_in_element((By.ID, "current-pick"), "3"))
    assert browser.find_element(By.ID, "recent-picks").text.count("Bijan Robinson") == 1

    browser.refresh()
    wait(browser).until(expected.text_to_be_present_in_element((By.ID, "current-pick"), "3"))
    assert browser.find_element(By.ID, "recent-picks").text.count("Bijan Robinson") == 1


@pytest.mark.browser
def test_undo_confirmation_restores_latest_pick(browser):
    browser.find_element(By.ID, "undo-last").click()
    dialog = wait(browser).until(expected.visibility_of_element_located((By.ID, "undo-dialog")))
    assert dialog.get_attribute("open") is not None
    assert browser.find_element(By.ID, "undo-player").text == "Jahmyr Gibbs"
    dialog.find_element(By.CSS_SELECTOR, 'button[value="confirm"]').click()

    wait(browser).until(expected.text_to_be_present_in_element((By.ID, "current-pick"), "1"))
    assert "No selections yet" in browser.find_element(By.ID, "recent-picks").text
    assert browser.find_element(By.ID, "health-autosave").text == "Saved"


@pytest.mark.browser
def test_board_navigation_and_position_filter_remain_interactive(browser):
    browser.find_element(By.CSS_SELECTOR, '[data-view="board"]').click()
    wait(browser).until(expected.visibility_of_element_located((By.ID, "view-board")))
    wait(browser).until(expected.presence_of_element_located((By.CSS_SELECTOR, ".tier-section")))

    browser.find_element(By.CSS_SELECTOR, '[data-board-position="WR"]').click()
    wait(browser).until(
        lambda driver: driver.find_element(By.ID, "full-board").text.startswith("WR")
        or "Ja'Marr Chase" in driver.find_element(By.ID, "full-board").text
    )
    board_text = browser.find_element(By.ID, "full-board").text
    assert "Ja'Marr Chase" in board_text
    assert "Josh Allen" not in board_text

    browser.find_element(By.CSS_SELECTOR, '[data-view="cockpit"]').click()
    te_filter = browser.find_element(By.CSS_SELECTOR, '[data-position="TE"]')
    browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", te_filter)
    wait(browser).until(expected.element_to_be_clickable((By.CSS_SELECTOR, '[data-position="TE"]')))
    te_filter.click()
    available_text = browser.find_element(By.ID, "best-available").text
    assert "Trey McBride" in available_text
    assert "Ja'Marr Chase" not in available_text
