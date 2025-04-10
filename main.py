import os
import logging
import discord
from discord.ext import commands
from dotenv import load_dotenv
from stocks import PolygonClient
import logging.handlers
import sys

# Create the main logger
logger = logging.getLogger("stockbot")
logger.setLevel(logging.DEBUG)

# Format for both handlers
formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', '%Y-%m-%d %H:%M:%S', style='{')

# 🔹 File Handler (rotates up to 5 files, 32 MiB each)
file_handler = logging.handlers.RotatingFileHandler(
    filename='discord.log',
    encoding='utf-8',
    maxBytes=32 * 1024 * 1024,
    backupCount=5
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# 🔹 Console Handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Optional: control Discord lib logging
discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.INFO)
discord_logger.addHandler(console_handler)

load_dotenv()
POLYGON_API_KEY = os.getenv("API_KEY")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

class StockBot(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.polygon_client = PolygonClient(api_key=POLYGON_API_KEY)

    @commands.command(name="stock")
    async def look_up_stock(self, ctx, raw_ticker: str):
        ticker = raw_ticker.upper()
        logger.info(f"[COMMAND] !stock invoked by {ctx.author} for ticker: {ticker}")

        try:
            details = self.polygon_client.filtered_ticker_details(ticker)
            snapshot = self.polygon_client.filter_snapshot_ticker(ticker)
        except Exception as e:
            logger.exception(f"Exception while fetching stock data for {ticker}: {e}")
            embed = self.create_ticker_error_embed(ticker, f"Internal error: {str(e)}")
            await ctx.send(embed=embed)
            return

        if not details or not snapshot or "error" in details or "error" in snapshot:
            error_msg = details.get("error") if details and "error" in details else snapshot.get("error", "Unknown error")
            request_id = snapshot.get("request_id") if snapshot else None
            logger.warning(f"[ERROR] Failed to fetch data for {ticker} | Error: {error_msg}")
            embed = self.create_ticker_error_embed(ticker, error_msg, request_id)
            await ctx.send(embed=embed)
            return

        price = snapshot.get("close")
        change_dollar = snapshot.get("dollar")
        change_percent = snapshot.get("percent")

        # Price fallback
        price_str = f"${price:,.2f}" if price is not None else "N/A"

        # Format price change with emoji and alignment
        if change_dollar is not None and change_percent is not None:
            if change_dollar > 0:
                change_str = f"📈 +${change_dollar:,.2f} / {change_percent:.2f}%"
            elif change_dollar < 0:
                change_str = f"📉 -${abs(change_dollar):,.2f} / {abs(change_percent):.2f}%"
            else:
                change_str = f"➖ $0.00 / 0.00%"
        else:
            change_str = "N/A"

        embed = discord.Embed(title=f"{ticker} Snapshot", color=discord.Color.green())

        embed.add_field(
            name="Price (USD)      Today's Change",
            value=f"{price_str:<18} {change_str}",
            inline=False
        )

        embed.add_field(name="\u200b", value="───────────────", inline=False)

        for label, value in details.items():
            if label == "branding":
                logger.debug(f"[INFO] Setting thumbnail for {ticker} from branding.icon_url: {value}")
                embed.set_thumbnail(url=value)
                continue
            embed.add_field(name=label, value=value, inline=False)
        embed.set_footer(text="Data provided by Polygon.io")
        await ctx.send(embed=embed)

    def create_ticker_error_embed(self, ticker: str, error_message: str, request_id: str = None):
        embed = discord.Embed(
            title="❌ Error Fetching Ticker Details",
            description=f"Could not retrieve data for ticker: `{ticker}`",
            color=discord.Color.red()
        )

        embed.add_field(name="Error", value=error_message, inline=False)

        if request_id:
            embed.add_field(name="Request ID", value=f"`{request_id}`", inline=False)

        embed.set_footer(text="Powered by Polygon.io | Check the ticker symbol and try again.")

        return embed

class MyBot(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def setup_hook(self):
        await self.add_cog(StockBot(self))

# Initialize and run the bot
intents = discord.Intents.default()
intents.message_content = True
bot = MyBot(command_prefix="!", intents=intents)
logger.info("Starting Discord bot...")
bot.run(DISCORD_TOKEN)



# client = RESTClient(api_key=POLYGON_API_KEY)

# def filter_ticker_details(details):
#     details_dict = details.__dict__
#     filtered_dict = {}
#     categories = {
#         "active": "Trading Status", 
#         "branding": "branding", 
#         "cik": "CIK Code",
#         "delisted_utc": "Delisted Time",
#         "description": "Company Description",
#         "homepage_url": "Homepage URL",
#         "market": "Asset Class",
#         "market_cap": "Market Capitalization",
#         "name": "Company Name",
#         "weighted_shares_outstanding": "Shares Outstanding",
#         "share_class_shares_outstanding": "Shares Outstanding",
#         "sic_code": "SIC Code",
#         "sic_description": "SIC Description",
#         "ticker": "Ticker",
#         "total_employees": "Total Number of employees"}
#     for details in details_dict:
#         if details_dict.get(details, None) is None or details not in categories:
#             print(f"{details} || {details_dict.get(details)}")
#             continue
#         if details == "branding":
#             if hasattr(details_dict.get(details, None), "icon_url"):
#                 filtered_dict["branding"] = details_dict.get(details, None).icon_url
#         if details not in filtered_dict:
#             filtered_dict[details] = details_dict.get(details, None)
#     return filtered_dict

# # details = client.get_ticker_details(ticker="INTC")
# # print(details.__dict__)
# # print("--------------------------------------\n")
# # print(filter_ticker_details(details))

# # url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

# # # Load the S&P 500 table
# # sp500_df = pd.read_html(url)[0]

# # # Extract only the ticker symbols
# # sp500_tickers = sp500_df['Symbol']

# # # Save to CSV
# # sp500_tickers.to_csv("sp500_tickers.csv", index=False, header=True)

# def filter_snapshot_ticker(ticker):
#     try:
#         snapshot = client.get_snapshot_ticker("stocks", ticker)
#     except Exception as e:
#         return {"error": f"{str(e)}"}
#     filtered_dict = {}
#     if hasattr(snapshot, "day"):
#         if getattr(snapshot.day, "close") is not None:
#             filtered_dict["close"] = snapshot.day.close
#     if getattr(snapshot, "todays_change", None) is not None:
#         filtered_dict["dollar"] = snapshot.todays_change
#     if getattr(snapshot, "todays_change_percent", None) is not None:
#         filtered_dict["percent"] = snapshot.todays_change_percent
#     return filtered_dict

# snapshot = filter_snapshot_ticker("TSLA")

