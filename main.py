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
            elif label == "Market Capitalization":
                market_cap = f"${value:,.2f}"
                embed.add_field(name=label, value=market_cap, inline=False)
            elif label in ["Total Number of Employees", "Shares Outstanding", "Class Shares Outstanding"]:
                result = f"{value:,}"
                embed.add_field(name=label, value=result, inline=False)
            else:
                embed.add_field(name=label, value=value, inline=False)
        if "Market Capitalization" not in details:
            if "Shares Outstanding" in details:
                market_cap = details.get("Shares Outstanding") * price
                embed.add_field(name="Market Capitalization", value=market_cap, inline=False)
            elif "Class Shares Outstanding" in details:
                market_cap = details.get("Shares Outstanding") * price
                embed.add_field(name="Market Capitalization", value=market_cap, inline=False)
        embed.set_footer(text="Data provided by Polygon.io (Data has a 15-min delay)")
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

    @commands.command(name="topspy")
    async def top_spy_movers(self, ctx):
        logger.info(f"[COMMAND] !topspy invoked by {ctx.author}")

        try:
            snapshots = self.polygon_client.filter_spy_snapshots()
        except Exception as e:
            logger.exception(f"Error fetching SPY snapshots: {e}")
            await ctx.send("❌ Failed to fetch S&P 500 stock data.")
            return

        if "error" in snapshots:
            await ctx.send(f"❌ API Error: {snapshots['error']}")
            return

        sorted_data = sorted(snapshots.items(), key=lambda x: x[1].get("percent", 0), reverse=True)
        top_gainers = sorted_data[:10]
        top_losers = sorted_data[-10:][::-1] 

        embed = discord.Embed(
            title="📊 Top 10 Gainers & Losers in the S&P 500",
            color=discord.Color.blue()
        )

        def format_entry(entry):
            ticker, data = entry
            percent = data.get("percent", 0)
            return f"`{ticker}`: {percent:+.2f}%"

        gainers_str = "\n".join(format_entry(entry) for entry in top_gainers)
        losers_str = "\n".join(format_entry(entry) for entry in top_losers)

        embed.add_field(name="📈 Gainers", value=gainers_str or "N/A", inline=True)
        embed.add_field(name="📉 Losers", value=losers_str or "N/A", inline=True)

        embed.set_footer(text="Data based on today's % change in S&P 500 (Polygon.io)")
        await ctx.send(embed=embed)

    @commands.command(name="joever")
    async def joever_check(self, ctx, raw_ticker: str):
        ticker = raw_ticker.upper()
        logger.info(f"[COMMAND] !joever invoked by {ctx.author} for ticker: {ticker}")

        try:
            snapshot = self.polygon_client.filter_snapshot_ticker(ticker)
        except Exception as e:
            logger.exception(f"Exception during joever check for {ticker}: {e}")
            await ctx.send(f"❌ Could not fetch data for `{ticker}`.")
            return

        if not snapshot or "error" in snapshot:
            await ctx.send(f"❌ Error: {snapshot.get('error', 'Unknown error')}")
            return

        pct_change = snapshot.get("percent")
        close_price = snapshot.get("close")

        if pct_change is None:
            await ctx.send(f"⚠️ No percent data available for `{ticker}`.")
            return

        
        if pct_change > 1.5:
            title = f"🚀 ${ticker} is so back 🚀"
            image_url = "https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExdjhndGN3czR0b3RybHZpOXNucGpjZGRnNDhpamxkejY3emIxbDMwYyZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/rsANkiygv0Jpyn7mFC/giphy.gif"
            color = discord.Color.green()
        elif pct_change < -1.5:
            title = f"😢 ${ticker} is so joever... 😭"
            image_url = "https://media4.giphy.com/media/ERIB4ws3cw17uWN4mF/200w.gif?cid=6c09b952hm65rrscei4j4nsn0ylwn1ftn5q9mgq3ecdr1tl6&ep=v1_gifs_search&rid=200w.gif&ct=g"
            color = discord.Color.red()
        else:
            title = f"${ticker} is stable"
            image_url = "https://media4.giphy.com/media/v1.Y2lkPTc5MGI3NjExcDQ0bDRycjgzbjR5Nnl4bmxmZW5pNjdidWR6dmJiamdvcHozNTA2aSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/OmSSWmIbtknHyHWcQ6/giphy.gif"
            color = discord.Color.dark_gray()

        embed = discord.Embed(title=title, color=color)
        embed.add_field(name="Ticker", value=f"`{ticker}`", inline=True)
        embed.add_field(name="Close Price", value=f"${close_price:,.2f}" if close_price else "N/A", inline=True)
        embed.add_field(name="Change (%)", value=f"{pct_change:+.2f}%", inline=True)
        embed.set_image(url=image_url)
        embed.set_footer(text="Powered by Polygon.io | 15-min delayed data")

        await ctx.send(embed=embed)


class MyBot(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def setup_hook(self):
        await self.add_cog(StockBot(self))

if __name__ == "__main__":
    intents = discord.Intents.default()
    intents.message_content = True
    bot = MyBot(command_prefix="!", intents=intents)
    logger.info("Starting Discord bot...")
    bot.run(DISCORD_TOKEN)


