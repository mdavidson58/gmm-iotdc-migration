import requests
import time
from logs import log
from core.constants import MAX_RETRIES


def serve_post_request(url, headers, pay_load):
    attempt_num = 0
    logger = log.get_logger("Post Request for :: {}".format(url))
    try:
        while attempt_num < MAX_RETRIES:
            response = requests.post(url, headers=headers, json=pay_load, verify=True, timeout=120)
            if 200 == response.status_code:
                logger.info("Success")
                return {"status": response.status_code, "data": response.json()}
            else:
                attempt_num += 1
                time.sleep(5)   # Wait for 5 seconds before re-trying
                logger.info("Failed")
                logger.error("error ::{}".format(response.json()))
            return {"status": response.status_code, "error": response.json()}
    except Exception as e:
        logger.error("{}{}".format(e, e.message))

def serve_get_request(url, headers, params=None):
    if params is None:
        params = {}
    attempt_num = 0
    logger = log.get_logger("Get Request for :: {}".format(url))
    try:
        while attempt_num < MAX_RETRIES:
            response = requests.get(url, headers=headers, params=params, verify=True, timeout=30)
            if 200 == response.status_code:
                logger.info("Success")
                return {"status": response.status_code, "data": response.json()}
            else:
                attempt_num += 1
                time.sleep(5)  # Wait for 5 seconds before re-trying
                logger.info("Failed to get data")
                logger.error("error :: {}".format(response.text))
            return {'status': response.status_code, "error": response.text}
    except Exception as e:
        logger.error("{}{}".format(e, e.message))
