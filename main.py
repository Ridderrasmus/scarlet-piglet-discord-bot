from discordbot import *
import multiprocessing
import os
import utils

log = utils.log_handler

def main():
    # Run the bot
    BOT.run(token=os.getenv('DISCORD_TOKEN'), log_handler=log)
    

if __name__ == "__main__":
    main()
