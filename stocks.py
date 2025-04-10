from dataclasses import dataclass
from typing import Optional
from polygon import RESTClient
from polygon.exceptions import BadResponse, AuthError
from polygon.rest.models import SnapshotMarketType
import logging

# Configure logger for this module
logger = logging.getLogger("stockbot")
logger.setLevel(logging.DEBUG)

class PolygonClient:
    def __init__(self, api_key):
        self.client = RESTClient(api_key=api_key)
        self.api_key = api_key
        self.details_categories = {
            "name": "Company Name",
            "ticker": "Ticker",
            "market_cap": "Market Capitalization",
            "description": "Company Description",
            "total_employees": "Total Number of Employees",
            "weighted_shares_outstanding": "Shares Outstanding",
            "share_class_shares_outstanding": "Class Shares Outstanding",
            "sic_description": "Industry",
            "sic_code": "SIC Code",
            "active": "Trading Status",
            "delisted_utc": "Delisted Time",
            "homepage_url": "Homepage URL",
            "cik": "CIK Code",
            "branding": "branding"
        }
        logger.info("PolygonClient initialized with API key.")

    def filtered_ticker_details(self, ticker):
        logger.info(f"Fetching ticker details for: {ticker}")
        try:
            details = self.client.get_ticker_details(ticker=ticker)
        except Exception as e:
            logger.error(f"Error fetching ticker details for {ticker}: {e}", exc_info=True)
            return {"error": f"Exception occurred: {str(e)}"}

        details_dict = details.__dict__
        filtered_dict = {}

        for key in details_dict:
            value = details_dict.get(key)
            if value is None or key not in self.details_categories:
                logger.debug(f"Skipping irrelevant or None field: {key}")
                continue

            if key == "branding":
                branding = value
                if hasattr(branding, "icon_url") and branding.icon_url:
                    filtered_dict["branding"] = f"{branding.icon_url}?apiKey={self.api_key}"
                    logger.debug(f"Added branding icon URL for {ticker}")
                continue
            else:
                display_name = self.details_categories[key]
                filtered_dict[display_name] = value
                logger.debug(f"Mapped {key} to {display_name}: {value}")

        logger.info(f"Finished filtering details for {ticker}")
        return filtered_dict

    def filter_snapshot_ticker(self, ticker):
        logger.info(f"Fetching snapshot for: {ticker}")
        try:
            snapshot = self.client.get_snapshot_ticker("stocks", ticker)
        except Exception as e:
            logger.error(f"Error fetching snapshot for {ticker}: {e}", exc_info=True)
            return {"error": f"{e}"}

        filtered_dict = {}

        if hasattr(snapshot, "day") and getattr(snapshot.day, "close", None) is not None:
            filtered_dict["close"] = snapshot.day.close
            logger.debug(f"{ticker} close price: {snapshot.day.close}")

        if getattr(snapshot, "todays_change", None) is not None:
            filtered_dict["dollar"] = snapshot.todays_change
            logger.debug(f"{ticker} change ($): {snapshot.todays_change}")

        if getattr(snapshot, "todays_change_percent", None) is not None:
            filtered_dict["percent"] = snapshot.todays_change_percent
            logger.debug(f"{ticker} change (%): {snapshot.todays_change_percent}")

        logger.info(f"Finished filtering snapshot for {ticker}")
        return filtered_dict
