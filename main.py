from discordbot import *
import multiprocessing
import os
import utils

log = utils.log_handler


def main():
    # Run the bot
    discordtoken = os.getenv("DISCORD_TOKEN")
    if discordtoken:
        BOT.run(token=discordtoken)
    else:
        print("No discord token found. Please set the DISCORD_TOKEN environment variable.")


if __name__ == "__main__":
    main()
