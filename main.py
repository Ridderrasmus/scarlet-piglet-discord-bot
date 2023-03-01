from discordbot import *
import multiprocessing
import os

def main():
    # Run the bot
    BOT.run(token=os.getenv('DISCORD_TOKEN'), log_handler=log_handler)
    

if __name__ == "__main__":
    main()
